import sys

path = sys.argv[1]

with open(path, "r", encoding="utf-8-sig") as f:
    content = f.read()

content = content.replace("\r\n", "\n")

old = '''    def summary(self) -> dict:
        rate = (
            round(self.placed / self.total_required * 100, 1)
            if self.total_required else 0
        )
        return {
            "term":               str(self.term),
            "placed":             self.placed,
            "total_required":     self.total_required,
            "completion_rate":    rate,
            "combined_placed":    self.combined_placed,
            "unresolved_count":   len(self.unresolved),
            "emergency_count":    len(self.emergency_placements),
            "unresolved":         self.unresolved,
            "emergency_placements": self.emergency_placements,
        }'''

new = '''    def summary(self) -> dict:
        from timetable.models import ScheduledUnit, Cohort, CurriculumUnit
        # Count from DB for accuracy
        placed = ScheduledUnit.objects.filter(
            term=self.term, status="DRAFT"
        ).values("cohort", "curriculum_unit").distinct().count()

        total = 0
        for c in Cohort.objects.filter(is_active=True):
            total += CurriculumUnit.objects.filter(
                programme=c.programme,
                term_number=c.current_term,
                is_active=True,
                is_outsourced=False,
            ).count()

        rate = round(placed / total * 100, 1) if total else 0
        return {
            "term":               str(self.term),
            "placed":             placed,
            "total_required":     total,
            "completion_rate":    rate,
            "combined_placed":    self.combined_placed,
            "unresolved_count":   len(self.unresolved),
            "emergency_count":    len(self.emergency_placements),
            "unresolved":         self.unresolved,
            "emergency_placements": self.emergency_placements,
        }'''

if old in content:
    content = content.replace(old, new)
    print("Summary fix OK")
else:
    print("MISS")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
