# Timetabler Project — Context Document
> **Purpose:** Paste this entire file at the start of every new Claude chat to restore full project context instantly.
> **Last updated:** 2026-05-01

---

## ⚠️ IMPORTANT INSTRUCTION FOR CLAUDE (READ FIRST)
You are continuing development of the Timetabler system. At the end of every chat session where changes are made, **update this context document** to reflect:
- Any new files created or modified
- Any bugs fixed and what caused them
- Any new decisions made about architecture or data models
- Progress on frontend, tests, or deployment
- Any new known issues discovered

Always ask the user to paste the updated context at the start of the next chat.

---

## 1. Project Overview

Building a **constraint-based academic timetabling system** as a Django REST API backend. The system schedules cohorts of students into rooms with qualified trainers, respects hard/soft constraints, and handles conflict detection and resolution.

**Target institution type:** TVET colleges / polytechnics (e.g. Kenya). Multi-institution ready.

---

## 2. Tech Stack

| Layer       | Technology |
|-------------|------------|
| Language    | Python 3.14 (Windows, C:\Users\sozi\AppData\Local\Programs\Python\Python314) |
| Framework   | Django 6.0.4 with Django REST Framework |
| Database    | PostgreSQL — hosted on Render (free tier — suspends after inactivity) |
| Auth        | Token authentication (DRF) |
| CORS        | django-cors-headers |
| OS / Shell  | Windows 11, PowerShell |
| AI          | Groq API (Llama 3.3 70B) via proxy view |

---

## 3. Project File Structure

```
C:\users\sozi\Desktop\2026-projects\Timetable\timetabler\
├── timetabler/
│   ├── settings.py                     ✅ DONE — DB keepalives + retry middleware added
│   ├── urls.py                         ✅ DONE
│   ├── wsgi.py
│   └── db_retry_middleware.py          ✅ NEW — auto-retry DB connection on timeout
├── timetable/
│   ├── models.py                       ✅ DONE
│   ├── admin.py                        ✅ DONE
│   ├── views.py                        ✅ DONE
│   ├── urls.py                         ✅ DONE
│   ├── scheduler.py                    ✅ DONE
│   ├── ai_views.py                     ✅ DONE — FIXED institution lookup
│   ├── signals.py                      ✅ DONE
│   └── migrations/
│       ├── 0001_initial.py             ✅ DONE
│       └── 0002_add_curriculum_unit_trainer_through.py ✅ DONE
```

---

## 4. Data Model Summary

```
Institution
  └── departments → Department → programmes → Programme
                                               └── curriculum_units → CurriculumUnit
                                                     ├── qualified_trainers M2M → Trainer
                                                     │     (through=CurriculumUnitTrainer)
                                                     └── is_outsourced: bool

CurriculumUnitTrainer (through model)
  ├── curriculum_unit FK → CurriculumUnit
  ├── trainer         FK → Trainer
  ├── trainer_type    INTERNAL | OUTSOURCED
  └── label           optional string

Cohort
  ├── programme FK → Programme
  ├── current_term: int
  └── is_active: bool

Term → ScheduledUnit → Conflict, Constraint
```

### Key Design Decisions
1. Template-first — ScheduledUnit is a weekly recurring template
2. No Stage model — `CurriculumUnit.term_number` replaces Stage
3. UUID PKs everywhere
4. `is_outsourced` on CurriculumUnit — scheduler skips these entirely
5. `CurriculumUnitTrainer` through model — INTERNAL/OUTSOURCED labelling
6. OccupancyGrid — in-memory O(1) availability tracker
7. Multi-pass scheduler: STRICT → RELAXED → EMERGENCY

---

## 5. API Endpoint Map

All routes under `/api/` prefix.

```
POST /api/auth/login/                          { username, password } → { token }
GET  /api/auth/me/

GET  /api/institution/
GET  /api/departments/
GET  /api/programmes/
GET  /api/curriculum/?programme=<uuid>&term_number=<n>
GET  /api/curriculum/<uuid>/
PUT  /api/curriculum/<uuid>/
GET  /api/curriculum/<uuid>/trainers/
POST /api/curriculum/<uuid>/trainers/          { trainer_id }
DEL  /api/curriculum/<uuid>/trainers/          { trainer_id }

GET  /api/trainers/
GET  /api/rooms/
GET  /api/periods/
GET  /api/terms/
GET  /api/cohorts/
GET  /api/cohorts/<uuid>/
GET  /api/constraints/
POST /api/constraints/
GET  /api/conflicts/?term=<uuid>
POST /api/conflicts/<uuid>/resolve/

POST /api/timetable/generate/                  { term_id }
POST /api/timetable/publish/                   { term_id, force? }
DELETE /api/timetable/drafts/                  { term_id }
GET  /api/timetable/master/?term=<uuid>&status=DRAFT|PUBLISHED
GET  /api/timetable/cohort/<uuid>/
GET  /api/timetable/trainer/<uuid>/

POST /api/ai/chat/                             { messages, term_id }

GET  /api/dashboard/
GET  /api/export/master/
GET  /api/export/cohort/<uuid>/
GET  /api/export/trainer/<uuid>/
```

---

## 6. Cohort API Response Shape (confirmed)

```json
{
  "id": "uuid",
  "name": "CND JAN 26",
  "programme": "CERTIFICATE IN NUTRITION AND DIETETICS",
  "programme_id": "uuid",
  "current_term": 1,
  "computed_current_term": 2,
  "term_is_synced": false,
  "student_count": 0,
  "start_year": 2026,
  "start_month": 1,
  "is_active": true
}
```
⚠️ `programme` = name string. `programme_id` = UUID. Always use `programme_id` for filtering.

---

## 7. Timetable Grid Response Shape (confirmed)

```json
{
  "ok": true,
  "data": {
    "term": "SEM 1",
    "term_id": "uuid",
    "status": "DRAFT",
    "days": ["MON","TUE","WED","THU","FRI"],
    "periods": [{ "id": "21", "label": "Morning Session", "start": "08:00:00", "order": 1 }],
    "teaching_weeks": 16,
    "total_entries": 25,
    "grid": {
      "MON": {
        "21": [
          {
            "id": "uuid",
            "unit_code": "CND1101",
            "unit_name": "Communication Skills",
            "cohort": "CND JAN 26",
            "cohort_id": "uuid",
            "trainer": "Mrs Ayuma",
            "trainer_id": "uuid",
            "room": "HND 3",
            "room_id": "uuid",
            "day": "MON",
            "period_label": "Morning Session"
          }
        ]
      }
    }
  }
}
```
⚠️ `cohort` = name string. `cohort_id` = UUID. Frontend must use `cohort_id` for comparisons.

---

## 8. Scheduler Behaviour (confirmed from TimetableEngine source)

1. Loads all active cohorts (`programme__department__institution`, `is_active=True`)
2. Per cohort: fetches `CurriculumUnit` filtered by `programme` + `current_term` + `is_active=True`
3. **Outsourced units** (`is_outsourced=True`) → skipped, marked handled, never scheduled
4. Units with no qualified trainer → `NO_TRAINER` conflict (HIGH severity), not scheduled
5. Shared units (same name, programmes in same `sharing_group`) → combined scheduling
6. Multi-pass: STRICT → RELAXED → EMERGENCY
7. Unplaced units → `NO_ROOM` conflict (HIGH severity)

**Units on Offer page writes to `qualified_trainers` M2M via `CurriculumUnitTrainer`. Same data the scheduler reads. No separate "units on offer" model.**

---

## 9. AI Chat (ai_views.py)

**Endpoint:** `POST /api/ai/chat/`
**Body:** `{ messages: [{role, content}], term_id }`
**Model:** Groq Llama 3.3 70B (`llama-3.3-70b-versatile`)

System prompt is built dynamically with live timetable state:
- Pending conflicts with descriptions
- Available trainers + workload
- Available rooms + capacity
- Available periods

Supports structured action blocks in response:
- `REGENERATE` — re-run scheduler
- `MARK_RESOLVED` — resolve a conflict by ID
- `REASSIGN_TRAINER` — guide coordinator to fix manually

**Bug fixed (2026-05-01):** Institution lookup used `departments__users=request.user` which doesn't exist on Institution model. Fixed to `Institution.objects.first()`.

---

## 10. Database Settings (settings.py)

### Production branch (Render — uses DATABASE_URL env var)
```python
DATABASES = {"default": dj_database_url.config(default=_db_url, conn_max_age=60, ssl_require=True)}
DATABASES['default'].setdefault('OPTIONS', {}).update({
    'connect_timeout': 10,
    'keepalives': 1,
    'keepalives_idle': 30,
    'keepalives_interval': 10,
    'keepalives_count': 5,
})
```

### Local branch (uses DB_NAME, DB_USER etc env vars)
```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "tani-africa"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "OPTIONS": {"connect_timeout": 10},
        "CONN_MAX_AGE": 60,
    }
}
```

### DB Retry Middleware (timetabler/db_retry_middleware.py)
Auto-retries failed DB connections up to 3 times with exponential backoff (1s, 2s).
Added to top of MIDDLEWARE list in settings.py.

---

## 11. Environment Variables

| Variable | Where | Notes |
|----------|-------|-------|
| DATABASE_URL | Render env + .env | Render PostgreSQL connection string |
| GROQ_API_KEY | Render env + .env | ⚠️ ROTATE — was exposed in chat session |
| DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT | .env | Local dev only |

---

## 12. Known Issues (as of 2026-05-01)

| Issue | Severity | Notes |
|-------|----------|-------|
| 60 NO_ROOM conflicts | HIGH | Units have trainers but no room slot found. Check room count/capacity. |
| Render DB sleep | MEDIUM | Free tier suspends after inactivity. Retry middleware helps but first request slow. Set up UptimeRobot. |
| Groq API key exposed | HIGH | Rotate at console.groq.com immediately |
| Token may expire | LOW | `611ba54aa78eb3dd57e0a7a9d2861f41553f8e12` used in shell commands — re-login if 401 |

---

## 13. Bugs Fixed (2026-05-01)

| Bug | Cause | Fix |
|-----|-------|-----|
| AI chat 500 error | `departments__users` relation doesn't exist on Institution | Changed to `Institution.objects.first()` in ai_views.py |
| DB timeout 500s | Render free tier suspends DB | Added keepalives to settings + DBRetryMiddleware |
| Timetable cohort count showing 1 | Frontend used `e.cohort.id` but API returns cohort as string + separate `cohort_id` | Fixed to use `cohort_id` field throughout timetable page |
| Units on Offer 404s | Frontend used `/api/curriculum-units/` (wrong) and `cohort.programme` (name not UUID) | Fixed to `/api/curriculum/` with `cohort.programme_id` |
| Trainer dropdown empty | API returns `full_name`/`short_name` not `name` | Fixed trainer interface in units-on-offer page |
| Trainer assign failed | POST body used `trainer_ids` (plural) | Fixed to `trainer_id` (singular) |

---

## 14. GitHub Repos

- Backend: `github.com:Sozi-source/timetabler-api.git` (branch: main)
- Frontend: `github.com:Sozi-source/timetabler.git` (branch: main)

Last backend push: `e78fa41` — "fix: AI chat institution lookup, DB keepalives, retry middleware, scheduler fixes"
Last frontend push: `d7b2931` — "fix: timetable cohort count, cohort filter, units-on-offer page"

---

## 15. Next Steps

1. **Rotate Groq API key** — exposed in chat, do this first
2. **Fix 60 NO_ROOM conflicts** — check rooms configured, capacity, scheduler room logic
3. **Add GROQ_API_KEY to Render** environment variables
4. **Set up UptimeRobot** — ping `/api/terms/` every 5 min to prevent DB sleep
5. **Verify sub-timetable pages** — cohort and trainer views
6. **Excel bulk trainer upload** — POST /api/curriculum/trainers/bulk/

---

*End of context document.*
*Paste this at the top of your next chat and say:*
**"Continue building the timetabler system — [your task]. Update the context file at the end of this session with all changes made."**