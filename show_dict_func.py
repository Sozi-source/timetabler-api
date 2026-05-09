"""
show_dict_func.py — run from timetabler/ to print the current _scheduled_unit_dict
"""
import pathlib, re

src = pathlib.Path("timetable/views.py").read_text(encoding="utf-8")

# Find the function and print ~35 lines from it
idx = src.find("def _scheduled_unit_dict")
if idx == -1:
    print("Function not found!")
else:
    snippet = src[idx:idx+1500]
    print(repr(snippet))   # repr so we see exact whitespace/quotes
