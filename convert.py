#!/usr/bin/env python3
"""Convert an authored course/<module>/ dir into Andamio compiled format.

One Andamio module per planner module: the `type: video` overview file becomes
introduction.md, each lesson file that actually has a body becomes a lesson-N.md
(one lesson per SLT), and outline.md lists one SLT per lesson (the lesson's first
SLT, or its title). Images are copied.

Selection is by *body*, not by a status field: an element ships if it carries real
prose (narration mapped from its deck, or migrated/grafted material). Empty `> TODO:`
stubs are skipped, so nothing half-built reaches the platform. Deferred elements never
produce a file in the first place, so they cannot appear here.

Usage: python3 convert.py <course-module-dir> <out-dir>
"""
import os, re, sys, glob, shutil

def parse(path):
    t = open(path).read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", t, re.S)
    fm, body = ({}, t)
    if m:
        for line in m.group(1).splitlines():
            mm = re.match(r'(\w+):\s*"?([^"#]*)"?', line)
            if mm: fm[mm.group(1)] = mm.group(2).strip()
        body = m.group(2)
    return fm, body.strip()

class MissingTarget(Exception):
    """An element with no learning target of its own."""


def first_slt(body, title, code=""):
    """The element's own learning target, or refuse to invent one.

    This used to answer a missing target with "I can understand {title}." — a lesson
    title with a stem bolted on. It reads like a target, so nothing downstream noticed,
    and 21 of the 39 targets on the platform arrived that way. A target names what the
    learner can do and is what the module's credential claims; a title cannot stand in
    for one. Failing here makes the gap visible where it can still be fixed.
    """
    m = re.search(r"## Student Learning Targets\s*\n(.*?)(?=\n## |\Z)", body, re.S)
    if m:
        for line in m.group(1).splitlines():
            s = re.match(r"\s*\d+\.\s*(.+)", line)
            if s and not s.group(1).strip().startswith(("_", ">")):
                return s.group(1).strip()
    raise MissingTarget(
        f"{code or title}: no Student Learning Target — write one on the element "
        "(and in column K of the planner) rather than shipping a generated stand-in")

PLANNER_OWNED = ("overview", "student learning target")


def has_body(body):
    """Real prose under any non-planner-owned heading (## Content, ## Lesson, …)."""
    words = 0
    for sec in re.split(r"^## +", body, flags=re.M)[1:]:
        if sec.splitlines()[0].strip().lower().startswith(PLANNER_OWNED):
            continue
        words += sum(len(l.split()) for l in sec.splitlines()[1:]
                     if l.strip() and not l.strip().startswith((">", "#")))
    return words > 25


# Provenance for us, noise for a learner: every mapped lesson opens with an italic line
# naming the deck and slide range its body came from. It belongs in the repo, where it
# says which file to re-map from, and not on the platform, where it appeared above the
# first paragraph of all 40 lessons.
PROVENANCE_RE = re.compile(
    r"^_(?:Lesson body|Narration|Body) from .*?_\s*$\n?", re.M | re.S)


def body_only(body):
    """Drop the planner-owned sections; the intro/lesson content is what ships."""
    keep = []
    for sec in re.split(r"^## +", body, flags=re.M)[1:]:
        if sec.splitlines()[0].strip().lower().startswith(PLANNER_OWNED):
            continue
        keep.append("## " + PROVENANCE_RE.sub("", sec).rstrip())
    return "\n\n".join(keep).strip()


def main():
    src, out = sys.argv[1], sys.argv[2]
    files = [parse(f) + (f,) for f in glob.glob(os.path.join(src, "*.md"))]
    overview = next((x for x in files if x[0].get("type") == "video"), None)
    lessons = sorted([x for x in files if x[0].get("type") in ("lesson", "overview")
                      and has_body(x[1])],
                     key=lambda x: x[0].get("code", ""))
    if not overview or not lessons:
        print(f"  skip {src}: overview={bool(overview)} lessons-with-body={len(lessons)}"); return
    ofm, obody = overview[0], overview[1]
    code, title = ofm.get("code"), ofm.get("title", "")
    d = os.path.join(out, code); os.makedirs(d, exist_ok=True)

    try:
        slts = [first_slt(b, fm.get("title", ""), fm.get("code", "")) for fm, b, _ in lessons]
    except MissingTarget as e:
        print(f"  SKIP {src}: {e}")
        return
    outline = [f'---', f'title: "{title}"', f'code: "{code}"', '---', '', f'# {title}', '', '## SLTs', '']
    outline += [f"{i+1}. {s}" for i, s in enumerate(slts)]
    open(os.path.join(d, "outline.md"), "w").write("\n".join(outline) + "\n")
    # each file needs an H1: the importer takes the lesson/intro title from it
    intro_body = body_only(obody) or obody
    open(os.path.join(d, "introduction.md"), "w").write(f"# {title}\n\n{intro_body}\n")
    for i, (fm, body, _) in enumerate(lessons, 1):
        ltitle = fm.get("title") or f"Lesson {i}"
        open(os.path.join(d, f"lesson-{i}.md"), "w").write(
            f"# {ltitle}\n\n{body_only(body)}\n")

    # Prune lesson files left by a previous, longer run. Without this a module that shrinks
    # keeps its old tail — module 300 went 18 lessons to 10 and would have staged eight
    # stale lessons the planner no longer defines.
    for stale in glob.glob(os.path.join(d, "lesson-*.md")):
        n = int(re.search(r"lesson-(\d+)\.md$", stale).group(1))
        if n > len(lessons):
            os.remove(stale)
            print(f"    pruned {os.path.basename(stale)} (no longer in the plan)")

    # Andamio holds ONE assignment per module, so the module's authored assignment element
    # becomes assignment.md. Same body rule as lessons: a `> TODO:` stub is not shipped, so
    # an unwritten assignment simply does not reach the platform. Where a module has several
    # `.a` elements the last by code wins — that is the module capstone, the one the earlier
    # ones feed into.
    assignments = sorted([x for x in files if x[0].get("type") == "assignment"
                          and has_body(x[1])],
                         key=lambda x: x[0].get("code", ""))
    if assignments:
        afm, abody, _ = assignments[-1]
        atitle = afm.get("title") or "Assignment"
        open(os.path.join(d, "assignment.md"), "w").write(
            f"# {atitle}\n\n{body_only(abody)}\n")
    if os.path.isdir(os.path.join(src, "assets")):
        # .svg never reaches the platform: Andamio's CDN answers INVALID_TYPE for it
        # (PNG/JPG/GIF/WebP only). Staging it just makes every import report a failed
        # upload. The SVG masters stay in course/ for theming; lessons cite the .png.
        shutil.copytree(os.path.join(src, "assets"), os.path.join(d, "assets"),
                        dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.svg"))
    print(f"  ✓ {code} '{title}': {len(lessons)} lessons, {len(slts)} SLTs"
          + (f", assignment '{assignments[-1][0].get('title')}'" if assignments else ", NO assignment"))

if __name__ == "__main__":
    main()
