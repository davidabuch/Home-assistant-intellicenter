#!/usr/bin/env python3
"""Upload approved backyard JPEG to this feature branch using authenticated gh CLI.

Usage:
  python3 standalone/tools/upload_backyard_scene.py /path/to/pool-spa-backyard-final.jpg
Requires: gh auth login (never paste a token into chat).
"""
import base64
import json
from pathlib import Path
import subprocess
import sys

BRANCH = "feature/pool-spa-liquid-glass-animated-scene"
REPO = "davidabuch/Home-assistant-intellicenter"
DEST = "standalone/web/backyard-final.jpg"

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 standalone/tools/upload_backyard_scene.py /path/to/pool-spa-backyard-final.jpg")
    path = Path(sys.argv[1]).expanduser()
    data = path.read_bytes()
    if not data.startswith(bytes.fromhex("ffd8ff")):
        raise SystemExit("Not a JPEG file; upload aborted.")
    if len(data) > 4 * 1024 * 1024:
        raise SystemExit("Image exceeds 4 MB; optimize it first.")
    payload = {
        "message": "Add approved clean sunset backyard photographic scene",
        "branch": BRANCH,
        "content": base64.b64encode(data).decode("ascii"),
    }
    cmd = ["gh", "api", "-X", "PUT", f"repos/{REPO}/contents/{DEST}", "--input", "-"]
    result = subprocess.run(cmd, input=json.dumps(payload), text=True, capture_output=True, check=False)
    if result.returncode:
        raise SystemExit("GitHub upload failed: " + result.stderr.strip())
    output = json.loads(result.stdout)
    print("Uploaded:", output["content"]["path"])
    print("Commit:", output["commit"]["sha"])

if __name__ == "__main__":
    main()
