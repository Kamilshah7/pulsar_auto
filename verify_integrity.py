import hashlib, json, os, sys

manifest_path = os.path.join(os.path.dirname(__file__), "system_manifest.json")
if not os.path.exists(manifest_path):
    print("ERROR: system_manifest.json not found!")
    sys.exit(1)

with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

all_ok = True
print("=" * 75)
print("SYSTEM INTEGRITY VERIFICATION")
print("=" * 75)

for rel_path, info in manifest.items():
    if not os.path.exists(rel_path):
        print(f"[MISSING]   {rel_path}")
        all_ok = False
        continue
    with open(rel_path, "rb") as f:
        actual_h = hashlib.sha256(f.read()).hexdigest()
    if actual_h == info["sha256"]:
        print(f"[OK]        {rel_path}")
    else:
        print(f"[MODIFIED] {rel_path}")
        print(f"   Expected: {info['sha256']}")
        print(f"   Actual:   {actual_h}")
        all_ok = False

print("=" * 75)
if all_ok:
    print("VERIFICATION PASSED: All files are untampered and match official checksums.")
else:
    print("WARNING: File tampering or modification detected!")
