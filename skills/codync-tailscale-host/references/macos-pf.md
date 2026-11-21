# macOS alternative: bind 0.0.0.0 and filter with pf

Use this only if the user rejects the default macOS approach (`--bind 127.0.0.1`
plus `tailscale serve`). The upside: tailnet peers reach the host directly, so
they don't appear as loopback, and the local API bearer token stays usable only
from the Mac itself. The downside: it needs sudo, edits system pf
configuration, and pf has to be enabled at every boot.

**Status: not exercised.** These steps follow standard macOS pf usage and have
not been tested with Codync. Test them on the Mac, with the user present,
before relying on them.

## Why filter by source address, not interface

The Tailscale interface on macOS is `utunN`, and N changes between boots and
VPN clients. Tailscale peers always come from `100.64.0.0/10` (IPv4) and
`fd7a:115c:a1e0::/48` (IPv6). A spoofed source on the LAN can't finish a TCP
handshake, because the reply is routed into the tailnet.

## Anchor

`/etc/pf.anchors/codync-host` (replace `{PORT}`):

```
tailnet4 = "100.64.0.0/10"
tailnet6 = "fd7a:115c:a1e0::/48"
pass in quick proto tcp from $tailnet4 to any port {PORT}
pass in quick proto tcp from $tailnet6 to any port {PORT}
pass in quick on lo0 proto tcp to any port {PORT}
block drop in quick proto tcp to any port {PORT}
```

Load it from `/etc/pf.conf` by appending these two lines after the existing
`anchor "com.apple/*"` lines, leaving Apple's lines untouched:

```
anchor "codync-host"
load anchor "codync-host" from "/etc/pf.anchors/codync-host"
```

Check the syntax, load the rules and enable pf:

```bash
sudo pfctl -nf /etc/pf.conf     # parse only
sudo pfctl -f /etc/pf.conf
sudo pfctl -E
sudo pfctl -a codync-host -sr   # show the anchor's rules
```

## Surviving reboots

macOS loads `/etc/pf.conf` at boot but doesn't necessarily *enable* pf. Add a
LaunchDaemon (`/Library/LaunchDaemons/{reverse-dns}.pf-enable.plist`, owned by
root, mode 0644) that runs `/sbin/pfctl -E -f /etc/pf.conf` with `RunAtLoad`.
Then check after a reboot with `sudo pfctl -s info | head -1` (`Status:
Enabled`).

macOS updates can reset `/etc/pf.conf`. Recheck the anchor lines after every
major OS update.

## With this approach

- In Step 6, install with `--bind 0.0.0.0`.
- Skip `tailscale serve` in Step 7.
- Verify from a LAN device that is off the tailnet, and from the internet if
  the Mac is exposed there: the port must not connect.
