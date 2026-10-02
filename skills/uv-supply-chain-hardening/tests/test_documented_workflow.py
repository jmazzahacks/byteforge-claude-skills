"""Execute the documented pre-push shell flow with a controlled Docker stand-in.

This checks shell control flow, not Docker/BuildKit behavior. No Docker daemon,
private repository, real token, or external network is used.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1]
TEXT = (SKILL / "SKILL.md").read_text()
VERIFY = re.search(r"```bash\n(.*?)\n```", TEXT.split("## Step 6:", 1)[1], re.S).group(1)
AUTH = re.search(r"```bash\n(with_private_git\(\).*?)\n```", TEXT, re.S).group(1)
TOKEN = "fixture-only.+[not-a-real-token]12345"
DOCKER = '''#!/usr/bin/env python3
import io, json, os, pathlib, sys, tarfile
args = sys.argv[1:]
mode = os.environ["FIXTURE_MODE"]
token = os.environ["CR_PAT"]
if args[0] == "build":
    print(token if mode == "build-leak" else "build complete")
    sys.exit(1 if mode == "build-failed" else 0)
if args[:2] == ["image", "inspect"]:
    if mode == "inspect-escaped-leak":
        # JSON escapes every ASCII character; the literal byte scan cannot match.
        print('{"Env":["' + ''.join(chr(92) + 'u%04x' % ord(char) for char in token) + '"]}')
    else:
        print(json.dumps({"Env": []}))
elif args[0] == "history":
    print(token if mode == "history-leak" else "RUN --mount=type=secret,id=cr_pat")
elif args[:2] == ["image", "save"]:
    if mode == "save-failed":
        sys.exit(1)
    target = pathlib.Path(args[args.index("--output") + 1])
    manifest = [{"Config": "config.json", "Layers": []}]
    with tarfile.open(target, "w") as archive:
        for name, content in {"manifest.json": json.dumps(manifest).encode(), "config.json": b"{}"}.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
else:
    sys.exit(99)
'''


class DocumentedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "dev_scripts").mkdir()
        shutil.copyfile(SKILL / "scripts" / "assert_no_secret.py", self.root / "dev_scripts" / "assert_no_secret.py")
        binary = self.root / "bin"
        binary.mkdir()
        docker = binary / "docker"
        docker.write_text(DOCKER)
        docker.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update(CR_PAT=TOKEN, PATH=str(binary) + os.pathsep + self.env["PATH"])

    def verify(self, mode, success):
        self.env["FIXTURE_MODE"] = mode
        result = subprocess.run(["bash", "-c", VERIFY + "\nprintf 'VERIFIED\\n'\n"], cwd=self.root, env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        self.assertEqual("VERIFIED" in result.stdout, success)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_clean_build_reaches_publish_boundary(self):
        self.verify("clean", True)

    def test_build_log_leak_blocks_publishing(self):
        self.verify("build-leak", False)

    def test_history_leak_blocks_publishing(self):
        self.verify("history-leak", False)

    def test_escaped_inspect_leak_blocks_publishing(self):
        self.verify("inspect-escaped-leak", False)

    def test_build_failure_blocks_publishing(self):
        self.verify("build-failed", False)

    def test_save_failure_blocks_publishing(self):
        self.verify("save-failed", False)

    def test_git_auth_is_process_scoped(self):
        global_config = self.root / "gitconfig"
        global_config.write_text("")
        env = {key: value for key, value in self.env.items() if not key.startswith("GIT_")}
        env.update(GIT_CONFIG_GLOBAL=str(global_config), GIT_CONFIG_NOSYSTEM="1")
        result = subprocess.run(["bash", "-c", AUTH + '\nwith_private_git git ls-remote --get-url https://github.com/example/repo.git\ngit ls-remote --get-url https://github.com/example/repo.git\n'], cwd=self.root, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), [f"https://{TOKEN}@github.com/example/repo.git", "https://github.com/example/repo.git"])
        self.assertEqual(global_config.read_text(), "")
        self.assertFalse((self.root / ".gitconfig").exists())


if __name__ == "__main__":
    unittest.main()
