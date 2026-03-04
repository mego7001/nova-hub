import re

text = open(r"D:\nouva hub\nova_hub_v1_release\nova_hub\ui\hud_qml\controller.py", "r", encoding="utf-8").read()
lines = text.splitlines()

# Find all self._xxx attributes used in the file
all_attrs = set()
for line in lines:
    for m in re.finditer(r"self\.(_[a-zA-Z_][a-zA-Z0-9_]*)", line):
        all_attrs.add(m.group(1))

# Find all self._xxx assignments in __init__
init_attrs = set()
in_init = False
init_indent = 0
for line in lines:
    stripped = line.strip()
    if "def __init__(" in line:
        in_init = True
        init_indent = len(line) - len(line.lstrip())
        continue
    if in_init:
        if stripped.startswith("def ") and not stripped.startswith("def __init__"):
            break
        for m in re.finditer(r"self\.(_[a-zA-Z_][a-zA-Z0-9_]*)\s*[=:]", line):
            init_attrs.add(m.group(1))

# Find missing attributes
missing = sorted(all_attrs - init_attrs)
print(f"Total attributes used: {len(all_attrs)}")
print(f"Total attributes in __init__: {len(init_attrs)}")
print(f"Missing from __init__: {len(missing)}")
print()

# For each missing, find the first usage line
for attr in missing:
    for i, line in enumerate(lines, 1):
        if f"self.{attr}" in line and not line.strip().startswith("#"):
            print(f"  {attr}: first seen L{i} | {line.strip()[:80]}")
            break
