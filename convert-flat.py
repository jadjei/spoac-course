#!/usr/bin/env python3
"""Convert authored course/ elements to FLAT Andamio modules (one module per Col-1 code).

Each `status: drafted` element file becomes its own Andamio module: outline (title +
1 SLT), introduction.md (its Overview), lesson-1.md (its Content/body). Module 100 is
left untouched (already correctly bundled with decimal sub-lessons 100.1–100.4).
Assignments and stubs are skipped. Images copied.

Out: import-flat/<code>/
"""
import os, re, glob, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "import-flat")

def parse(p):
    t = open(p).read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", t, re.S)
    fm = {}
    body = t
    if m:
        for line in m.group(1).splitlines():
            mm = re.match(r'(\w+):\s*"?([^"#]*)"?', line)
            if mm: fm[mm.group(1)] = mm.group(2).strip()
        body = m.group(2)
    return fm, body

def section(body, name):
    m = re.search(rf"^## {name}\b.*?\n(.*?)(?=\n## |\Z)", body, re.S | re.M)
    return m.group(1).strip() if m else ""

def first_slt(body, title):
    s = section(body, "Student Learning Targets")
    for line in s.splitlines():
        mm = re.match(r"\s*\d+\.\s*(.+)", line)
        if mm and not mm.group(1).strip().startswith(("_", ">")):
            return mm.group(1).strip()
    # No stand-in: see the note on convert.py's first_slt. A generated target reads like
    # a real one, which is exactly why it goes unnoticed all the way onto the platform.
    raise SystemExit(f"{title}: no Student Learning Target — write one before converting")

def main():
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    made = []
    for f in sorted(glob.glob(os.path.join(HERE, "course", "*", "*.md"))):
        fm, body = parse(f)
        code = fm.get("code", "")
        if fm.get("status") != "drafted": continue
        if code.startswith("100"): continue            # keep 100 bundled, untouched
        if fm.get("type") == "assignment": continue
        title = fm.get("title", code)
        d = os.path.join(OUT, code); os.makedirs(d, exist_ok=True)
        # outline: 1 SLT (single-topic module)
        open(os.path.join(d, "outline.md"), "w").write(
            f'---\ntitle: "{title}"\ncode: "{code}"\n---\n\n# {title}\n\n## SLTs\n\n1. {first_slt(body, title)}\n')
        ov = section(body, "Overview")
        if ov: open(os.path.join(d, "introduction.md"), "w").write(f"# {title}\n\n{ov}\n")
        # lesson-1 = the content (prefer ## Content, else ## Lesson, else whole body)
        content = section(body, "Content") or section(body, "Lesson") or body.strip()
        open(os.path.join(d, "lesson-1.md"), "w").write(f"# {title}\n\n{content}\n")
        # assets referenced
        srcassets = os.path.join(os.path.dirname(f), "assets")
        if os.path.isdir(srcassets):
            shutil.copytree(srcassets, os.path.join(d, "assets"), dirs_exist_ok=True)
        made.append(code)
    print(f"flat modules: {len(made)}")
    print(" ".join(made))

if __name__ == "__main__":
    main()
