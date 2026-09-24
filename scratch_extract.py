import re

with open("inspect_labelbox.py", "r", encoding="utf-8") as f:
    text = f.read()

match = re.search(r'inspection_js = """(.*?)"""', text, re.DOTALL)
if match:
    js = match.group(1).strip()
    print("Found JS, length:", len(js))
    with open("output/test_syntax.js", "w", encoding="utf-8") as out:
        out.write(js)
    print("Written to output/test_syntax.js")
else:
    print("Not found!")
