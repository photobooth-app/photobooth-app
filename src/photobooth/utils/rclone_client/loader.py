import hashlib
import io
import os
import pathlib
import platform
import sys
import zipfile

import niquests as requests

RCLONE_VERSION = os.environ.get("RCLONE_CLIENT_RCLONE_VERSION", "1.72.1")
RCLONE_BASE_URL = "https://downloads.rclone.org"

ARCH_MAP = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
}

SYS_MAP = {
    "windows": "windows",
    "linux": "linux",
    "darwin": "osx",
}


def rclone_install_dir() -> pathlib.Path:
    fpath = pathlib.Path.home() / ".cache" / "photobooth-app" / "rclone"
    fpath.mkdir(parents=True, exist_ok=True)

    return fpath


def downloaded_rclone(force_download: bool = False) -> pathlib.Path:
    try:
        system = SYS_MAP[platform.system().lower()]
        arch = ARCH_MAP[platform.machine().lower()]
    except KeyError:
        raise OSError(f"{platform.system().lower()}-{platform.machine().lower()} is not supported.") from None

    target_dir = rclone_install_dir()
    filename = f"rclone-v{RCLONE_VERSION}-{system}-{arch}.zip"
    unzip_folder = f"rclone-v{RCLONE_VERSION}-{system}-{arch}"

    bin_name = "rclone.exe" if system == "windows" else "rclone"
    bin_path = target_dir / unzip_folder / bin_name

    if bin_path.exists() and not force_download:
        return bin_path

    base_url = f"{RCLONE_BASE_URL}/v{RCLONE_VERSION}"
    url = f"{base_url}/{filename}"
    sums_url = f"{base_url}/SHA256SUMS"

    print(f"Downloading rclone from {url}", file=sys.stderr)
    req_session = requests.Session(disable_http3=True)  # niquests supports http3 while the server seems it does not despite advertising so
    resp = req_session.get(url)
    resp.raise_for_status()
    assert resp.content
    zip_bytes = resp.content

    print("verify sha265 hash")
    try:
        hash_valid = None
        resp = req_session.get(sums_url)
        resp.raise_for_status()
        assert resp.text
        sums_text = resp.text

        for line in sums_text.splitlines():
            parts = line.strip().split()
            if len(parts) == 2 and parts[1] == filename:
                hash_valid = parts[0]
                break

        if not hash_valid:
            raise RuntimeError(f"{filename} not found in SHA256SUMS")

        hash = hashlib.sha256(zip_bytes).hexdigest()
        if hash != hash_valid.lower():
            raise RuntimeError(f"rclone checksum mismatch: expected {hash_valid}, got {hash}")

    except Exception as e:
        raise RuntimeError(f"Failed to verify rclone checksum: {e}") from e

    print(f"extracting rclone from downloaded zip to {target_dir}")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extractall(target_dir)

    assert bin_path.is_file()

    if system != "windows":
        bin_path.chmod(0o755)

    return bin_path


def resolve_rclone(allow_fallback_to_system_rclone: bool = False, force_download: bool = False) -> pathlib.Path:
    from shutil import which

    # 1. downloaded-install
    try:
        bin_path = downloaded_rclone(force_download=force_download)
        return bin_path
    except Exception as exc:
        print(exc)

    # 2. fallback to local install
    if allow_fallback_to_system_rclone:
        bin_path = which("rclone")
        if bin_path:
            return pathlib.Path(bin_path)

    raise RuntimeError("rclone not found.")


if __name__ == "__main__":
    import time

    tms = time.monotonic()
    print(resolve_rclone(allow_fallback_to_system_rclone=False, force_download=False))
    print((time.monotonic() - tms) * 1000)
