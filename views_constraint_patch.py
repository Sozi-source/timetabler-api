# ─── PATCH: replace ConstraintListView.post() in views.py ───────────────────
#
# The original code only read data.get("unit_id") but the frontend ConstraintModal
# sends "curriculum_unit" as the key (matching the model field name).
# This patch accepts either key so both old and new frontend code works.
#
# Find this method in views.py and replace it:

    def post(self, request):
        data = request.data
        try:
            # FIX: accept "curriculum_unit" OR "unit_id" for the unit foreign key.
            # The rebuilt ConstraintModal sends "curriculum_unit"; legacy code sent "unit_id".
            unit_id = (
                data.get("curriculum_unit")      # new frontend key
                or data.get("unit_id")           # legacy / direct API key
            )
            c = Constraint.objects.create(
                scope=data["scope"],
                rule=data["rule"],
                is_hard=bool(data.get("is_hard", True)),
                curriculum_unit_id=unit_id,      # None is fine for COHORT/TRAINER/ROOM scope
                cohort_id=data.get("cohort_id"),
                trainer_id=data.get("trainer_id"),
                room_id=data.get("room_id"),
                parameters=data.get("parameters", {}),
                notes=data.get("notes", ""),
                is_active=bool(data.get("is_active", True)),
            )
            return ok({"id": str(c.id)}, 201)
        except KeyError as e:
            return err(f"Missing field: {e}")
        except Exception as e:
            return err(str(e), status_code=500)


# ─── HOW TO APPLY IN POWERSHELL ──────────────────────────────────────────────
#
# The ConstraintListView.post() method starts around line 340 in views.py.
# Replace the entire post() method body with the one above.
#
# PowerShell patch command:
#
# $f = "C:\users\sozi\Desktop\2026-projects\Timetable\timetabler\timetable\views.py"
# $old = @'
#     def post(self, request):
#         data = request.data
#         try:
#             c = Constraint.objects.create(
#                 scope=data["scope"],
#                 rule=data["rule"],
#                 is_hard=bool(data.get("is_hard", True)),
#                 curriculum_unit_id=data.get("unit_id"),
#                 cohort_id=data.get("cohort_id"),
#                 trainer_id=data.get("trainer_id"),
#                 room_id=data.get("room_id"),
#                 parameters=data.get("parameters", {}),
#                 notes=data.get("notes", ""),
#             )
#             return ok({"id": str(c.id)}, 201)
#         except KeyError as e:
#             return err(f"Missing field: {e}")
#         except Exception as e:
#             return err(str(e), status_code=500)
# '@
# $new = @'
#     def post(self, request):
#         data = request.data
#         try:
#             unit_id = (
#                 data.get("curriculum_unit")
#                 or data.get("unit_id")
#             )
#             c = Constraint.objects.create(
#                 scope=data["scope"],
#                 rule=data["rule"],
#                 is_hard=bool(data.get("is_hard", True)),
#                 curriculum_unit_id=unit_id,
#                 cohort_id=data.get("cohort_id"),
#                 trainer_id=data.get("trainer_id"),
#                 room_id=data.get("room_id"),
#                 parameters=data.get("parameters", {}),
#                 notes=data.get("notes", ""),
#                 is_active=bool(data.get("is_active", True)),
#             )
#             return ok({"id": str(c.id)}, 201)
#         except KeyError as e:
#             return err(f"Missing field: {e}")
#         except Exception as e:
#             return err(str(e), status_code=500)
# '@
# (Get-Content $f -Raw) -replace [regex]::Escape($old), $new | Set-Content $f -Encoding UTF8
