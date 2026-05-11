# apply_patch.ps1
# Run from your project root: Set-ExecutionPolicy Bypass -Scope Process; .\apply_patch.ps1

$file = "timetable\scheduler.py"

if (-not (Test-Path $file)) {
    Write-Error "Could not find $file. Run this script from your project root."
    exit 1
}

Copy-Item $file "$file.bak"
Write-Host "Backup saved to $file.bak"

$content = Get-Content $file -Raw

# ── Change 1: add TermTrainerAssignment to imports ────────────────────────────
$old1 = 'from .models import (
    Cohort, Conflict, Constraint, CurriculumUnit,
    Period, Programme, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,
)'

$new1 = 'from .models import (
    Cohort, Conflict, Constraint, CurriculumUnit,
    Period, Programme, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,
    TermTrainerAssignment,
)'

if ($content.Contains($old1)) {
    $content = $content.Replace($old1, $new1)
    Write-Host "[OK] Change 1: TermTrainerAssignment added to imports"
} else {
    Write-Warning "Change 1 NOT applied - import block not matched"
}

# ── Change 2: insert term_assignments lookup after GenerationResult line ──────
$old2 = '        result = GenerationResult(term=self.term, total_required=total_required)

        # ── Step 3: schedule COMBINED sessions (shared classes) ───────────'

$new2 = '        result = GenerationResult(term=self.term, total_required=total_required)

        # ── Term-specific trainer override lookup ─────────────────────────
        # Key: (cohort_id_str, curriculum_unit_id_str) -> [Trainer]
        # When a TermTrainerAssignment exists for this cohort+unit+term,
        # only that trainer is offered to the Placer instead of the full pool.
        term_assignments: dict[tuple[str, str], list[Trainer]] = {}
        for tta in TermTrainerAssignment.objects.filter(
            term=self.term,
            trainer__is_active=True,
        ).select_related("trainer"):
            key = (str(tta.cohort_id), str(tta.curriculum_unit_id))
            term_assignments[key] = [tta.trainer]

        # ── Step 3: schedule COMBINED sessions (shared classes) ───────────'

if ($content.Contains($old2)) {
    $content = $content.Replace($old2, $new2)
    Write-Host "[OK] Change 2: term_assignments lookup inserted"
} else {
    Write-Warning "Change 2 NOT applied - anchor text not matched"
}

# ── Change 3: call site A (pre-check loop) ────────────────────────────────────
$old3 = '            for unit in unit_list:
                qualified = [t for t in unit.qualified_trainers.all() if t.is_active]
                if not qualified and not getattr(unit, "is_outsourced", False):
                    no_trainer_units.append((cohort, unit))
                    placed_keys.add(f"{cohort_id}_{unit.id}")   # prevent re-try
                else:
                    viable.append(unit)'

$new3 = '            for unit in unit_list:
                ta_key    = (cohort_id, str(unit.id))
                qualified = term_assignments.get(ta_key) or [
                    t for t in unit.qualified_trainers.all() if t.is_active
                ]
                if not qualified and not getattr(unit, "is_outsourced", False):
                    no_trainer_units.append((cohort, unit))
                    placed_keys.add(f"{cohort_id}_{unit.id}")
                else:
                    viable.append(unit)'

if ($content.Contains($old3)) {
    $content = $content.Replace($old3, $new3)
    Write-Host "[OK] Change 3: call site A (pre-check loop) patched"
} else {
    Write-Warning "Change 3 NOT applied - call site A not matched"
}

# ── Change 4: call site B (pass loop) ────────────────────────────────────────
$old4 = '                    qualified = [t for t in unit.qualified_trainers.all() if t.is_active]
                    pr        = placer.place(cohort, unit, qualified)'

$new4 = '                    ta_key    = (cohort_id, str(unit.id))
                    qualified = term_assignments.get(ta_key) or [
                        t for t in unit.qualified_trainers.all() if t.is_active
                    ]
                    pr = placer.place(cohort, unit, qualified)'

if ($content.Contains($old4)) {
    $content = $content.Replace($old4, $new4)
    Write-Host "[OK] Change 4: call site B (pass loop) patched"
} else {
    Write-Warning "Change 4 NOT applied - call site B not matched"
}

Set-Content $file $content -NoNewline
Write-Host ""
Write-Host "Done. Regenerate your timetable to verify."
