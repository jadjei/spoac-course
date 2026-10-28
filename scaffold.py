#!/usr/bin/env python3
"""Scaffold a local course tree from the authoritative SPOAC Course Planner.

Reads plan/course-plan.yaml and writes course/<module>/<element>.md — one markdown
file per planned element, grouped by top module, populated with the planner's
title / overview / SLTs. Each file is tagged with `live_source` (the existing live
module code whose content maps in, per gap-analysis.md) so authored content can be
grafted in a later pass. Re-run any time; it overwrites course/ from the plan.

`--dry-run` writes nothing and instead reports what a real run would do to the existing
tree: which files match, which are new, and which existing files would be **orphaned**
(no element in the current plan produces them). Orphans holding authored prose — as
opposed to untouched `> TODO:` stubs — are called out separately, because a real run
deletes them.
"""
import argparse, os, re, shutil
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(HERE, "plan", "course-plan.yaml")
OUT = os.path.join(HERE, "course")

# planner code -> live module code in compiled/ that holds existing content for it
# (from gap-analysis.md §1). Partial = content exists but only covers part of the element.
LIVE_MAP = {
    "000": "000",
    "202": "201",            # live "Biomes"
    "205": "202",            # live "Business Audit"
    "301": "301",            # live "Big Purpose"
    "303.1": "320*",         # partial — consolidated in live 320
    "303.3": "320*",         # partial — consolidated in live 320
    "306": "320*",           # partial — consolidated in live 320
    "400": "400",
    "501": "501",
    "502": "502",
    "601": "601", "602": "602", "603": "603",
    "700": "700",
    "301.3": "701",          # live "Setting Your Vision"
    "701": "702",            # live "Your Business Plan"
    "702": "203",            # live "Building Your Dashboard for Growth"
    "703": "703",
    "704": "704",
}

MODULE_DIRNAMES = {
    "000": "000-orientation",
    "100": "100-our-changing-world",
    "200": "200-your-journey-toolkit",
    "300": "300-your-why-your-essence",
    "400": "400-market-biome",
    "500": "500-internal-biome",
    "600": "600-external-biome",
    "700": "700-the-journey",
}


def slug(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "untitled"


def frontmatter(txt):
    d = {}
    if txt.startswith("---"):
        for ln in txt.split("---", 2)[1].strip().splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                d[k.strip()] = v.split("#")[0].strip().strip('"')
    return d


PLANNER_OWNED = ("overview", "student learning target")


def split_sections(txt):
    """Authored body sections, and the file's SLT section if it has one.

    Files here use several conventions: this script writes `## Content` /
    `## Assignment`, while hand-authored lessons use `## Lesson` and add their own
    sections. So rather than hunting for one known heading, keep every section except
    the ones the planner owns (Overview, SLTs) — anything else is authored material.
    """
    body = txt.split("---", 2)[-1]
    parts = re.split(r"^## +", body, flags=re.M)
    keep, slt = [], ""
    for p in parts[1:]:
        name = p.splitlines()[0].strip().lower()
        if name.startswith("student learning target"):
            slt = "## " + p.rstrip()
            continue
        if name.startswith(PLANNER_OWNED):
            continue
        keep.append("## " + p.rstrip())
    return "\n\n".join(keep).strip(), slt


def content_section(txt):
    return split_sections(txt)[0]


def is_prose(section):
    prose = [ln for ln in section.splitlines()
             if ln.strip() and not ln.strip().startswith((">", "#"))]
    return sum(len(ln.split()) for ln in prose) > 25


def authored(path):
    """True if the file carries real prose rather than an untouched scaffold stub."""
    try:
        return is_prose(content_section(open(path).read()))
    except OSError:
        return False


def harvest(out_dir):
    """Index authored bodies in the existing tree, keyed for remapping.

    The planner renames and renumbers elements between revisions, so a rescaffold must
    not identify content by filename. `old_code` (the legacy M-code) is stable across
    every rename observed so far and is tried first; the element code is the fallback.
    """
    by_old, by_code = {}, {}
    for r, _d, fs in os.walk(out_dir):
        for f in fs:
            if not f.endswith(".md") or f == "INDEX.md":
                continue
            p = os.path.join(r, f)
            txt = open(p).read()
            section, slt = split_sections(txt)
            if not is_prose(section):
                continue
            fm = frontmatter(txt)
            rec = {"path": os.path.relpath(p, out_dir), "body": section, "slt": slt,
                   "title": fm.get("title", ""), "used": False}
            if fm.get("old_code"):
                by_old[fm["old_code"]] = rec
            if fm.get("code"):
                by_code.setdefault(fm["code"], rec)
    return by_old, by_code


def assign_bodies(plan, by_old, by_code):
    """Map each planned element to an authored body from the previous tree.

    Two passes, strongest signal first: every `old_code` match is settled before any
    code match is considered. Single-pass matching mis-assigns whenever the planner
    renumbers a range — a weak code match can consume a file that a later element
    would have claimed on its stable `old_code`, cascading content under wrong titles.
    """
    claims = {}
    elements = [el for m in plan["modules"] for el in m["elements"]]

    for el in elements:
        rec = by_old.get(str(el.get("old") or ""))
        if el.get("old") and rec and not rec["used"]:
            rec["used"] = True
            claims[id(el)] = rec

    for el in elements:
        if id(el) in claims:
            continue
        rec = by_code.get(str(el["code"]))
        if rec and not rec["used"]:
            rec["used"] = True
            claims[id(el)] = rec

    return claims


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change; write nothing")
    args = ap.parse_args()

    plan = yaml.safe_load(open(PLAN))
    existing = {os.path.relpath(os.path.join(r, f), OUT)
                for r, _d, fs in os.walk(OUT) for f in fs
                if f.endswith(".md") and f != "INDEX.md"}
    planned = set()
    deferred = []
    by_old, by_code = harvest(OUT)   # read authored bodies BEFORE the tree is removed
    claims = assign_bodies(plan, by_old, by_code)
    migrations = []

    # Clear only the generated markdown. A blanket rmtree would also take the
    # course/<module>/assets/ image sets that migrated lesson bodies reference.
    assets = sum(len(fs) for r, _d, fs in os.walk(OUT) if os.path.basename(r) == "assets")
    if not args.dry_run:
        for r, _d, fs in os.walk(OUT):
            if os.path.basename(r) == "assets":
                continue
            for f in fs:
                if f.endswith(".md"):
                    os.remove(os.path.join(r, f))
        os.makedirs(OUT, exist_ok=True)

    manifest = ["# Course scaffold — element manifest",
                "", f"Generated from `plan/course-plan.yaml` ({plan['course']['title']}).",
                "Status: `live` = existing content maps in (graft from `compiled/.../<src>`); "
                "`new` = author from scratch. `*` = partial (consolidated source).", "",
                "| code | type | status | live src | title |", "|---|---|---|---|---|"]
    counts = {"live": 0, "new": 0, "partial": 0}

    for mod in plan["modules"]:
        mcode = mod["code"]
        mdir = os.path.join(OUT, MODULE_DIRNAMES.get(mcode, slug(mcode + "-" + mod["title"])))
        if not args.dry_run:
            os.makedirs(mdir, exist_ok=True)
        for el in mod["elements"]:
            code = str(el["code"])
            if el.get("deferred"):
                # deferred out of this build (plan/deferred.yaml): no file, so it is
                # never scaffolded, imported or shipped. Planner text stays in the yaml.
                deferred.append((code, el.get("title", ""), el.get("deferred_reason", "")))
                continue
            typ = el.get("type", "lesson")
            title = el.get("title") or f"({typ})"
            overview = el.get("overview", "")
            slts = el.get("slts", [])
            old = el.get("old", "")
            src = LIVE_MAP.get(code, "")
            partial = src.endswith("*")
            src_clean = src.rstrip("*")
            status = "new" if not src else ("partial" if partial else "live")
            counts["partial" if partial else ("live" if src else "new")] += 1

            fname = f"{code}-{slug(title)}.md"
            if typ == "assignment":
                fname = f"{code}-{slug(title) if title and not title.startswith('(') else 'assignment'}.assignment.md"

            carried = claims.get(id(el))
            if carried:
                migrations.append((carried["path"], os.path.join(
                    os.path.basename(mdir), fname), code, el.get("source", "none")))

            fm = [f'code: "{code}"', f'module: "{mcode} {mod["title"]}"',
                  f"type: {typ}", f'title: "{title}"', f"status: {status}"]
            if el.get("source"):
                fm.append(f'source: {el["source"]}')
            if carried:
                fm.append(f'migrated_from: "{carried["path"]}"')
            if src_clean:
                fm.append(f'live_source: "{src_clean}"   # graft from compiled/spo-online-business-academy/{src_clean}'
                          + ("  (PARTIAL — consolidated source)" if partial else ""))
            if old:
                fm.append(f'old_code: "{old}"')

            body = [f"---", *fm, "---", "", f"# {title}", ""]
            if overview:
                body += ["## Overview", "", overview, ""]
            if slts:
                body += ["## Student Learning Targets", ""]
                body += [f"{i+1}. {s}" for i, s in enumerate(slts)]
                body += [""]
            heading = "## Assignment" if typ == "assignment" else "## Content"
            if carried:
                # authored prose survives the rescaffold; the planner still owns the
                # title / overview / SLTs above, which are regenerated fresh. The body
                # brings its own headings (## Lesson, ## Content, …) so none is added.
                body += [carried["body"], ""]
                if carried["slt"] and not slts:
                    # planner has no SLTs for this element — keep the authored ones
                    body += [carried["slt"], ""]
            elif typ == "assignment":
                body += [heading, "",
                         "> TODO: author assignment brief and submission criteria." if not src
                         else f"> Graft assignment from live module {src_clean}.", ""]
            else:
                body += [heading, "",
                         ("> TODO: author content." if not src
                          else f"> Graft from live module {src_clean}"
                          + (" (PARTIAL — only part of this element lives there)." if partial else ".")), ""]

            planned.add(os.path.relpath(os.path.join(mdir, fname), OUT))
            if not args.dry_run:
                open(os.path.join(mdir, fname), "w").write("\n".join(body))
            manifest.append(f"| {code} | {typ} | {status} | {src_clean or '—'} | {title} |")

    manifest += ["", f"**Totals:** {counts['live']} live · {counts['partial']} partial · "
                 f"{counts['new']} new = {sum(counts.values())} elements."]

    migrated_paths = {m[0] for m in migrations}
    stranded = [r for r in list(by_old.values()) + list(by_code.values())
                if not r["used"] and r["path"] not in migrated_paths]
    stranded = sorted({r["path"]: r for r in stranded}.values(), key=lambda r: r["path"])

    if args.dry_run:
        kept = sorted(planned & existing)
        fresh = sorted(planned - existing)
        orphans = sorted(existing - planned)
        lost = [o for o in orphans if authored(os.path.join(OUT, o))
                and o not in migrated_paths]
        print(f"DRY RUN — nothing written\n")
        if deferred:
            print(f"  {len(deferred)} deferred, so no file is generated for them:")
            for c, t, r in deferred:
                print(f"     ~ {c} {t}" + (f"  ({r})" if r else ""))
            print()
        print(f"  {len(migrations)} authored bodies would be carried over:")
        for frm, to, code, source in migrations:
            note = "  (will be superseded by SPO narration)" if source == "spo" else ""
            arrow = "same path" if frm == to else to
            print(f"     {frm}\n        -> {arrow}{note}")
        if stranded:
            print(f"\n  {len(stranded)} authored bodies with NO home in the new plan:")
            for r in stranded:
                print(f"     !! {r['path']}  \"{r['title'][:44]}\"")
        print()
        print(f"  {len(planned)} elements in the plan")
        print(f"  {len(kept):3} unchanged paths (already in course/)")
        print(f"  {len(fresh):3} would be created")
        print(f"  {len(orphans):3} would be DELETED (no plan element produces them)")
        print(f"  {len(lost):3} of those hold authored prose\n")
        if lost:
            print("  authored files that a real run would destroy:")
            for o in lost:
                print(f"    !! {o}")
        moved = [o for o in orphans if o in migrated_paths]
        stubs = [o for o in orphans if o not in migrated_paths and o not in lost]
        if moved:
            print(f"  {len(moved)} orphaned paths whose content is carried to a new path above:")
            for o in moved:
                print(f"     ~ {o}")
        if stubs:
            print(f"\n  {len(stubs)} stub-only orphans (nothing to lose):")
            for o in stubs:
                print(f"     - {o}")
        if fresh:
            print(f"\n  new files ({len(fresh)}):")
            for f in fresh:
                print(f"     + {f}")
        return

    if migrations:
        manifest += ["", "## Migrated bodies", "",
                     "Authored prose carried across the planner's renames/renumbering "
                     "(matched on `old_code`, then code).", "",
                     "| from | to | code |", "|---|---|---|"]
        manifest += [f"| {frm} | {to} | {code} |" for frm, to, code, _s in migrations]
    if deferred:
        manifest += ["", "## Deferred", "",
                     "Carried in the planner but deliberately out of this build "
                     "(`plan/deferred.yaml`). No file is generated, so these are never "
                     "imported to Andamio. Undefer by removing the entry and re-running.", "",
                     "| code | title | reason |", "|---|---|---|"]
        manifest += [f"| {c} | {t} | {r or '—'} |" for c, t, r in deferred]
    if stranded:
        manifest += ["", "## Stranded bodies", "",
                     "Authored prose with no element in the current plan — **not** carried "
                     "over. Recover from git history if the planner regains a home for it.", ""]
        manifest += [f"- `{r['path']}` — {r['title']}" for r in stranded]

    open(os.path.join(OUT, "INDEX.md"), "w").write("\n".join(manifest) + "\n")
    print(f"Scaffolded {sum(counts.values())} elements: "
          f"{counts['live']} live, {counts['partial']} partial, {counts['new']} new")
    if deferred:
        print(f"Deferred {len(deferred)} elements (no file generated)")
    print(f"Migrated {len(migrations)} authored bodies; {len(stranded)} stranded"
          + (" (listed in course/INDEX.md)" if stranded else ""))


if __name__ == "__main__":
    main()
