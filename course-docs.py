#!/usr/bin/env python3
"""Generate the module reference page for the docs site.

The hand-written module list on the docs site went a year without an update and drifted
badly — it still described lessons the planner had deleted (100.1-100.4) and a numbering
scheme that no longer exists (710/720/730/740). Structure is generated from now on;
narrative and rationale stay hand-written on the Course Design page.

Sources, all authoritative in their own right:
  plan/course-plan.yaml   the planner's structure and per-element deck source
  import-staging/<code>/  the exact payload sent to Andamio — SLT text, lesson and
                          assignment counts, i.e. what is actually live

Usage:
    python3 course-docs.py            # writes ../spoacademydocs/docs/course/modules.md
    python3 course-docs.py --stdout
"""
import argparse, glob, json, os, re, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(HERE, "plan", "course-plan.yaml")
STAGING = os.path.join(HERE, "import-staging")
OUT = os.path.abspath(os.path.join(HERE, "..", "spoacademydocs", "docs", "course", "modules.md"))
STATS = os.path.abspath(os.path.join(HERE, "..", "spoacademydocs", "src", "data",
                                     "course-stats.json"))
COURSE_ID = "e60f29abf7a3f348bf4f51a078dae6f53cd3bc065d74632d3f67d785"
COURSE_URL = f"https://app.andamio.io/course/{COURSE_ID}"

SOURCE_LABEL = {"spo": "written", "general": "in adaptation", "none": "in preparation"}


def planner_date():
    m = re.search(r"modified (\d{4}-\d{2}-\d{2})", open(PLAN).read())
    return m.group(1) if m else "unknown date"


def live(code):
    """What the platform actually holds for this module, read from the import payload."""
    d = os.path.join(STAGING, code)
    if not os.path.isdir(d):
        return None
    outline = os.path.join(d, "outline.md")
    slts = []
    if os.path.exists(outline):
        slts = [re.sub(r"^\d+\.\s*", "", l).strip()
                for l in open(outline).read().splitlines() if re.match(r"^\d+\.\s", l)]
    return dict(
        slts=slts,
        lessons=len(glob.glob(os.path.join(d, "lesson-*.md"))),
        assignment=os.path.exists(os.path.join(d, "assignment.md")),
        intro=os.path.exists(os.path.join(d, "introduction.md")),
        images=len(glob.glob(os.path.join(d, "assets", "*.png")))
               + len(glob.glob(os.path.join(d, "assets", "*.jpg"))),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--stats", default=STATS,
                    help="JSON the docs homepage reads for its figures")
    args = ap.parse_args()

    plan = yaml.safe_load(open(PLAN))
    # Public page: no tool names, no repository paths, no "do not edit" instructions and
    # no planner dates. Those are build-process details and mean nothing to a reader.
    L = ["---", "title: Module Reference", "---", "",
         "The structure of the course as it stands on the platform — every module, its "
         "elements, and the learning targets a student works through.", "",
         f"The course is live at [app.andamio.io]({COURSE_URL}).", ""]

    tot = dict(slts=0, lessons=0, assignments=0, elements=0)
    rows = []
    for m in plan["modules"]:
        lv = live(str(m["code"]))
        tot["elements"] += len(m["elements"])
        if lv:
            tot["slts"] += len(lv["slts"])
            tot["lessons"] += lv["lessons"]
            tot["assignments"] += 1 if lv["assignment"] else 0
        rows.append((m, lv))

    L += ["| module | title | on the platform |", "|---|---|---|"]
    for m, lv in rows:
        state = (f"{len(lv['slts'])} learning targets · {lv['lessons']} lessons · "
                 f"{'assignment' if lv['assignment'] else 'no assignment'}") if lv else "in preparation"
        L.append(f"| {m['code']} | {m['title']} | {state} |")
    L += ["",
          f"**{len(rows)} modules · {tot['slts']} student learning targets · "
          f"{tot['lessons']} lessons · {tot['assignments']} assignments.** "
          f"{tot['elements']} elements are defined in total; those still being written are "
          "not yet on the platform.", ""]

    for m, lv in rows:
        L += [f"## {m['code']} — {m['title']}", ""]

        L += ["| element | type | title | content |", "|---|---|---|---|"]
        for el in m["elements"]:
            src = SOURCE_LABEL.get(el.get("source") or "none", el.get("source"))
            L.append(f"| {el['code']} | {el.get('type', '')} | "
                     f"{(el.get('title') or '').replace('|', '/')} | {src} |")
        L += [""]
        if lv and lv["slts"]:
            L += ["**Student learning targets**", ""]
            L += [f"{i}. {s}" for i, s in enumerate(lv["slts"], 1)]
            L += [""]

    text = "\n".join(L) + "\n"
    if args.stdout:
        print(text)
        return 0

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    open(args.out, "w").write(text)
    print(f"{len(rows)} modules, {tot['slts']} SLTs, {tot['lessons']} lessons, "
          f"{tot['assignments']} assignments → {args.out}")

    # The docs homepage shows these figures. Emitting them here means the homepage cannot
    # quietly go stale the way its hand-written predecessor did.
    # Count figures the staged content actually references, not every file sitting in
    # assets/. A module that shrinks leaves its old figures behind, and counting those
    # would overstate the course — 215 against a true 172 after module 300 went 18 to 10.
    images = set()
    for md in glob.glob(os.path.join(STAGING, "*", "*.md")):
        mod = os.path.basename(os.path.dirname(md))
        for ref in re.findall(r"assets/([^)\s]+)", open(md).read()):
            images.add((mod, ref))
    images = len(images)
    stats = dict(modules=len(rows), slts=tot["slts"], lessons=tot["lessons"],
                 assignments=tot["assignments"], images=images,
                 planner=planner_date(), courseUrl=COURSE_URL)
    os.makedirs(os.path.dirname(args.stats), exist_ok=True)
    with open(args.stats, "w") as fh:
        json.dump(stats, fh, indent=2)
        fh.write("\n")
    print(f"stats → {args.stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
