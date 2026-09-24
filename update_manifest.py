import os
import json
import hashlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
manifest_path = os.path.join(BASE_DIR, "system_manifest.json")
checksums_path = os.path.join(BASE_DIR, "SYSTEM_CHECKSUMS.sha256")

if os.path.exists(manifest_path):
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
else:
    manifest = {}

lines = []
for rel_path in sorted(manifest.keys()):
    full_path = os.path.join(BASE_DIR, rel_path)
    if os.path.exists(full_path):
        with open(full_path, "rb") as f:
            data = f.read()
            h = hashlib.sha256(data).hexdigest()
            manifest[rel_path] = {
                "sha256": h,
                "size_bytes": len(data)
            }
            lines.append(f"{h}  {rel_path.replace(chr(92), '/')}")

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

with open(checksums_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Updated {len(manifest)} manifest entries and checksums successfully.")
