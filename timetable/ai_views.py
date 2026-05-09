"""
timetable/ai_views.py
=====================
Proxy view for Groq AI chat — keeps API key server-side.

Add to timetable/urls.py:
    path("ai/chat/", ai_views.AIChatView.as_view()),

Add to Render environment variables:
    GROQ_API_KEY=gsk_...
"""

import json
import traceback

import requests
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Cohort, Conflict, Institution, Period, Room,
    ScheduledUnit, Term, Trainer,
)


# ── Response helpers ───────────────────────────────────────────────────────
# Defined locally so we're not dependent on views.ok / views.err signature.

def _ok(data, status=200):
    return Response({"ok": True, "data": data}, status=status)

def _err(message, detail=None, status=400):
    payload = {"ok": False, "error": message}
    if detail:
        payload["detail"] = detail
    return Response(payload, status=status)


# ── Context builder ────────────────────────────────────────────────────────

def _build_timetable_context(term: Term, institution: Institution) -> dict:
    """Gather live timetable state to inject into the AI system prompt."""
    pending_conflicts = Conflict.objects.filter(
        term=term,
        resolution_status="PENDING",
    ).select_related("cohort", "trainer", "curriculum_unit")

    sessions        = ScheduledUnit.objects.filter(term=term).count()
    draft_count     = ScheduledUnit.objects.filter(term=term, status="DRAFT").count()
    published_count = ScheduledUnit.objects.filter(term=term, status="PUBLISHED").count()

    trainers = list(
        Trainer.objects.filter(institution=institution, is_active=True)
        .values("id", "first_name", "last_name", "max_periods_per_week", "available_days")
    )
    rooms = list(
        Room.objects.filter(institution=institution, is_active=True)
        .values("id", "name", "code", "capacity", "room_type")
    )
    periods = list(
        Period.objects.filter(institution=institution, is_break=False)
        .order_by("order")
        .values("id", "label", "start_time", "end_time", "order")
    )

    conflicts_data = []
    for c in pending_conflicts:
        conflicts_data.append({
            "id": str(c.id),
            "type": c.conflict_type,
            "severity": c.severity,
            "description": c.description,
            "unit_code":    c.curriculum_unit.code if c.curriculum_unit else None,
            "cohort_name":  c.cohort.name if c.cohort else None,
            "trainer_name": f"{c.trainer.first_name} {c.trainer.last_name}" if c.trainer else None,
        })

    return {
        "term_name":         term.name,
        "total_sessions":    sessions,
        "draft_sessions":    draft_count,
        "published_sessions": published_count,
        "pending_conflicts": conflicts_data,
        "trainers":          trainers,
        "rooms":             rooms,
        "periods": [
            {**p, "start_time": str(p["start_time"]), "end_time": str(p["end_time"])}
            for p in periods
        ],
    }


# ── System prompt ──────────────────────────────────────────────────────────

def _build_system_prompt(ctx: dict) -> str:
    conflicts = ctx["pending_conflicts"]
    trainers  = ctx["trainers"]
    rooms     = ctx["rooms"]
    periods   = ctx["periods"]

    conflict_text = "None — timetable is clean." if not conflicts else "\n".join(
        (
            f"  {i+1}. [{c['severity']}] {c['type']}: {c['description']}"
            + (f" | Unit: {c['unit_code']}"      if c['unit_code']    else '')
            + (f" | Cohort: {c['cohort_name']}"  if c['cohort_name']  else '')
            + (f" | Trainer: {c['trainer_name']}" if c['trainer_name'] else '')
            + f" | ID: {c['id']}"
        )
        for i, c in enumerate(conflicts)
    )

    trainer_text = "\n".join(
        f"  - {t['first_name']} {t['last_name']} | max {t['max_periods_per_week']} periods/wk | days: {t['available_days']}"
        for t in trainers
    ) or "  None configured."

    room_text = "\n".join(
        f"  - {r['code']} ({r['name']}) | capacity: {r['capacity']} | type: {r['room_type']}"
        for r in rooms
    ) or "  None configured."

    period_text = "\n".join(
        f"  - {p['label']} | {p['start_time']}–{p['end_time']} | ID: {p['id']}"
        for p in periods
    ) or "  None configured."

    return f"""You are an expert academic timetable coordinator AI assistant embedded in a system called Timetabler. You help admins and coordinators diagnose and fix scheduling conflicts.

CURRENT TIMETABLE STATE:
- Term: {ctx['term_name']}
- Total sessions: {ctx['total_sessions']} ({ctx['draft_sessions']} draft, {ctx['published_sessions']} published)
- Pending conflicts: {len(conflicts)}

PENDING CONFLICTS:
{conflict_text}

AVAILABLE TRAINERS:
{trainer_text}

AVAILABLE ROOMS:
{room_text}

AVAILABLE PERIODS (teaching sessions only):
{period_text}

YOUR ROLE:
- Diagnose conflicts clearly and explain them in plain language
- Suggest specific, actionable fixes referencing real trainer names, room codes, and period labels
- When you recommend an action the system can apply automatically, include it as a structured JSON action block
- Be concise — coordinators are busy. Max 3 sentences per explanation.

AVAILABLE ACTIONS (include JSON block ONLY when genuinely applicable):
- REGENERATE: Re-run the scheduling engine
- MARK_RESOLVED: Mark a specific conflict as manually resolved (requires conflict_id)
- REASSIGN_TRAINER: Guide coordinator to reassign trainer (requires unit_code)

When including actions, append this exact format after your response text:
<actions>
[{{"label":"Button label","action":"ACTION_TYPE","payload":{{"conflict_id":"...","unit_code":"...","notes":"..."}},"description":"One line description"}}]
</actions>

Only include <actions> when a clear executable step exists. Do not include it for general advice.
Always be direct, specific, and reference real names and IDs from the context above."""


# ── View ───────────────────────────────────────────────────────────────────

class AIChatView(APIView):
    """
    POST /api/ai/chat/
    Body: { "messages": [...], "term_id": "..." }
    Returns: { "ok": true, "data": { "content": "..." } }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # ── Guard: API key ─────────────────────────────────────────────────
        groq_api_key = getattr(settings, "GROQ_API_KEY", None)
        if not groq_api_key:
            return _err(
                "GROQ_API_KEY is not configured on the server. "
                "Add it to your Render environment variables.",
                status=500,
            )

        messages = request.data.get("messages", [])
        term_id  = request.data.get("term_id", "")

        if not messages:
            return _err("messages is required.", status=400)

        # ── Resolve term & build context ───────────────────────────────────
        try:
            institution = Institution.objects.first()
            if not institution:
                return _err("No institution configured.", status=500)

            if term_id:
                term = Term.objects.get(id=term_id)
            else:
                term = Term.objects.filter(
                    institution=institution, is_current=True
                ).first()

            if not term:
                return _err(
                    "No active term found. Please set a current term in the admin.",
                    status=400,
                )

            ctx           = _build_timetable_context(term, institution)
            system_prompt = _build_system_prompt(ctx)

        except Term.DoesNotExist:
            return _err("Term not found.", status=404)
        except Exception:
            return _err(
                "Failed to build timetable context.",
                detail=traceback.format_exc(),
                status=500,
            )

        # ── Call Groq ──────────────────────────────────────────────────────
        try:
            groq_response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       "llama-3.3-70b-versatile",
                    "max_tokens":  1024,
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        *[
                            {"role": m["role"], "content": m["content"]}
                            for m in messages
                            if m.get("role") in ("user", "assistant") and m.get("content")
                        ],
                    ],
                },
                timeout=30,
            )
            groq_response.raise_for_status()
            result  = groq_response.json()
            content = result["choices"][0]["message"]["content"]
            return _ok({
                "content": content,
                "context": {
                    "pending_conflicts": len(ctx["pending_conflicts"]),
                    "term_name":         ctx["term_name"],
                },
            })

        except requests.exceptions.Timeout:
            return _err("Groq API timed out. Please try again.", status=504)

        except requests.exceptions.HTTPError:
            detail = ""
            try:
                detail = groq_response.json().get("error", {}).get("message", str(groq_response.text))
            except Exception:
                detail = str(groq_response.text)
            return _err(f"Groq API error: {detail}", status=502)

        except Exception:
            return _err(
                "Failed to call Groq API.",
                detail=traceback.format_exc(),
                status=500,
            )