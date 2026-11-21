---
name: codync-tailscale-host
description: Install a Codync host (persistent coding-agent bots driven from a phone or desktop app) on Linux or macOS so it is reachable ONLY over the user's Tailscale tailnet, with the Codync cloud relay off, automatic updates on, and chosen environment variables (agent auth tokens etc.) passed into the background service. Use when the user asks to install, set up, harden or replicate a Codync host, make Codync tailnet-only, turn off the Codync cloud relay, or fix bots that can't see env vars or tokens under the codync-host service.
---

# Codync host, reachable only over Tailscale

[Codync](https://github.com/leepokai/Codync) (Apache-2.0) runs coding agents
(Claude Code, Codex, Gemini CLI, …) as persistent bots on a computer and lets
paired phones and desktops drive them. This skill takes a machine to a Codync
host that:

- listens only where tailnet peers can reach it (never the LAN or the internet),
- does not register with the Codync cloud relay,
- updates itself automatically, and
- passes the variables the user chooses (for example the agents' auth tokens)
  into the background service, where shell rc files never reach.

It supports **Linux** (systemd `--user` unit `codync-host.service`) and
**macOS** (launchd LaunchAgent `com.pokai.codync.host`). Installing Tailscale
itself is out of scope: it must already be up.

Upstream behaviour below was read from the Codync source (host 2.5x). Where a
step depends on a version detail, the skill says how to check it on the
machine rather than trusting this text.

## Placeholders

| Placeholder | Meaning | Default |
|---|---|---|
| `{PORT}` | host port | `19222` |
| `{TAILSCALE_INTERFACE}` | Linux Tailscale interface | `tailscale0` |
| `{ENV_NAME}` | short name for the env file | `agents` |
| `{ENV_FILE}` | private env file | `~/.config/codync-host/{ENV_NAME}.env` |
| `{VAR_NAME}` | each variable the user chooses to pass in | — |
| `{VERSION}` | pinned Codync release tag, e.g. `v2.50.0` | latest release, pinned |
| `{TAILNET_HOSTNAME}` | this machine's MagicDNS name or `100.x` address | from `tailscale status` |
| `{LAN_OR_PUBLIC_IP}` | an address of this machine outside the tailnet | — |

## Ground rules for Claude

- Ask the questions in Step 1 **one at a time**, waiting for each answer.
- **Never print secret values.** Move values only by redirection into
  `0600` files; verify by printing variable **names** only.
- Steps needing `sudo` (firewall, linger) are run by the user if Claude has no
  sudo; give them one command at a time.
- Every step is idempotent: re-running it leaves the same state. Check before
  changing (existing rules, existing drop-ins, existing bind).
- The order matters. The host binds **every interface by default** and
  `codync-host install` starts it immediately, so the network lockdown (Step 4)
  comes **before** the install (Step 6).

## Step 1: Ask the user (one at a time)

1. **"Which OS account will run the host?"** Bots run as this user, with all of
   its permissions (files, SSH keys, Docker group membership…). Recommend a
   dedicated or development account, not an admin account with broad access.
   Claude must be running as that account for the rest of the skill.
2. **"Which port?"** Default `{PORT}` = 19222; change only if taken.
3. **"Which environment variables should the bots get?"** Typically the coding
   agents' auth tokens (e.g. a Claude Code OAuth token, API keys) and the
   tokens their tools need. Apply least privilege: **every bot, and every
   device paired to drive a bot, can read them.** Recommend leaving out
   database, cloud-admin and production credentials unless a bot needs them.
   Record the names as `{VAR_NAME}` values; never ask for the values in chat.
4. **"Pin a version?"** Recommend yes: pin `{VERSION}` to the release whose
   installer you review in Step 3. Auto-updates (Step 8) take over afterwards.
5. **"Turn usage analytics off too?"** Optional, `codync-host analytics off`.

## Step 2: Preflight

```bash
uname -s                       # Linux or Darwin
tailscale status | head -5     # must show this machine online
command -v node npx            # Claude Code, Codex and Pi run through npx
echo "$PATH" | tr ':' '\n' | grep -x "$HOME/.local/bin"   # binaries land here
```

- Missing `~/.local/bin` on PATH: add it to the shell rc. The service captures
  the PATH of the shell that runs `codync-host install`, so make sure that
  shell's PATH finds `npx`, `node`, `claude`, `codex`, … **before** Step 6.
- Already installed? `codync-host status` shows `installed`, `running`,
  `port`, `bind`. Skip to the first step whose state is wrong.

## Step 3: Download, review and run the installer

Don't pipe an unreviewed script into `sh`. Download it, read it, then run the
copy you read, pinned to a release:

```bash
work="$(mktemp -d)"
curl -fsSL -o "$work/install.sh" https://raw.githubusercontent.com/leepokai/Codync/main/packaging/install.sh
less "$work/install.sh"        # Claude: read it and summarize to the user
CODYNC_VERSION={VERSION} sh "$work/install.sh" --host-only
codync-host --version
```

What the script does (verify against the copy you read):

- Downloads `codync-host-{os}-{arch}.tar.gz` from GitHub Releases and checks it
  against the published `.sha256`.
- Installs `codync-host` (plus `codync-screen` and `cua-driver` on Linux) into
  `~/.local/bin` as a non-root user, without sudo.
- Restarts an already-installed service that runs that binary; it does not
  create the service.
- `--host-only` matters on **macOS** too: without it the script installs
  `Codync.app` into `/Applications` and opens it. Use `--host-only` for
  servers and headless Macs; the standalone host is also what the built-in
  updater (Step 8) updates.

## Step 4: Lock the port to the tailnet (before the host starts)

`--bind` accepts only `127.0.0.1` or `0.0.0.0`; it refuses a tailnet IP or an
interface ("the host only binds 127.0.0.1 (this computer) or 0.0.0.0 (every
interface)"), because every local client (bots' MCP servers, `status`, the
updater's health check) dials `127.0.0.1`. The choice is saved in
`~/.codync/bind` and survives updates and reinstalls.

### Linux: bind 0.0.0.0, allow the port only on the Tailscale interface (ufw)

```bash
sudo ufw status verbose
```

It must say `Status: active` and `Default: deny (incoming)`. If ufw is inactive
or allows incoming by default, **stop**: binding 0.0.0.0 would expose the port.
Either fix the firewall with the user (enabling ufw on a remote machine needs
an SSH allow rule first, or you lock yourself out), or use the macOS approach
below (`--bind 127.0.0.1` plus `tailscale serve`), which works on Linux too.

Add the allow rule, only if it isn't already there:

```bash
sudo ufw status | grep -q "{PORT}/tcp on {TAILSCALE_INTERFACE}" \
  || sudo ufw allow in on {TAILSCALE_INTERFACE} to any port {PORT} proto tcp comment 'codync-host (tailnet only)'
sudo ufw status numbered | grep {PORT}
```

With default-deny incoming, no explicit deny rule is needed. Docker's
published-port bypass of ufw doesn't apply: the host is a normal process, not a
container. Other firewalls (firewalld, nftables) follow the same rule: allow
`{PORT}/tcp` on `{TAILSCALE_INTERFACE}`, deny it everywhere else.

### macOS: bind 127.0.0.1, publish to the tailnet with `tailscale serve`

macOS has no ufw, its application firewall filters per app (not per port or
interface), and the Tailscale interface is `utunN` with a variable N. The
recommended approach keeps the host off every network interface and lets
Tailscale forward tailnet traffic to it:

- Step 6 installs with `--bind 127.0.0.1`.
- Step 7 adds `tailscale serve` forwarding `{PORT}` on the tailnet address to
  `localhost:{PORT}`.

Trade-off to tell the user: the host accepts its bearer token (the local API
token in `~/.codync/token`) **only from loopback**, and phones never use it
(they use the end-to-end-encrypted channel with their pairing keys). Behind
`tailscale serve`, tailnet callers arrive from loopback, so a tailnet peer that
somehow obtained that token could use the local API. Treat the token as a full
credential, and restrict who can reach this machine's port with Tailscale ACLs
or grants. The pf-based alternative, which keeps loopback-only token use, is
in [references/macos-pf.md](references/macos-pf.md); it needs sudo and its own
boot-time enabling, so prefer `tailscale serve` unless the user objects.

## Step 5: Service environment (secrets and `CODYNC_CLOUD=off`)

The service manager does not read `~/.bashrc`, `~/.zshrc` or `~/.profile`.
Without this step, bots can't see the agents' tokens; the typical symptom is
the default "lead" bot failing its sign-in check at first start.

### Create `{ENV_FILE}` without printing values

Run in a shell where the chosen variables are already exported (open a new
login shell if needed). One `KEY=value` per line, no `export`, no quotes
needed:

```bash
umask 077
mkdir -p ~/.config/codync-host && chmod 700 ~/.config/codync-host
: > {ENV_FILE} && chmod 600 {ENV_FILE}
for name in {VAR_NAME} {VAR_NAME}; do        # the names from Step 1 Q3
  if [ -n "${!name+x}" ]; then
    printf '%s=%s\n' "$name" "${!name}" >> {ENV_FILE}
  else
    echo "not set in this shell: $name" >&2
  fi
done
cut -d= -f1 {ENV_FILE}                        # names only
```

(`${!name}` is bash indirection; under zsh use `${(P)name}`.) Values containing
newlines can't go in an env file; give that variable another mechanism.
Re-running replaces the file (`: >`), so it stays idempotent.

Tell the user the values now live in **two places** (shell rc and
`{ENV_FILE}`): rotating a token means updating both and restarting the service.

### Linux: systemd drop-ins (before the install)

`codync-host install` rewrites the base unit file every time, so never edit it.
Drop-ins in `codync-host.service.d/` survive. Create them now, so the very
first start already has the tokens and the cloud relay off:

```bash
dropins=~/.config/systemd/user/codync-host.service.d
mkdir -p "$dropins"
printf '[Service]\nEnvironmentFile=%%h/.config/codync-host/{ENV_NAME}.env\n' > "$dropins/{ENV_NAME}.conf"
printf '[Service]\nEnvironment=CODYNC_CLOUD=off\n' > "$dropins/cloud-off.conf"
cat "$dropins"/*.conf
```

(`%%h` prints `%h`, systemd's home-directory specifier.) Keep one concern per
drop-in; non-secret settings use `Environment=` lines.

### macOS: launchd

`codync-host install` writes the LaunchAgent plist from scratch with only
`PATH` and `CODYNC_HOME` in `EnvironmentVariables`, so variables must be added
**after** Step 6 and **re-applied after every later `codync-host install`**.
Automatic updates (Step 8) only swap the binary and restart the job; they keep
the plist. The commands are in Step 7.

## Step 6: Install the background service

```bash
# Linux
codync-host install --port {PORT} --bind 0.0.0.0
sudo loginctl enable-linger "$USER"          # run at boot without a login

# macOS
codync-host install --port {PORT} --bind 127.0.0.1

codync-host status                           # installed: yes, running, port, bind
```

`install` also captures the current shell's PATH into the service. Re-run it
(Linux: drop-ins are kept; macOS: then repeat Step 7) after changing PATH or
moving the binary.

## Step 7: Cloud relay off, then (macOS) env and `tailscale serve`

On first start the host registers with the Codync cloud relay
(`api.codync.dev`) without asking. That's a path to the machine from outside
the tailnet. Turn it off, and keep it off:

```bash
codync-host cloud --disable
codync-host cloud                 # must show enabled: false
codync-host analytics off         # only if the user chose it in Step 1
```

`CODYNC_CLOUD=off` in the service environment overrides the saved switch, so
it stays off even if the switch is flipped later. Linux already has it from
Step 5. On macOS, add it now with the other variables:

```bash
# macOS only. Re-run this block after every `codync-host install`.
plist=~/Library/LaunchAgents/com.pokai.codync.host.plist
plutil -replace EnvironmentVariables.CODYNC_CLOUD -string off "$plist"
while IFS= read -r line; do
  [ -n "$line" ] || continue
  plutil -replace "EnvironmentVariables.${line%%=*}" -string "${line#*=}" "$plist"
done < {ENV_FILE}
chmod 600 "$plist"
plutil -lint "$plist"
plutil -extract EnvironmentVariables xml1 -o - "$plist" | grep '<key>'   # names only
```

The values are now also in the plist (kept `0600`). While `plutil` runs, each
value is briefly visible in that process's arguments to the same machine's
process list; on a shared Mac, discuss this with the user first.

Restart so the new environment applies and connections opened before the
change are dropped:

```bash
# Linux
systemctl --user daemon-reload && systemctl --user restart codync-host
# macOS
launchctl bootout "gui/$(id -u)/com.pokai.codync.host"
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.pokai.codync.host.plist
```

macOS: publish the loopback port on the tailnet (it persists across reboots):

```bash
tailscale serve --bg --tcp {PORT} tcp://localhost:{PORT}
tailscale serve status
```

Check `tailscale serve --help` first: flag spelling has changed between
Tailscale versions. On the Mac App Store build, the CLI may need to be enabled
in Tailscale's settings.

Normal outbound traffic afterwards: `registry.modelcontextprotocol.io` (bot
marketplace), GitHub (update checks), and occasional `api.codync.dev` calls.
None of it opens inbound access.

## Step 8: Automatic updates

```bash
codync-host update --auto on
codync-host update --status        # "Automatic updates: on"
```

The built-in updater downloads signed releases, waits until no bot is busy,
swaps the binary, restarts the service and checks it came back healthy (rolling
back if not). Re-running the Step 3 installer also upgrades and restarts.

## Step 9: Verify

```bash
codync-host status                 # running, port {PORT}, bind as chosen
codync-host cloud                  # enabled: false
codync-host update --status        # automatic updates on
```

Names (never values) the running service sees:

```bash
# Linux
tr '\0' '\n' < "/proc/$(systemctl --user show -p MainPID --value codync-host)/environ" | cut -d= -f1 | sort
# macOS
plutil -extract EnvironmentVariables xml1 -o - ~/Library/LaunchAgents/com.pokai.codync.host.plist | grep '<key>'
```

Reachability, which **the user** must test from other machines (a test from
this machine never crosses the inbound firewall path):

- From a tailnet device: `nc -vz {TAILNET_HOSTNAME} {PORT}` connects.
- From a device on the same LAN but **off** the tailnet (or the internet):
  `nc -vz {LAN_OR_PUBLIC_IP} {PORT}` must time out or be refused.

## Step 10: Tell the user about side effects

- **Claude Code status line:** `codync-host install` sets `statusLine` in
  `~/.claude/settings.json` to `codync-host statusline`, which forwards Claude
  usage limits to the host. An existing status line is kept and wrapped
  (after `statusline --command=`), and `codync-host uninstall` restores it.
  Offer to revert it now if they don't want it.
- **Data:** `~/.codync` (or `CODYNC_HOME`) holds the computer's identity key,
  the local API token, bots and SQLite transcripts. If the home directory is a
  git repo or is backed up, exclude it.
- **Permissions:** bots run as the service user (Step 1 Q1), with everything
  that account can do.

## Step 11: Pair devices

```bash
codync-host pair                   # QR code for the phone app
codync-host access                 # pending requests; approve with: codync-host access approve <code>
codync-host devices                # list; revoke from here
```

The pairing link advertises the machine's Tailscale addresses (MagicDNS name
and `100.x` address) first, then LAN addresses, which the firewall blocks.

## Maintenance

- **Rotate a token:** update the shell rc and `{ENV_FILE}`; macOS: re-run the
  Step 7 plist block; then restart (Step 7).
- **After `codync-host install`** (PATH change, moved binary): Linux needs
  nothing more; macOS needs the Step 7 plist block and a restart.
- **Uninstall:** `codync-host uninstall` (removes the service and restores the
  status line; keeps data), then remove the firewall rule
  (`sudo ufw delete allow in on {TAILSCALE_INTERFACE} to any port {PORT} proto tcp`)
  or the serve config (`tailscale serve --tcp {PORT} off`), delete the drop-ins
  and `{ENV_FILE}`, the binaries in `~/.local/bin`, and `~/.codync` if the user
  wants the data gone.

## Reporting problems with this skill

If you find a bug or stale instruction while using this skill:

- If HiveMake is connected and `byteforge-skills-maintainer-agent` is available,
  file a ticket with that agent. Use `discover_agents` to find its project ID.
- Otherwise, open an issue at
  [GitHub Issues](https://github.com/jmazzahacks/byteforge-claude-skills/issues).
  If you cannot submit a report, give the human the details and this link.

Include the skill name, plugin version if known, the instruction followed,
expected and actual results, relevant errors/runtime versions, and any fix or
workaround that worked. Omit credentials and private data.

Address the user's immediate problem first; report the skill defect afterward.
