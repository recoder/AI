"""Reconcile only the declared, pinned YuE2 artifacts."""
import argparse
import hashlib
from pathlib import Path
import struct
import json
import os
import time
import re
import uuid
import yaml


def download_http(declaration, artifact, destination):
    """Bounded ranges avoid a stalled multi-gigabyte response; partial bytes survive retries."""
    import requests
    from filelock import FileLock
    from huggingface_hub import hf_hub_url
    from huggingface_hub.utils import build_hf_headers
    path = destination / artifact["name"]
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + "." + declaration["revision"] + ".partial")
    url = hf_hub_url(declaration["repo"], artifact["name"], revision=declaration["revision"])
    with FileLock(str(partial) + ".lock", timeout=30), requests.Session() as session:
        # Reuse the provider's interrupted partial only when its name identifies the declared hash.
        if not partial.exists() and artifact.get("sha256"):
            candidates = list((destination / ".cache/huggingface/download").glob("*." + artifact["sha256"] + ".incomplete"))
            if len(candidates) == 1:
                candidates[0].replace(partial)
        if partial.exists() and partial.stat().st_size > artifact["size"]:
            raise RuntimeError(f"Oversized partial; preserve/resolve explicitly: {partial}")
        retries = 0
        while not partial.exists() or partial.stat().st_size < artifact["size"]:
            start = partial.stat().st_size if partial.exists() else 0
            end = min(start + declaration.get("chunk_bytes", 64 * 2**20), artifact["size"]) - 1
            headers = build_hf_headers()
            headers.update({"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"})
            try:
                with session.get(url, headers=headers, stream=True, timeout=(10, 30)) as response:
                    expected = f"bytes {start}-{end}/{artifact['size']}"
                    full_response = response.status_code == 200 and start == 0 and end == artifact["size"] - 1
                    if not full_response and (response.status_code != 206 or response.headers.get("Content-Range") != expected):
                        raise RuntimeError(f"Unexpected range response ({response.status_code}); partial preserved")
                    began = time.monotonic()
                    written = start
                    with partial.open("ab") as stream:
                        for chunk in response.iter_content(128 * 1024):
                            if written + len(chunk) > end + 1:
                                raise RuntimeError("Range response exceeds requested length")
                            stream.write(chunk)
                            written += len(chunk)
                            if time.monotonic() - began > 180:
                                raise requests.Timeout("Range transfer exceeded 180 seconds")
                    if written != end + 1:
                        raise requests.ConnectionError("Incomplete range response")
                retries = 0
                print(f"  {artifact['name']}: {written / artifact['size']:.1%}", flush=True)
            except requests.RequestException as error:
                retries += 1
                if retries > 3:
                    # Request exceptions can contain signed URLs/headers; do not print them.
                    raise RuntimeError("HTTP download failed after retries; partial retained. Retry just models yue") from None
                print(f"  Retrying HTTP transfer ({type(error).__name__}, {retries}/3)", flush=True)
        if not check(partial, artifact):
            quarantine = partial.with_name(partial.name + ".invalid-" + uuid.uuid4().hex[:8])
            partial.replace(quarantine)
            raise RuntimeError(f"Downloaded bytes failed verification; retained at {quarantine}. Retry just models yue")
        partial.replace(path)


def check(path, artifact):
    if not path.is_file() or path.stat().st_size != artifact["size"]:
        return False
    if artifact.get("sha256"):
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != artifact["sha256"]:
            return False
    if artifact["name"].endswith(".safetensors"):
        try:
            with path.open("rb") as stream:
                size = struct.unpack("<Q", stream.read(8))[0]
                if not 0 < size < min(path.stat().st_size, 100_000_000):
                    return False
                json.loads(stream.read(size))
        except (ValueError, struct.error):
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    declaration = yaml.safe_load(args.manifest.read_text(encoding="utf-8-sig"))["models"]["yue"]
    if declaration.get("source") != "huggingface" or not re.fullmatch(r"[a-f0-9]{40}", declaration.get("revision", "")):
        raise ValueError("Models require Hugging Face and an exact source revision")
    if type(declaration.get("chunk_bytes", 64 * 2**20)) is not int or not 1024 <= declaration.get("chunk_bytes", 64 * 2**20) <= 256 * 2**20:
        raise ValueError("chunk_bytes must be an integer between 1 KiB and 256 MiB")
    missing = []
    for artifact in declaration["files"]:
        path = (args.destination / artifact["name"]).resolve()
        if not path.is_relative_to(args.destination.resolve()):
            raise ValueError("Model artifact escapes destination")
        if not check(path, artifact):
            missing.append(artifact)
    if missing and args.check:
        parser.exit(1, "Missing/invalid YuE2 artifacts: " + ", ".join(a["name"] for a in missing) + ". Repair: just models yue\n")
    if missing:
        if declaration.get("download_transport") == "http":
            # HTTP streams progress to the partial file rather than buffering Xet reconstruction.
            os.environ["HF_HUB_DISABLE_XET"] = "1"
        from huggingface_hub import hf_hub_download
        args.destination.mkdir(parents=True, exist_ok=True)
        for artifact in missing:
            path = args.destination / artifact["name"]
            # A complete but corrupt artifact must not be trusted by HF's download metadata.
            force = path.is_file() and path.stat().st_size == artifact["size"]
            print(f"Downloading {artifact['name']} ({artifact['size'] / 2**30:.2f} GiB)", flush=True)
            if declaration.get("download_transport") == "http":
                download_http(declaration, artifact, args.destination)
            else:
                hf_hub_download(repo_id=declaration["repo"], revision=declaration["revision"], filename=artifact["name"],
                                local_dir=args.destination, force_download=force)
            if not check(path, artifact):
                raise RuntimeError(f"Artifact verification failed: {path}. Retry just models yue")
    print("OK YuE2 models: exact sizes, declared SHA-256 hashes and safetensors headers")


if __name__ == "__main__":
    main()
