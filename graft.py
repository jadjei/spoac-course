#!/usr/bin/env python3
"""Graft existing live content into the scaffold's `live_source`-tagged elements.

For every course/**/*.md whose frontmatter has a `live_source`, replace its trailing
"## Content"/"## Assignment" placeholder with the real content from the matching live
module in compiled/spo-online-business-academy/<src>/ (introduction + lessons +
assignment). The planner-authored Overview + SLTs above are left untouched
(authoritative). Re-runnable: run after scaffold.py.

Partial (consolidated) sources: live 320's content covers three planned elements
(303.1, 303.3, 306). To avoid triplicating it, the full 320 content is grafted into
306 only; 303.1/303.3 get a pointer note. The 320 split is a deferred decision.

**Stubs only.** The live Andamio content is the *oldest* material in play — the planner
and its decks outrank it. So an element that already holds authored prose (hand-written,
or migrated across a planner renumbering by scaffold.py) is skipped: grafting there
would replace better content with worse. Only genuine `> TODO:` stubs get filled.
"""
import os, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.join(HERE, "course")
LIVE = os.path.join(HERE, "compiled", "spo-online-business-academy")
DATE = "2026-06-11"
PARTIAL_FULL_TARGET = "306"  # the single element that receives the consolidated 320 content
PLANNER_OWNED = ("overview", "student learning target")


def read(p):
    return open(p).read() if os.path.isfile(p) else ""


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r'(\w+):\s*"?([^"#]*)"?', line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip()
    return fm, text


def live_block(src):
    d = os.path.join(LIVE, src)
    parts = []
    intro = read(os.path.join(d, "introduction.md")).strip()
    if intro:
        parts += ["### Introduction (live)", "", intro, ""]
    for lf in sorted(glob.glob(os.path.join(d, "lesson-*.md")),
                     key=lambda p: int(re.search(r"lesson-(\d+)", p).group(1))):
        n = re.search(r"lesson-(\d+)", lf).group(1)
        body = read(lf).strip()
        if body:
            parts += [f"### Lesson {n} (live)", "", body, ""]
    asg = read(os.path.join(d, "assignment.md")).strip()
    if asg:
        parts += ["### Assignment (live)", "", asg, ""]
    return "\n".join(parts).strip() or "_(live module had no body content)_"


def has_authored_body(text):
    """True if the element already carries prose the graft must not overwrite."""
    body = text.split("---", 2)[-1]
    words = 0
    for sec in re.split(r"^## +", body, flags=re.M)[1:]:
        if sec.splitlines()[0].strip().lower().startswith(PLANNER_OWNED):
            continue
        words += sum(len(ln.split()) for ln in sec.splitlines()[1:]
                     if ln.strip() and not ln.strip().startswith((">", "#")))
    return words > 25


def splice(text, new_section):
    """Replace from the '## Content' or '## Assignment' header to EOF."""
    m = re.search(r"\n## (Content|Assignment)\b", text)
    head = text[: m.start()].rstrip() if m else text.rstrip()
    header = m.group(1) if m else "Content"
    return f"{head}\n\n## {header}\n\n{new_section}\n"


def main():
    grafted = pointer = skipped = 0
    for f in glob.glob(os.path.join(COURSE, "*", "*.md")):
        text = read(f)
        fm, _ = frontmatter(text)
        src = fm.get("live_source", "").strip()
        if not src:
            continue
        if has_authored_body(text):
            print(f"  skip (already authored): {os.path.relpath(f, COURSE)}")
            skipped += 1
            continue
        code = fm.get("code", "")
        is_partial = "PARTIAL" in text.split("---", 2)[1]  # comment flag in frontmatter

        if is_partial and code != PARTIAL_FULL_TARGET:
            note = (f"_Content for this element currently lives **consolidated in live module "
                    f"`{src}`**, grafted into element `{PARTIAL_FULL_TARGET}`. Splitting "
                    f"`{src}` into this element is a deferred decision (see gap-analysis.md §3)._")
            open(f, "w").write(splice(text, note))
            pointer += 1
            continue

        tag = " (consolidated source — pending split)" if is_partial else ""
        body = (f"_Grafted from live module `{src}` "
                f"(`compiled/spo-online-business-academy/{src}`) on {DATE}.{tag}_\n\n"
                + live_block(src))
        open(f, "w").write(splice(text, body))
        grafted += 1

    print(f"Grafted live content into {grafted} elements; {pointer} partial pointers; "
          f"{skipped} skipped (already authored — planner/deck content outranks live).")


if __name__ == "__main__":
    main()
