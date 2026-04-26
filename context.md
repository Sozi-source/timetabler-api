# Timetabler Project — Context Document
> **Purpose:** Paste this entire file at the start of every new Claude chat to restore full project context instantly.
> **Last updated:** 2026-04-26

---

## ⚠️ IMPORTANT INSTRUCTION FOR CLAUDE (READ FIRST)
You are continuing development of the Timetabler system. At the end of every chat session where changes are made, **update this context document** to reflect:
- Any new files created or modified (update the file structure and status table)
- Any bugs fixed and what caused them
- Any new decisions made about architecture or data models
- Progress on frontend, tests, or deployment
- Any new known issues discovered

Always ask the user to paste the updated context at the start of the next chat. The goal is seamless continuity across sessions, especially as frontend development begins.

---

## 1. Project Overview

Building a **constraint-based academic timetabling system** as a Django REST API backend. The system schedules cohorts of students into rooms with qualified trainers, respects hard/soft constraints, and handles conflict detection and resolution.

**Target institution type:** TVET colleges / polytechnics (e.g. Kenya). Multi-institution ready.

---

## 2. Tech Stack

| Layer       | Technology                                                    |
|-------------|---------------------------------------------------------------|
| Language    | Python 3.14 (Windows, path: C:\Users\sozi\AppData\Local\Programs\Python\Python314) |
| Framework   | Django 4.2+ with Django REST Framework                        |
| Database    | PostgreSQL — hosted on Render (see Section 13)                |
| Auth        | Session + Token authentication (DRF)                         |
| CORS        | django-cors-headers                                           |
| OS / Shell  | Windows 11, PowerShell                                        |
| Deployment  | Not yet decided                                               |

---

## 3. Project File Structure

```
C:\users\sozi\Desktop\2026-projects\Timetable\timetabler\
├── timetabler/
│   ├── settings.py                     # ✅ DONE
│   ├── urls.py                         # ✅ DONE
│   └── wsgi.py
├── timetable/
│   ├── models.py                       # ✅ DONE — see Section 4 for latest changes
│   ├── admin.py                        # ✅ DONE — CurriculumUnitTrainerInline added
│   ├── views.py                        # ✅ DONE — new endpoints added
│   ├── urls.py                         # ✅ DONE — new routes added
│   ├── scheduler.py                    # ✅ DONE
│   ├── signals.py                      # ✅ DONE
│   ├── migrations/
│   │   ├── 0001_initial.py             # ✅ DONE
│   │   └── 0002_add_curriculum_unit_trainer_through.py  # ✅ DONE
│   └── management/commands/seed_timetable.py
```

---

## 4. Data Model Summary

### Core Models — latest additions

```
CurriculumUnit
  ├── qualified_trainers  M2M → Trainer  (through=CurriculumUnitTrainer)
  └── is_outsourced       BooleanField(default=False)  ← NEW

CurriculumUnitTrainer  (through model)  ← NEW
  ├── curriculum_unit  FK → CurriculumUnit
  ├── trainer          FK → Trainer
  ├── trainer_type     CharField  INTERNAL | OUTSOURCED
  └── label            CharField (blank=True) — e.g. "HOD Physics dept"
```

### Key Design Decisions
1. **Template-first** — ScheduledUnit is a weekly recurring template.
2. **No Stage model** — `CurriculumUnit.term_number` replaces Stage.
3. **UUID PKs** everywhere.
4. **is_outsourced** on CurriculumUnit — marks units taught by external trainers with no specific trainer assigned.
5. **CurriculumUnitTrainer through model** — allows labelling each trainer assignment as INTERNAL or OUTSOURCED with an optional custom label.
6. **OccupancyGrid** — in-memory O(1) availability tracker.
7. **Multi-pass scheduler**: STRICT → RELAXED → EMERGENCY.

---

## 5. API Endpoint Map

All routes under `/api/` prefix.

```
GET  /api/curriculum/?programme=<id>&term_number=<n>
GET  /api/curriculum/<id>/                           ← NEW (unit detail)
PUT  /api/curriculum/<id>/                           ← NEW (update unit fields incl. is_outsourced)
GET  /api/curriculum/<id>/trainers/                  ← NEW (list assigned trainers)
POST /api/curriculum/<id>/trainers/                  ← NEW (assign trainer)
DEL  /api/curriculum/<id>/trainers/                  ← NEW (remove trainer, pass trainer_id in body)

... (all previous endpoints unchanged)
```

### Trainer assignment POST body:
```json
{ "trainer_id": "<uuid>", "trainer_type": "INTERNAL|OUTSOURCED", "label": "optional label" }
```

### Trainer assignment response:
```json
{ "id": "<uuid>", "name": "short_name", "trainer_type": "INTERNAL", "label": "" }
```

### Curriculum unit response now includes:
```json
{
  "is_outsourced": false,
  "qualified_trainers": [
    { "id": "<uuid>", "name": "short_name", "trainer_type": "INTERNAL", "label": "" }
  ]
}
```

---

## 6. Constraints

Supported rules: `PIN_DAY_PERIOD`, `PIN_DAY`, `PREFERRED_ROOM`, `AVOID_DAY`, `AVOID_PERIOD`, `BACK_TO_BACK`, `MAX_PER_DAY`

Constraint creation (simplified UI — unit + day + period only):
```json
POST /api/constraints/
{
  "name": "Anatomy — Monday morning",
  "scope": "UNIT",
  "rule": "PIN_DAY_PERIOD",
  "is_hard": true,
  "is_active": true,
  "curriculum_unit": "<uuid>",
  "parameters": { "day": "MON", "period_id": "<uuid>" }
}
```

---

## 7. Bugs Fixed (Session: 2026-04-26)

| Bug | Cause | Fix |
|-----|-------|-----|
| `qualified_trainers` M2M couldn't be altered | Django can't alter M2M to add through= in one step | Migration: RemoveField + AddField instead of AlterField |
| Admin error on `CurriculumUnitAdmin` | `filter_horizontal` and `fieldsets` can't include M2M with through model | Removed from fieldsets, added `CurriculumUnitTrainerInline` instead |
| `CurriculumUnitTrainer` NameError in views | Import not added to views.py | Added to models import line |
| `curriculum/` list route disappeared | URL regex replaced instead of appended | Re-added `path("curriculum/", views.CurriculumView.as_view())` |
| `is_outsourced` added to wrong model | Regex matched `Constraint` model instead of `CurriculumUnit` | Removed duplicate from Constraint model |

---

## 8. Current Status

| Component          | Status         | Notes |
|--------------------|---------------|-------|
| models.py          | ✅ Complete    | CurriculumUnitTrainer through model + is_outsourced added |
| admin.py           | ✅ Complete    | CurriculumUnitTrainerInline added |
| views.py           | ✅ Complete    | CurriculumUnitDetailView + CurriculumUnitTrainersView added |
| urls.py            | ✅ Complete    | curriculum/<id>/ and curriculum/<id>/trainers/ routes added |
| migrations         | ✅ Complete    | 0002_add_curriculum_unit_trainer_through applied |
| Frontend           | ✅ In progress | See frontend context |

---

## 9. Environment & Database

### Database (Render PostgreSQL)
- Host: dpg-d743sghr0fns73c1q1k0-a.oregon-postgres.render.com
- Name: tani_africa_db
- User: tani_africa_db_user

### PowerShell Tips
```powershell
# Patch files safely
(Get-Content $f -Raw) -replace 'old', 'new' | Set-Content $f -Encoding UTF8

# Append to file
(Get-Content $f -Raw) + $newContent | Set-Content $f -Encoding UTF8

# Check specific lines
Get-Content $f | Select-Object -Skip 108 -First 15
```

---

## 10. Known Issues / Watch Points

1. `views.py` uses `permission_classes = [IsAuthenticated]` globally — tighten per view later.
2. `scheduler.py` — qualified_trainers now uses through model; scheduler reads `.qualified_trainers.all()` which still works transparently.
3. Units marked `is_outsourced=True` have no trainer assigned — scheduler should handle gracefully (skip trainer assignment for outsourced units). **Not yet implemented in scheduler.**
4. Downloads folder unreliable on this machine — always use inline PowerShell patches instead.

---

*End of context document.*
*Paste this at the top of your next chat and say:*
**"Continue building the timetabler system — [your task]. Update the context file at the end of this session with all changes made."**