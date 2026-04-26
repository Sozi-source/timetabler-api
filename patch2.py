import sys

path = sys.argv[1]

with open(path, "r", encoding="utf-8-sig") as f:
    content = f.read()

content = content.replace("\r\n", "\n")

old = (
    "                    qualified = list(unit.qualified_trainers.filter(is_active=True))\n"
    "                    if not qualified:\n"
    "                        still_unplaced.append(unit)\n"
    "                        continue"
)
new = (
    "                    if getattr(unit, 'is_outsourced', False):\n"
    "                        continue\n"
    "                    qualified = list(unit.qualified_trainers.filter(is_active=True))\n"
    "                    if not qualified:\n"
    "                        still_unplaced.append(unit)\n"
    "                        continue"
)

if old in content:
    content = content.replace(old, new)
    print("Patch applied OK")
else:
    print("MISS - not found")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
