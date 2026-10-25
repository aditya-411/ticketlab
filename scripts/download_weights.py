"""Restore the local tuned model and optionally the pinned base weights."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/weights_manifest.json"
RELEASE_ROOT = "https://github.com/aditya-411/ticketlab/releases/download/models-v1/"


def download_tuned():
    manifest = json.loads(MANIFEST.read_text())
    if not manifest.get("files"):
        raise RuntimeError("Release asset manifest is not populated yet")
    for item in manifest["files"]:
        destination = ROOT / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.stat().st_size == item["size"]:
            print(f"Already present: {item['path']}")
            continue
        temp = destination.with_name(destination.name + ".download")
        digest = hashlib.sha256()
        count = 0
        try:
            with temp.open("wb") as out:
                for part in item["parts"]:
                    url = RELEASE_ROOT + quote(part["asset"])
                    request = Request(url, headers={"User-Agent": "TicketLab weight downloader"})
                    with urlopen(request, timeout=60) as response:
                        while chunk := response.read(4 * 1024 * 1024):
                            out.write(chunk)
                            digest.update(chunk)
                            count += len(chunk)
            if count != item["size"] or digest.hexdigest() != item["sha256"]:
                raise RuntimeError(f"Size or SHA-256 mismatch: {item['path']}")
            os.replace(temp, destination)
            print(f"Restored: {item['path']}")
        finally:
            if temp.exists():
                temp.unlink()


def download_base():
    from huggingface_hub import snapshot_download

    selection = json.loads((ROOT / "config/MODEL_SELECTION.json").read_text())
    destination = ROOT / selection["base_path"]
    expected = {name: size for name, size in selection["base_file_sizes"].items()
                if name.endswith(".safetensors")}
    if all((destination / name).exists() and (destination / name).stat().st_size == size
           for name, size in expected.items()):
        print("Pinned base weights already present")
        return
    snapshot_download(repo_id=selection["base_repo"], revision=selection["base_revision"],
                      allow_patterns=list(expected), local_dir=destination)
    if not all((destination / name).exists() and (destination / name).stat().st_size == size
               for name, size in expected.items()):
        raise RuntimeError("Pinned base weights are incomplete")
    print("Restored pinned base weights")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["selected", "base", "all"], default="selected")
    choice = parser.parse_args().model
    if choice in ("selected", "all"):
        download_tuned()
    if choice in ("base", "all"):
        download_base()


if __name__ == "__main__":
    main()
