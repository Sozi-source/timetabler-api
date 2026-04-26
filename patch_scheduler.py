import sys

path = sys.argv[1]

with open(path, "r", encoding="utf-8-sig") as f:
    content = f.read()

content = content.replace("\r\n", "\n")
fixes = 0

old1 = "    def _trainer_day_ok(self, trainer: Trainer, day: str) -> bool:\n        days = trainer.get_available_days(trainer.institution)\n        return day in days"
new1 = "    def _trainer_day_ok(self, trainer: Trainer, day: str) -> bool:\n        try:\n            days = trainer.get_available_days(trainer.institution)\n            if not days:\n                return True\n            return day in days\n        except Exception:\n            return True"
if old1 in content:
    content = content.replace(old1, new1); fixes += 1; print("Fix 1 OK")
else:
    print("Fix 1 MISS")

old2 = '                    qualified = list(unit.qualified_trainers.filter(is_active=True))\n                    if not qualified:\n                        if pass_cfg["use_any_trainer"]:\n                            qualified = list(\n                                Trainer.objects.filter(\n                                    institution=self.institution, is_active=True\n                                )\n                            )\n                        else:\n                            still_unplaced.append(unit)\n                            continue'
new2 = "                    qualified = list(unit.qualified_trainers.filter(is_active=True))\n                    if not qualified:\n                        still_unplaced.append(unit)\n                        continue"
if old2 in content:
    content = content.replace(old2, new2); fixes += 1; print("Fix 2 OK")
else:
    print("Fix 2 MISS")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print(f"{fixes}/2 fixes applied")
