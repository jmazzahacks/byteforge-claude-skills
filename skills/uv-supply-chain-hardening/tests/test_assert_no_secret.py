"""Run with: python3 -m unittest discover -s skills/uv-supply-chain-hardening/tests."""

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "assert_no_secret.py"
spec = importlib.util.spec_from_file_location("scanner", SCRIPT)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)
TOKEN = "fixture-token.[literal]*+?123456789"


def tar_bytes(files, mode="w"):
    target = io.BytesIO()
    with tarfile.open(fileobj=target, mode=mode) as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return target.getvalue()


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def run_scan(self, *args, token=TOKEN, code=0):
        env = os.environ.copy()
        if token is None:
            env.pop("FIXTURE_SECRET", None)
        else:
            env["FIXTURE_SECRET"] = token
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--secret-env", "FIXTURE_SECRET", *map(str, args)],
            env=env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        if token:
            self.assertNotIn(token, result.stdout + result.stderr)
        return result

    def artifact(self, contents, name="artifact"):
        path = self.root / name
        path.write_bytes(contents)
        return path

    def image(self, layer_files, *, config=b"{}", compressed=False):
        files = {"config.json": config}
        layers = []
        for index, contents in enumerate(layer_files):
            name = f"{index}/layer.tar"
            files[name] = tar_bytes(contents, "w:gz" if compressed else "w")
            layers.append(name)
        files["manifest.json"] = json.dumps([{"Config": "config.json", "Layers": layers}]).encode()
        return self.artifact(tar_bytes(files), "image.tar")

    def test_secret_name_in_history_is_not_a_leak(self):
        self.run_scan(self.artifact(b"RUN --mount=type=secret,id=cr_pat CR_PAT=$(cat /run/secrets/cr_pat)"))

    def test_literal_value_with_regex_metacharacters_is_a_leak(self):
        self.run_scan(self.artifact(TOKEN.encode()), code=1)

    def test_directory_finds_package_metadata_leak(self):
        self.artifact(b"Requires-Dist: git+https://" + TOKEN.encode() + b"@example.invalid/lib", "METADATA")
        self.run_scan(self.root, code=1)

    def test_filesystem_filename_leak(self):
        self.artifact(b"safe", TOKEN)
        self.run_scan(self.root, code=1)

    def test_filesystem_link_target_leak(self):
        (self.root / "link").symlink_to("missing-" + TOKEN)
        self.run_scan(self.root, code=1)

    def test_json_escaped_value_leak(self):
        token = 'fixture-"quoted"-\u2603-token'
        contents = json.dumps([{"Config": {"Env": ["PAT=" + token]}}]).encode()
        self.assertNotIn(token.encode(), contents)
        self.run_scan("--json", self.artifact(contents), token=token, code=1)

    def test_malformed_json_fails_closed(self):
        self.run_scan("--json", self.artifact(b"not json"), code=2)

    def test_json_secret_name_is_not_a_value_leak(self):
        self.run_scan("--json", self.artifact(b'{"CR_PAT": "not-the-token"}'))

    def test_binary_and_chunk_boundary(self):
        data = b"\0" * (1024 * 1024 - 3) + TOKEN.encode() + b"\0"
        self.run_scan(self.artifact(data), code=1)

    def test_missing_empty_and_multiline_secret_fail_closed(self):
        path = self.artifact(b"safe")
        for value in (None, "", "first\nsecond"):
            with self.subTest(value=value):
                self.run_scan(path, token=value, code=2)

    def test_missing_path_does_not_report_clean(self):
        self.run_scan(self.root / "missing", code=2)

    def test_read_error_does_not_report_clean(self):
        path = self.artifact(b"safe")
        argv = [str(SCRIPT), "--secret-env", "FIXTURE_SECRET", str(path)]
        with patch.dict(os.environ, {"FIXTURE_SECRET": TOKEN}), patch.object(sys, "argv", argv):
            with patch.object(Path, "open", side_effect=PermissionError(TOKEN)), patch("sys.stderr", new_callable=io.StringIO) as output:
                self.assertEqual(scanner.main(), 2)
                self.assertNotIn(TOKEN, output.getvalue())

    def test_secret_file_input_trims_file_newline(self):
        secret = self.artifact(TOKEN.encode() + b"\n", "secret")
        target = self.artifact(TOKEN.encode())
        result = subprocess.run([sys.executable, str(SCRIPT), "--secret-file", str(secret), str(target)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_clean_image(self):
        self.run_scan("--docker-archive", self.image([{"app/file": b"no secret"}]))

    def test_image_config_leak(self):
        self.run_scan("--docker-archive", self.image([], config=TOKEN.encode()), code=1)

    def test_image_escaped_config_leak(self):
        config = ('{"Env":["' + "".join(f"\\u{ord(char):04x}" for char in TOKEN) + '"]}').encode()
        self.assertNotIn(TOKEN.encode(), config)
        self.run_scan("--docker-archive", self.image([], config=config), code=1)

    def test_malformed_image_config_fails_closed(self):
        self.run_scan("--docker-archive", self.image([], config=b"broken json"), code=2)

    def test_compressed_layer_leak_survives_later_deletion(self):
        path = self.image([{"root/.gitconfig": TOKEN.encode()}, {"root/.wh..gitconfig": b""}], compressed=True)
        self.run_scan("--docker-archive", path, code=1)

    def test_layer_filename_leak(self):
        self.run_scan("--docker-archive", self.image([{TOKEN: b"safe"}]), code=1)

    def test_corrupt_archive_and_missing_layer_fail_closed(self):
        self.run_scan("--docker-archive", self.artifact(b"not a tar"), code=2)
        files = {"config.json": b"{}", "manifest.json": b'[{"Config":"config.json","Layers":["absent.tar"]}]'}
        self.run_scan("--docker-archive", self.artifact(tar_bytes(files)), code=2)

    def test_corrupt_compressed_layer_fails_closed(self):
        files = {"config.json": b"{}", "manifest.json": b'[{"Config":"config.json","Layers":["layer.tar"]}]', "layer.tar": b"not a layer"}
        self.run_scan("--docker-archive", self.artifact(tar_bytes(files)), code=2)

    def test_directory_scan_does_not_follow_symlinks(self):
        directory = self.root / "root"
        directory.mkdir()
        (directory / "cycle").symlink_to(directory, target_is_directory=True)
        self.run_scan(directory)


if __name__ == "__main__":
    unittest.main()
