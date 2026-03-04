import sys

text = open(r"D:\nouva hub\nova_hub_v1_release\nova_hub\ui\hud_qml\qml\Main.qml", "r", encoding="utf-8").read()
lines = text.splitlines()

depth = 0
bracket_depth = 0
for i, line in enumerate(lines, 1):
    s = line.strip()
    if s.startswith("//"):
        continue
    in_str = False
    qc = None
    for ch in s:
        if in_str:
            if ch == qc:
                in_str = False
        else:
            if ch in ('"',):
                in_str = True
                qc = ch
            elif ch == "[":
                bracket_depth += 1
            elif ch == "]":
                bracket_depth -= 1
            elif ch == "{" and bracket_depth == 0:
                depth += 1
            elif ch == "}" and bracket_depth == 0:
                depth -= 1

print(f"Final depth: {depth}")
print(f"Final bracket depth: {bracket_depth}")

# Now find where the extra open brace is
depth = 0
bracket_depth = 0
last_opens = []
for i, line in enumerate(lines, 1):
    s = line.strip()
    if s.startswith("//"):
        continue
    in_str = False
    qc = None
    for ch in s:
        if in_str:
            if ch == qc:
                in_str = False
        else:
            if ch in ('"',):
                in_str = True
                qc = ch
            elif ch == "[":
                bracket_depth += 1
            elif ch == "]":
                bracket_depth -= 1
            elif ch == "{" and bracket_depth == 0:
                depth += 1
                last_opens.append((i, depth, s[:80]))
            elif ch == "}" and bracket_depth == 0:
                depth -= 1
                if last_opens and last_opens[-1][1] == depth + 1:
                    last_opens.pop()

print(f"\nUnmatched open braces:")
for li, d, txt in last_opens:
    print(f"  L{li}: depth={d} | {txt}")
