#!/usr/bin/env python3
"""Install a checksum-verified yt-dlp standalone binary inside this Skill."""

import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen

RELEASE_BASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download"


def asset_name(system: str, machine: str) -> str:
    system = system.lower()
    machine = machine.lower()
    if system == "darwin":
        return "yt-dlp_macos"
    if system.startswith("win"):
        return "yt-dlp_arm64.exe" if machine in ("arm64", "aarch64") else "yt-dlp.exe"
    if system == "linux":
        if machine in ("arm64", "aarch64"):
            return "yt-dlp_linux_aarch64"
        if machine in ("armv7l", "armv7"):
            return "yt-dlp_linux_armv7l"
        return "yt-dlp_linux"
    raise RuntimeError("unsupported platform: {} {}".format(system, machine))


def expected_checksum(checksums: str, asset: str) -> str:
    for line in checksums.splitlines():
        fields = line.strip().split()
        if len(fields) >= 2 and fields[-1].lstrip("*") == asset:
            digest = fields[0].lower()
            if len(digest) == 64 and all(character in "0123456789abcdef" for character in digest):
                return digest
    raise RuntimeError("release checksums did not list {}".format(asset))


def _fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "media-downloader-bootstrap/0.1"})
    with urlopen(request, timeout=120) as response:
        return response.read()


def install() -> Path:
    asset = asset_name(sys.platform, platform.machine())
    checksums = _fetch("{}/SHA2-256SUMS".format(RELEASE_BASE)).decode("utf-8")
    expected = expected_checksum(checksums, asset)
    payload = _fetch("{}/{}".format(RELEASE_BASE, asset))
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise RuntimeError("yt-dlp checksum mismatch")

    skill_root = Path(__file__).resolve().parents[1]
    tools_dir = skill_root / ".tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    destination = tools_dir / ("yt-dlp.exe" if asset.endswith(".exe") else "yt-dlp")
    temporary = destination.with_name(destination.name + ".part")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o755)
        os.replace(str(temporary), str(destination))
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def main() -> int:
    try:
        destination = install()
        completed = subprocess.run(
            [str(destination), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "installed binary did not run")
        print("Installed yt-dlp {} at {}".format(completed.stdout.strip(), destination))
        return 0
    except Exception as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
