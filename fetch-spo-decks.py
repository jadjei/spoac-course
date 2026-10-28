#!/usr/bin/env python3
"""Download the SPO-flavour decks that the current Course Planner links to.

The planner's **column G** ("SPO Overview FIlename") holds one `=HYPERLINK()` per
lesson row pointing at that lesson's `_SPO` deck. Those decks are the authoring
source: the narration that becomes the lesson body lives in their **speaker notes**
(there are no separate `__N` narration decks any more).

The decks live in the *shared drive*, so they must be fetched with a remote that can
see it (`gdsa:` / `gdwrite:`). The personal `gdrive:` remote 404s on these ids — that
is what silently broke the 2026-06-11 pull.

Before resolving anything it re-lists the shared drive, because the listing is what
goes stale: Harry saves a deck and every script downstream stays blind to it until the
next snapshot. M207 sat unseen for exactly that reason, saved twenty minutes after the
snapshot that missed it.

The freshness check is scoped to the decks the planner links. Everything else that
moved in Drive is listed, because one recursive call is cheaper than dozens, but it is
not reported and not acted on — an unlinked deck changing is not this script's business.

Usage:
    python3 fetch-spo-decks.py                      # re-list, then fetch + verify
    python3 fetch-spo-decks.py --dry-run
    python3 fetch-spo-decks.py --no-refresh         # trust the newest snapshot on disk

Requires: rclone (remote `gdsa:`), openpyxl.
"""
import argparse, glob, hashlib, json, os, re, subprocess, sys
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
PLANNER = os.path.join(HERE, "spoac-dl/planner/current/SPOAC Course Planner.xlsx")
LISTINGS = os.path.join(HERE, "spoac-dl")
DEST = os.path.join(HERE, "spoac-dl/spo-decks")
REMOTE = "gdsa:"
# The planner links into two trees. Most rows point at the shared drive; module 100 and
# the 300 overview point at the General tree, which is shared with the service account
# rather than living in the shared drive. Both are planner-linked, so both are checked.
TREES = [
    ("drive-listing", ["rclone", "lsjson", "-R", "--files-only", "--hash",
                       "gdwrite:Course Content"], os.path.join(HERE, "spoac-dl/spo-decks")),
    ("general-listing", ["rclone", "lsjson", "-R", "--files-only", "--hash",
                         "--drive-root-folder-id", "1Bqt2bsmaM4jBmiP_UhYAbLvEw0ZdVTLV",
                         "gdsa:"], os.path.join(HERE, "spoac-dl/general-decks")),
]


def newest_listing(prefix):
    found = sorted(glob.glob(os.path.join(LISTINGS, f"{prefix}-*.json")))
    return found[-1] if found else None


def refresh(prefix, cmd):
    """Re-list one tree and keep it as today's snapshot.

    Suffixed a, b, c… when the day already has one, so the sequence stays readable and
    `newest_listing()` still picks the latest.
    """
    import datetime, string
    day = datetime.date.today().isoformat()
    for suffix in [""] + list(string.ascii_lowercase[1:]):
        path = os.path.join(LISTINGS, f"{prefix}-{day}{suffix}.json")
        if not os.path.exists(path):
            break
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(f"  ! could not re-list {prefix}: {(r.stderr.strip().splitlines() or [''])[-1]}")
        return newest_listing(prefix)
    open(path, "w").write(r.stdout)
    return path


def spo_column(ws, header_row=7):
    """The column headed "SPO Overview FIlename", found rather than assumed.

    It has been column G and is now column F: deleting the General filename column
    shifted everything after it. Reading by letter silently pointed this at Snagging,
    and every fetch failed with ids that were not in the listing.
    """
    for c in range(1, ws.max_column + 1):
        h = re.sub(r"\s+", " ", str(ws.cell(header_row, c).value or "")).strip().lower()
        if h == "spo overview filename":
            return openpyxl.utils.get_column_letter(c)
    sys.exit(f"no 'SPO Overview FIlename' header in row {header_row} of the planner")


def planner_links(path, column=None):
    """(cell, label, drive_id) for every =HYPERLINK() formula in the SPO column."""
    import openpyxl
    ws = openpyxl.load_workbook(path)["SPO Academy Modules"]
    column = column or spo_column(ws)
    out = []
    for row in ws.iter_rows():
        for c in row:
            if not c.coordinate.startswith(column):
                continue
            v = str(c.value or "")
            for target in re.findall(r'HYPERLINK\("([^"]+)"', v):
                m = re.search(r"/d/([A-Za-z0-9_-]{20,})", target)
                if not m:
                    continue
                label = re.findall(r'","([^"]*)"\)', v)
                out.append((c.coordinate, label[0] if label else "", m.group(1)))
    return out


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-refresh", action="store_true",
                    help="skip the Drive re-list and trust the newest snapshot on disk")
    args = ap.parse_args()

    before, byid = {}, {}
    for prefix, cmd, dest in TREES:
        prior = newest_listing(prefix)
        if prior:
            before.update({f.get("ID"): f.get("Hashes", {}).get("md5")
                           for f in json.load(open(prior))})
        listing = prior if args.no_refresh else refresh(prefix, cmd)
        if not listing:
            continue
        for f in json.load(open(listing)):
            byid[f.get("ID")] = (f, dest)
        print(f"{'using' if args.no_refresh else 'listed'} {os.path.basename(listing)}")

    links = planner_links(PLANNER)
    if not args.no_refresh:
        # only the decks the planner points at: everything else that moved in Drive is
        # listed because one recursive call is cheaper than dozens, and then ignored
        moved = [fid for _c, _l, fid in links
                 if fid in byid and before.get(fid) != byid[fid][0].get("Hashes", {}).get("md5")]
        fresh = [fid for _c, _l, fid in links if fid not in before]
        print(f"  planner-linked: {len(moved)} changed, {len(fresh)} newly linked")
    print(f"{len(links)} SPO links in the planner\n")

    ok = skipped = failed = 0
    for cell, label, fid in links:
        entry = byid.get(fid)
        if not entry:
            print(f"  ✗ {cell} {label} — id {fid} in neither tree")
            failed += 1
            continue
        meta, dest = entry
        out = os.path.join(dest, meta["Path"])
        want = meta.get("Hashes", {}).get("md5")
        if os.path.exists(out) and want and md5(out) == want:
            print(f"  = {meta['Path']}")
            skipped += 1
            continue
        if args.dry_run:
            print(f"  → would fetch {meta['Path']} ({meta['Size']/1e6:.1f} MB)")
            continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        r = subprocess.run(["rclone", "backend", "copyid", REMOTE, fid, out],
                           capture_output=True, text=True)
        got = md5(out) if os.path.exists(out) else None
        if r.returncode or (want and got != want):
            print(f"  ✗ {meta['Path']} — {r.stderr.strip().splitlines()[-1:] or 'md5 mismatch'}")
            failed += 1
        else:
            print(f"  ✓ {meta['Path']} ({meta['Size']/1e6:.1f} MB)")
            ok += 1

    print(f"\nfetched {ok}, already current {skipped}, failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
