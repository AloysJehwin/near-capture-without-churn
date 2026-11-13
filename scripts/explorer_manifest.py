#!/usr/bin/env python3
"""Write data/explorer/MANIFEST.json for the stored samples of NEAR's swap records.

Run it after scripts/explorer_sample.py has written or changed a sample file.
It records the size and SHA-256 of each sample file named in
config/analysis.json. The rebuild refuses to use a sample file that does not
match this record. No network, no key.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    spec = json.loads((ROOT / "config" / "analysis.json").read_text(encoding="utf-8"))["partners"]
    entries = []
    for name in spec["sample_files"]:
        path = ROOT / name
        if not path.exists():
            print(f"skipped {name}: not there")
            continue
        raw = path.read_bytes()
        sample = json.loads(raw)
        entries.append({
            "file": path.name,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "blocks": len(sample["blocks"]),
            "blocks_failed": len(sample.get("blocks_failed", [])),
            "sampled_from_utc": sample.get("sampled_from_utc"),
            "sampled_to_utc": sample.get("sampled_to_utc"),
        })
        print(f"recorded {name}: {len(sample['blocks'])} blocks")
    if not entries:
        print("No sample file found. Nothing written.")
        return 1
    out = ROOT / "data" / "explorer" / "MANIFEST.json"
    out.write_text(json.dumps({"source": spec["source"], "files": entries}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
