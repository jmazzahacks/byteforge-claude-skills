#!/usr/bin/env python3
"""Fail on literal secret bytes in files/directories or a Docker-save archive.

Exit 0: checked inputs have no match; 1: secret found; 2: scan incomplete.
Never print matching data, artifact names, or exception details. Directory scans
cover regular files without following symlinks. Docker-save mode also decompresses
and scans every referenced layer, including files deleted by later layers.
"""

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import tarfile


class SecretFound(Exception):
    pass


def scan_stream(stream, secret):
    tail = b""
    while chunk := stream.read(1024 * 1024):
        data = tail + chunk
        if secret in data:
            raise SecretFound
        tail = data[-(len(secret) - 1):] if len(secret) > 1 else b""


def scan_path(path, secret):
    if secret in os.fsencode(path.name):
        raise SecretFound
    mode = path.lstat().st_mode
    if stat.S_ISREG(mode):
        with path.open("rb") as stream:
            scan_stream(stream, secret)
    elif stat.S_ISDIR(mode):
        for child in path.iterdir():
            scan_path(child, secret)
    elif stat.S_ISLNK(mode):
        if secret in os.fsencode(os.readlink(path)):
            raise SecretFound
    else:
        raise ValueError("unsupported scan root")


def scan_json(value, secret):
    """Inspect decoded strings too: JSON escaping must not conceal a token."""
    if isinstance(value, str):
        if secret in value.encode():
            raise SecretFound
    elif isinstance(value, dict):
        for key, item in value.items():
            scan_json(key, secret)
            scan_json(item, secret)
    elif isinstance(value, list):
        for item in value:
            scan_json(item, secret)


def scan_docker_archive(path, secret):
    with tarfile.open(path, "r:*") as archive:
        manifest_file = archive.extractfile("manifest.json")
        if manifest_file is None:
            raise ValueError("missing manifest")
        with manifest_file:
            manifest = json.load(manifest_file)
        if not isinstance(manifest, list) or not manifest:
            raise ValueError("invalid manifest")
        # Inspect all outer regular files, including image configuration/history.
        # Tar member names can themselves contain a credential.
        for member in archive:
            if secret in member.name.encode() or secret in member.linkname.encode():
                raise SecretFound
            if member.isfile():
                with archive.extractfile(member) as stream:
                    scan_stream(stream, secret)
        for image in manifest:
            config = image["Config"]
            layers = image["Layers"]
            if not isinstance(config, str) or not isinstance(layers, list):
                raise ValueError("invalid manifest entry")
            if not archive.getmember(config).isfile():
                raise ValueError("missing configuration")
            with archive.extractfile(config) as stream:
                configuration = json.load(stream)
            if not isinstance(configuration, dict):
                raise ValueError("invalid image configuration")
            scan_json(configuration, secret)
            for layer in layers:
                if not isinstance(layer, str):
                    raise ValueError("invalid layer")
                with archive.extractfile(layer) as layer_stream:
                    with tarfile.open(fileobj=layer_stream, mode="r|*") as contents:
                        for member in contents:
                            if secret in member.name.encode() or secret in member.linkname.encode():
                                raise SecretFound
                            if member.isfile():
                                with contents.extractfile(member) as stream:
                                    scan_stream(stream, secret)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--secret-env", help="name of an environment variable")
    source.add_argument("--secret-file", type=Path, help="BuildKit secret file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--docker-archive", action="store_true", help="inputs are docker image save archives")
    mode.add_argument("--json", action="store_true", help="inputs are JSON; also scan decoded strings")
    parser.add_argument("paths", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        if args.secret_file:
            secret = args.secret_file.read_bytes().rstrip(b"\r\n")
        else:
            secret = os.environ[args.secret_env].encode()
        if not secret or b"\n" in secret or b"\r" in secret:
            raise ValueError("expected a nonempty single-line token")
        for path in args.paths:
            if args.docker_archive:
                scan_docker_archive(path, secret)
            elif args.json:
                scan_path(path, secret)
                with path.open("rb") as stream:
                    scan_json(json.load(stream), secret)
            else:
                scan_path(path, secret)
    except SecretFound:
        print("FAIL: secret value found in scanned artifacts", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: scan incomplete; check secret input, paths, permissions and archive format", file=sys.stderr)
        return 2
    print("PASS: no literal secret value found in scanned artifacts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
