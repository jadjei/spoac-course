#!/usr/bin/env python3
"""Report what still blocks the course: missing sources, and cross-course wording.

Two checks, both regenerated from the planner and the current Drive listings:

1. **Content gaps.** Every element the planner defines but nothing covers stays a stub —
   the source-precedence rule forbids inventing content for it. This turns that set into
   something chaseable: per element, what the planner already specifies, and whether any
   older material or other-flavour deck exists that Harry could work from.

   A deck is not the only way an element can be covered. Videos are delivered on YouTube
   and assignments in the Playbook Builder, and the planner now records both as links in
   the same columns that hold deck filenames. Counting those elements as gaps because
   they have no deck said the course was less finished than it is — 8 videos and 8
   assignments were being reported as missing while they were live. They are counted as
   covered here, and their links are checked rather than taken on trust.

2. **Cross-course language.** The course ships in three flavours built from shared
   material, so another flavour's branding travels with its decks. Anything in `course/`
   is serious — it reaches the platform. Anything in an extracted deck is advisory, and
   becomes live the moment that deck is linked in the planner.

Re-run after any `fetch-spo-decks.py` + `plan-from-planner.py` cycle; the list shrinks
as decks land.

Usage:
    python3 gap-report.py                 # writes plan/content-gaps.md
    python3 gap-report.py --stdout
    python3 gap-report.py --docs          # also publish to the Docusaurus site
    python3 gap-report.py --no-check-links  # skip the artefact link checks (offline)
"""
import argparse, glob, json, os, re, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(HERE, "plan", "course-plan.yaml")
OUT = os.path.join(HERE, "plan", "content-gaps.md")
# newest lsjson snapshot of each tree — a deck added after the last snapshot is
# invisible otherwise, which would report a gap that has actually been filled
LISTINGS = {
    "shared drive (SPO tree)": sorted(glob.glob(
        os.path.join(HERE, "spoac-dl/drive-listing-*.json")))[-1],
    "General tree": sorted(glob.glob(
        os.path.join(HERE, "spoac-dl/general-listing-*.json")))[-1],
}
COMPILED = os.path.join(HERE, "compiled", "spo-online-business-academy")
# the public docs site (GitLab Pages) — see --docs
DOCS_DEFAULT = os.path.abspath(os.path.join(
    HERE, "..", "spoacademydocs", "docs", "course", "content-gaps.md"))
COURSE = os.path.join(HERE, "course")


def planner_date():
    """The planner date recorded in the generated plan — never hardcode it here."""
    m = re.search(r"modified (\d{4}-\d{2}-\d{2})", open(PLAN).read())
    return m.group(1) if m else "unknown-date"


# Wording that belongs to a different course flavour. Harry authors three flavours from
# shared material, so the General and Developer-Accelerator decks carry their own branding —
# and module 100 plus the 300 overview legitimately draw on General decks, which is exactly
# how such wording reaches an SPO lesson. Extend this list as other flavours appear.
FOREIGN_MARKERS = [
    (re.compile(r"dev(eloper)?[\s-]?accelerator", re.I),
     "Developer Accelerator Academy — a different Andamio course; re-aim at SPOs"),
]

EXTRACTED = os.path.join(HERE, "extracted")


def extracted_for(deck_rel):
    """The extracted markdown mirroring a deck path recorded in the plan.

    extract.py mirrors its --src root, so `spoac-dl/spo-decks/300/x.pptx` extracts to
    `extracted/300/x.pptx.md`, while the General tree keeps its own prefix.
    """
    for prefix, keep in (("spoac-dl/spo-decks/", ""),
                         ("spoac-dl/general-decks/", "general-decks/")):
        if deck_rel.startswith(prefix):
            return os.path.join(EXTRACTED, keep + deck_rel[len(prefix):] + ".md")
    return None


def foreign_language(plan):
    """(shipped, source) hits for wording belonging to another course flavour.

    `shipped` is the serious one: it is in course/ and therefore reaches the platform.
    `source` is advisory — the wording sits in a deck an element draws on, so it could
    arrive on the next narration pass even though nothing is wrong today.
    """
    shipped, source = [], []
    for f in sorted(glob.glob(os.path.join(COURSE, "*", "*.md"))):
        txt = open(f, encoding="utf-8", errors="replace").read()
        code = (re.search(r'^code:\s*"([^"]+)"', txt, re.M) or [None, "?"])[1]
        for n, line in enumerate(txt.splitlines(), 1):
            for rx, note in FOREIGN_MARKERS:
                if rx.search(line):
                    shipped.append((code, os.path.relpath(f, HERE), n, line.strip()[:90], note))

    # Every extracted deck, not only the linked ones: a deck carrying another flavour's
    # branding is a hazard the moment someone links it in the planner, and saying "linked to
    # X" vs "not linked" is what tells you whether it is urgent or just worth knowing.
    linked = {}
    for m in plan["modules"]:
        for el in m["elements"]:
            for deck in (el.get("spo_decks") or []) + (el.get("general_decks") or []):
                ex = extracted_for(deck)
                if ex:
                    linked[os.path.abspath(ex)] = str(el["code"])

    for ex in sorted(glob.glob(os.path.join(EXTRACTED, "**", "*.md"), recursive=True)):
        txt = open(ex, encoding="utf-8", errors="replace").read()
        for rx, note in FOREIGN_MARKERS:
            hits = len(rx.findall(txt))
            if hits:
                source.append((linked.get(os.path.abspath(ex)),
                               os.path.relpath(ex, EXTRACTED), hits, note))
    return shipped, source


def bodies():
    """Element code -> True when course/ already holds prose for it (older material)."""
    out = {}
    for f in glob.glob(os.path.join(COURSE, "*", "*.md")):
        txt = open(f).read()
        m = re.search(r'^code:\s*"([^"]+)"', txt, re.M)
        if not m:
            continue
        words = 0
        for sec in re.split(r"^## +", txt.split("---", 2)[-1], flags=re.M)[1:]:
            if sec.splitlines()[0].strip().lower().startswith(("overview", "student learning")):
                continue
            words += sum(len(l.split()) for l in sec.splitlines()[1:]
                         if l.strip() and not l.strip().startswith((">", "#")))
        out[m.group(1)] = words > 25
    return out


def covered(el):
    """True when something exists behind this element: a deck, a video, or a brief.

    `source` only ever speaks about decks, so an element with no deck can still be
    delivered — read the artefact links before calling anything a gap.
    """
    return ((el.get("source") or "none") != "none"
            or bool(el.get("video_url")) or bool(el.get("playbook_url")))


def artefacts(plan):
    """(module, element, kind, url) for every element delivered outside the deck pipeline."""
    out = []
    for m in plan["modules"]:
        for el in m["elements"]:
            if el.get("video_url"):
                out.append((m, el, "video", el["video_url"]))
            if el.get("playbook_url"):
                out.append((m, el, "assignment", el["playbook_url"]))
    return out


def check_video(url):
    """Ask YouTube's oEmbed endpoint whether the video is actually watchable.

    Fetching the watch page proves nothing — it answers 200 for videos that have been
    made private or removed. oEmbed answers 401/404 for exactly those.
    """
    import urllib.parse, urllib.request
    q = urllib.parse.urlencode({"url": url, "format": "json"})
    try:
        with urllib.request.urlopen(
                f"https://www.youtube.com/oembed?{q}", timeout=10) as r:
            title = json.load(r).get("title", "")
        return True, f"live — “{title[:48]}”"
    except urllib.error.HTTPError as e:
        return False, ("private or removed" if e.code in (401, 403)
                       else "no such video" if e.code == 404 else f"HTTP {e.code}")
    except Exception as e:                                    # offline, DNS, timeout
        return None, f"not checked ({type(e).__name__})"


def check_playbook(url, plan):
    """The page must answer, and its `#module-NNN` anchor must name a module that has
    an assignment. The Builder resolves that anchor in the browser, so the served HTML
    cannot confirm it — the planner can, and a wrong anchor is the realistic error."""
    import urllib.request
    frag = url.partition("#")[2]
    mod = frag[len("module-"):] if frag.startswith("module-") else frag
    known = {m["code"] for m in plan["modules"]
             for el in m["elements"] if el.get("type") == "assignment"}
    if mod and mod not in known:
        return False, f"anchor `#{frag}` names no module with an assignment"
    try:
        req = urllib.request.Request(url.partition("#")[0], method="GET",
                                     headers={"User-Agent": "gap-report"})
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return None, f"not checked ({type(e).__name__})"
    return (code == 200), (f"page 200, opens module {mod}" if code == 200
                           else f"HTTP {code}")


def load_listings():
    out = []
    for label, path in LISTINGS.items():
        if os.path.exists(path):
            for f in json.load(open(path)):
                out.append((label, f["Path"], f.get("ModTime", "")[:10]))
    return out


def candidates(el, listings):
    """Existing files that plausibly cover this element: by planner code or legacy M-code."""
    code, old = str(el["code"]), str(el.get("old") or "")
    keys = [code]
    if old:
        keys.append(old)
        keys.append(old.replace("M", "M"))
    hits = []
    for label, path, mod in listings:
        base = os.path.basename(path)
        if not base.lower().endswith((".pptx", ".docx")):
            continue
        for k in keys:
            # a trailing '.' must not match either, or every child deck (M301.6…)
            # looks like material for its parent (301)
            if re.search(rf"(?<![\d.]){re.escape(k)}(?![\d.])", base):
                hits.append((label, path, mod))
                break
    # newest first, keep it short
    return sorted({h[1]: h for h in hits}.values(), key=lambda h: h[2], reverse=True)[:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--no-check-links", action="store_true",
                    help="skip the YouTube and Playbook Builder checks (offline runs)")
    ap.add_argument("--docs", metavar="PATH", nargs="?", const=DOCS_DEFAULT,
                    help="also publish to the Docusaurus site (default: %(default)s)"
                         if False else "also write the docs-site page (default: "
                         + os.path.relpath(DOCS_DEFAULT, HERE) + ")")
    args = ap.parse_args()

    plan = yaml.safe_load(open(PLAN))
    listings = load_listings()
    live = set(os.listdir(COMPILED)) if os.path.isdir(COMPILED) else set()
    has_body = bodies()

    deferred = [(m, el) for m in plan["modules"] for el in m["elements"]
                if el.get("deferred")]
    gaps = [(m, el) for m in plan["modules"] for el in m["elements"]
            if not covered(el) and not el.get("deferred")]
    have = sum(1 for m in plan["modules"] for el in m["elements"] if covered(el))
    links = artefacts(plan)
    checked = {}
    if not args.no_check_links:
        for _m, _el, kind, url in links:
            if url not in checked:
                checked[url] = (check_video(url) if kind == "video"
                                else check_playbook(url, plan))

    L = ["# Content gaps — elements with nothing behind them yet",
         "",
         f"Generated by `gap-report.py` from the {planner_date()} planner. "
         f"**{have} of {have + len(gaps)} elements are covered** — by a current deck, a "
         f"YouTube video or a Playbook Builder brief. "
         f"**The {len(gaps)} below {'is' if len(gaps) == 1 else 'are'} not** — of those, "
         f"{sum(1 for _m, e in gaps if has_body.get(str(e['code'])))} still carry older "
         f"prose (migrated or grafted) and "
         f"{sum(1 for _m, e in gaps if not has_body.get(str(e['code'])))} "
         f"{'is an empty stub' if sum(1 for _m, e in gaps if not has_body.get(str(e['code']))) == 1 else 'are empty stubs'}.",
         "",
         "These are blocked on source material, not on build work: the source-precedence "
         "rule keeps them as stubs rather than inventing content. Each row shows what the "
         "planner already specifies (so Harry isn't starting cold) and the closest existing "
         "material found in Drive.",
         "",
         "`spec` — planner already provides: **O**verview, **S**LTs, **T**itle only.",
         ""]

    if links:
        n_v = sum(1 for *_x, k, _u in links if k == "video")
        n_a = len(links) - n_v
        bad = [u for u, (ok, _n) in checked.items() if ok is False]
        L += ["", "## Delivered outside the deck pipeline", "",
              f"{n_v} videos and {n_a} assignments, linked from the planner rather than "
              "sourced from a deck. These are not gaps and are not counted as such.",
              ""]
        L += ["Every link below was checked when this report ran"
              + (f" — **{len(bad)} did not answer**." if bad else ", and all answered.")
              if checked else "Link checking was skipped for this run "
              "(`--no-check-links`).", ""]
        L += ["| code | element | type | link | checked |", "|---|---|---|---|---|"]
        for _m, el, kind, url in links:
            ok, note = checked.get(url, (None, "not checked"))
            mark = {True: "✅", False: "❌", None: "—"}[ok]
            L += [f"| {el['code']} | {str(el.get('title', ''))[:34]} | {kind} | "
                  f"[{url.replace('https://', '')}]({url}) | {mark} {note} |"]
        L += [""]

    # A module's own row carries both its video link and its overview deck. The two
    # share column G, so pasting one over the other loses the deck silently: the module
    # still counts as covered by its video while the introduction body it narrates has
    # no source. Checked directly rather than by title matching, which misses any module
    # whose deck is named differently from its element title.
    no_overview = [(m, el) for m in plan["modules"] for el in m["elements"]
                   if el["code"] == m["code"] and (el.get("source") or "none") == "none"
                   and not el.get("deferred")]
    if no_overview:
        L += ["", "## Module introductions with no overview deck", "",
              "These modules are covered by a video, so they are not gaps — but the "
              "introduction on the platform is narrated from the module's overview deck, "
              "and column G no longer points at one. Worth confirming the video link was "
              "added alongside the deck link rather than over it.", "",
              "| module | element | has | overview deck in Drive |", "|---|---|---|---|"]
        for m, el in no_overview:
            # the module's own deck is either named for its code (M500_…) or sits in an
            # overview folder under it — the naming is not consistent across modules
            near = [p for _lab, p, _mod in listings
                    if p.endswith("_SPO.pptx")
                    and (os.path.basename(p).startswith(f"M{m['code']}_")
                         or (p.startswith(f"{m['code']}/") and "overview" in p.lower()))]
            L += [f"| {m['code']} | {str(el.get('title', ''))[:34]} | "
                  f"{'video link only' if el.get('video_url') else 'nothing'} | "
                  + (f"`{os.path.basename(near[0])}`" if near else "none found") + " |"]
        L += [""]

    by_type = {}
    for _m, el in gaps:
        by_type[el.get("type", "lesson")] = by_type.get(el.get("type", "lesson"), 0) + 1
    L += ["| by type | count |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in sorted(by_type.items(), key=lambda x: -x[1])]
    L += [""]

    cur = None
    for m, el in gaps:
        if m["code"] != cur:
            cur = m["code"]
            L += ["", f"## {m['code']} {m['title']}", "",
                  "| code | element | type | spec | in course/ now | existing material |",
                  "|---|---|---|---|---|---|"]
        spec = ("O" if el.get("overview") else "") + ("S" if el.get("slts") else "")
        spec = spec or "T"
        cands = candidates(el, listings)
        if cands:
            what = "<br />".join(f"`{os.path.basename(p)[:52]}` ({lab}, {mod})"
                               for lab, p, mod in cands)
        elif el.get("named_deck"):
            what = (f"planner names `{el['named_deck'][:52]}` in column G, but no such "
                    "file is in Drive — named, not built")
        elif str(el["code"]) in live:
            what = f"live Andamio module `{el['code']}` only (oldest material)"
        else:
            what = "**nothing found**"
        state = "older prose" if has_body.get(str(el["code"])) else "**empty**"
        L += [f"| {el['code']} | {el.get('title', '')[:44]} | {el.get('type', '')} | "
              f"{spec} | {state} | {what} |"]

    shipped_foreign, source_foreign = foreign_language(plan)
    L += ["", "## Cross-course language", "",
          "The course ships in three flavours from shared material, so wording from another "
          "flavour can travel with a deck. Anything below names a different course and should "
          "read as SPO Academy content instead.", ""]
    if shipped_foreign:
        L += [f"**{len(shipped_foreign)} in authored content — these reach the platform.**", "",
              "| code | file | line | text |", "|---|---|---|---|"]
        L += [f"| {c} | `{f}` | {n} | {t} |" for c, f, n, t, _note in shipped_foreign]
        L += [""]
    else:
        L += ["**Nothing in `course/` — no cross-course wording currently reaches the "
              "platform.**", ""]
    if source_foreign:
        n_linked = sum(1 for c, *_ in source_foreign if c)
        L += [f"Advisory: {len(source_foreign)} source deck(s) carry it. "
              + (f"**{n_linked} of them are linked to an element**, so it could arrive on the "
                 "next narration pass — cut it when mapping."
                 if n_linked else
                 "None is currently linked to an element, so nothing pulls it in today — but "
                 "linking one in the planner would."), "",
              "| deck | linked to | hits | what it is |", "|---|---|---|---|"]
        L += [f"| `{d}` | {c or '— not linked —'} | {h} | {note} |"
              for c, d, h, note in source_foreign]
        L += [""]

    if deferred:
        L += ["", "## Deferred — not counted as gaps", "",
              "Kept in the planner but deliberately out of this build, so they need no "
              "deck and block nothing. Listed here so the decision stays visible.", "",
              "| code | title | reason |", "|---|---|---|"]
        L += [f"| {el['code']} | {el.get('title','')[:44]} | "
              f"{el.get('deferred_reason','') or '—'} |" for _m, el in deferred]
        L += [""]

    L += ["", "## What would close these", "",
          "- **Assignments and videos** — never had decks and never will. They are closed "
          "by a brief in the Playbook Builder or a video on YouTube, linked from the "
          "planner; the table above lists the ones already delivered.",
          "- **Lessons** — need an `_SPO` deck linked from column G of the planner. Once "
          "linked, `fetch-spo-decks.py` → `plan-from-planner.py` → `scaffold.py` → "
          "`map-narration.py` picks them up in one pass (~10 min end to end).",
          "- **Already-built decks that are simply unlinked** are the cheapest win: see below.",
          ""]

    # SPO decks that exist in Drive but no planner column-G link points at them
    linked = {os.path.basename(d) for m in plan["modules"] for el in m["elements"]
              for d in (el.get("spo_decks") or [])}
    unlinked = sorted({p for lab, p, _mod in listings
                       if lab.startswith("shared") and p.endswith("_SPO.pptx")
                       and os.path.basename(p) not in linked})
    if unlinked:
        L += ["### Built but not linked in the planner", "",
              "These `_SPO` decks exist in Drive and are ready to use — they are just not "
              "referenced from column G, so nothing downstream can see them. Linking them "
              "is a spreadsheet edit.", ""]
        import difflib
        # Match against every element, not only the gaps. An element covered by a video
        # still draws its lesson body from a deck, so a displaced deck link is a real
        # loss even though nothing counts as a gap — matching gaps alone hides it.
        every = [(m, el) for m in plan["modules"] for el in m["elements"]
                 if not el.get("deferred")]
        hits = 0
        for p in unlinked:
            stem = re.sub(r"^M[\d.\-]+_|_SPO\.pptx$", " ", os.path.basename(p))
            stem = stem.replace("_", " ").strip().lower()
            best, score = None, 0.0
            for _m, el in every:
                r = difflib.SequenceMatcher(None, stem, str(el.get("title", "")).lower()).ratio()
                if r > score:
                    best, score = el, r
            if score > 0.6:
                hits += 1
                if not covered(best):
                    state = "older prose" if has_body.get(str(best["code"])) else "empty"
                    hint = (f"  → likely covers **{best['code']} {best['title']}**, "
                            f"currently a gap ({state})")
                elif best.get("type") == "assignment":
                    hint = (f"  → title matches {best['code']} {best['title']}, an "
                            "assignment — those are delivered as briefs, so nothing is "
                            "missing here")
                elif (best.get("source") or "none") == "none":
                    hint = (f"  → **{best['code']} {best['title']}** has only a "
                            f"{'video' if best.get('video_url') else 'brief'} link in "
                            "column G — the deck link looks displaced rather than dropped")
                else:
                    hint = (f"  → {best['code']} {best['title']} already has a deck; this "
                            "one looks superseded")
            else:
                hint = "  → no element in the planner is waiting for it"
            L += [f"- `{os.path.basename(p)}` — `{os.path.dirname(p)}`", hint]
        L += ["",
              (f"{hits} of the {len(unlinked)} match an element by title. Where the match "
               "is a gap, linking the cell closes it with no authoring; where the element "
               "already carries a video link, check whether the deck link was overwritten."
               if hits else
               "None matches an element by title, so none of these is a one-cell fix — "
               "they are spare material rather than missing links."), ""]

    text = "\n".join(L) + "\n"
    if args.stdout:
        print(text)
        return 0

    open(OUT, "w").write(text)
    print(f"{len(gaps)} gaps → {os.path.relpath(OUT, HERE)}")
    if unlinked:
        print(f"{len(unlinked)} built-but-unlinked SPO decks flagged")

    if args.docs:
        # Same body, published to the public docs site. Docusaurus needs frontmatter, and
        # the page says plainly that it is generated so nobody edits it there by hand.
        # `unlisted` keeps the page reachable by URL while excluding it from the sidebar,
        # the search index and the sitemap. It is a working document — useful to the team
        # in a browser, not something to advertise from the site's navigation.
        page = ["---", "title: Content Gaps", "unlisted: true", "---", "",
                "> Working document, generated from the planner and the current Drive "
                "listings. Not linked from the site navigation. Edit the planner and "
                "re-run the report rather than editing this page.", ""]
        # drop the report's own H1 — Docusaurus renders the frontmatter title as the heading
        page.append(text.split("\n", 1)[1].lstrip("\n"))
        os.makedirs(os.path.dirname(args.docs), exist_ok=True)
        open(args.docs, "w").write("\n".join(page))
        print(f"published → {args.docs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
