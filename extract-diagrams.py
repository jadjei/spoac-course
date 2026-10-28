#!/usr/bin/env python3
"""Produce a diagram-only source file per figure, for overlay on themed backgrounds.

The course ships in three flavours, so figures need to be the artwork alone — no deck
background, no title bar, no Edify branding — ready to composite onto whatever
background a flavour uses.

The right source differs per slide, so this picks per slide:

  picture       The diagram *is* an embedded image. Export the original bytes straight
                out of the pptx: no slide background, no recompression, native
                resolution. Raster, because the source always was.
  native        No embedded image — real vector geometry. The deck is copied and that
                slide stripped to its artwork (master graphics hidden, white background),
                then rendered: vector out, nothing behind it.

Every figure is written twice: a `.svg` master for theming and a `.png` beside it, from
the *same* render. Andamio's CDN rejects SVG, so the lesson references the PNG.

Slides carrying both an image and vector shapes are treated as `picture`. Cropping the
rendered slide to a bounding box was tried first and is wrong: the decks put their body
text in autoshapes rather than text boxes, so the box spans the whole slide and drags
in the background, page number and audio glyph. On those slides the embedded image is
the diagram, and the surrounding vector shapes are the deck's own commentary — which a
flavour will re-add in its own styling anyway.

Bounding boxes come from the pptx shape geometry (EMU), converted to the PDF's point
space, and applied to the SVG by rewriting its viewBox — pdftocairo ignores -x/-W crop
flags when the output is SVG.

Backgrounds are chosen per figure, not fixed. Most artwork is dark-on-light and wants
white; some slides draw white text and pale strokes straight onto the deck's dark field,
and forcing white erases them (700 slides 3 and 7 came out ~8% visible — effectively
blank). `--bg auto` renders on white, measures what reads against the background, and
re-renders keeping the deck's own fill when almost nothing does. The choice per figure is
recorded in course/.figure-backgrounds.json and shown in svg-review.py.

Usage:
    python3 extract-diagrams.py --dry-run
    python3 extract-diagrams.py
    python3 extract-diagrams.py --code 700 --bg deck    # force one figure either way
"""
import argparse, collections, glob, json, os, re, shutil, subprocess, sys
import yaml
from pptx import Presentation
from pptx.util import Emu
from pptx.dml.color import RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(HERE, "plan", "course-plan.yaml")
COURSE = os.path.join(HERE, "course")
TMP = os.path.join(HERE, "spoac-dl", "pdf-tmp")
PNG_DPI = 150            # raster companion for the SVG master; see render_png
SOFFICE = ["flatpak-spawn", "--host", "flatpak", "run", "org.libreoffice.LibreOffice"]

from pptx.enum.shapes import MSO_SHAPE_TYPE
VECTOR = {MSO_SHAPE_TYPE.GROUP, MSO_SHAPE_TYPE.FREEFORM, MSO_SHAPE_TYPE.CHART,
          MSO_SHAPE_TYPE.TABLE, MSO_SHAPE_TYPE.AUTO_SHAPE}


def shape_type(sh):
    try:
        return sh.shape_type
    except Exception:
        return None


def classify(slide):
    """Kind of figure, or None when the slide has no diagram worth extracting.

    Must agree with map-narration.py's figure rule, or this emits files no lesson
    references (and, worse, leaves referenced ones missing).
    """
    pics = [sh for sh in slide.shapes if shape_type(sh) == MSO_SHAPE_TYPE.PICTURE]
    vecs = [sh for sh in slide.shapes if shape_type(sh) in VECTOR]
    strong = [sh for sh in vecs if shape_type(sh) != MSO_SHAPE_TYPE.AUTO_SHAPE]
    autos = [sh for sh in vecs if shape_type(sh) == MSO_SHAPE_TYPE.AUTO_SHAPE]
    if not (pics or strong or len(autos) >= 4):
        return None, pics, vecs
    if pics:
        return "picture", pics, vecs      # incl. image + vector commentary
    return "native", pics, vecs


def diagram_shapes(slide):
    """Artwork shapes only — drop titles, body text and the small footer furniture."""
    out = []
    for sh in slide.shapes:
        st = shape_type(sh)
        if st is None or st == MSO_SHAPE_TYPE.PLACEHOLDER:
            continue
        if st == MSO_SHAPE_TYPE.TEXT_BOX:
            continue
        out.append(sh)
    return out


def foreground(shapes, size, share=0.6):
    """Drop slide-spanning shapes — the background panel and the white content card.

    Their bbox is what drags the deck's own body text into a cropped figure. Anything
    covering more than `share` of the slide is furniture, not artwork. Falls back to the
    full set when that leaves nothing (a genuinely full-bleed diagram).
    """
    sw, sh_ = size
    limit = share * (sw or 1) * (sh_ or 1)
    small = [s for s in shapes if (s.width or 0) * (s.height or 0) < limit]
    return small or shapes


def bbox(shapes):
    xs = [s.left for s in shapes if s.left is not None]
    ys = [s.top for s in shapes if s.top is not None]
    x2 = [s.left + (s.width or 0) for s in shapes if s.left is not None]
    y2 = [s.top + (s.height or 0) for s in shapes if s.top is not None]
    if not xs:
        return None
    return min(xs), min(ys), max(x2), max(y2)


def soffice(fmt, src, outdir):
    os.makedirs(outdir, exist_ok=True)
    r = subprocess.run(SOFFICE + ["--headless", "--convert-to", fmt, "--outdir", outdir, src],
                       capture_output=True, text=True, timeout=600)
    m = re.search(r"-> (\S.*?) using filter", r.stdout)
    return m.group(1).strip() if m else None


def render_png(src_pdf, page, root, box_pt, pad=6, dpi=PNG_DPI):
    """Render the same figure to PNG beside the SVG.

    Andamio's CDN rejects SVG — verified 2026-07-29 against `/api/upload`, which
    answers `INVALID_TYPE` for anything outside PNG/JPG/GIF/WebP, and the same
    allow-list is enforced client-side by the CLI. So the SVG stays as the themable
    master and the lesson references this raster. pdftocairo's crop flags are in
    pixels at the output resolution, unlike crop_svg's points.
    """
    cmd = ["pdftocairo", "-png", "-singlefile", "-r", str(dpi),
           "-f", str(page), "-l", str(page)]
    if box_pt:
        x0, y0, x1, y1 = box_pt
        x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
        px = lambda v: max(1, round(v * dpi / 72))
        cmd += ["-x", str(px(x0)), "-y", str(px(y0)),
                "-W", str(px((x1 - x0) + pad)), "-H", str(px((y1 - y0) + pad))]
    subprocess.run(cmd + [src_pdf, root], check=True)


def crop_svg(path, box_pt, pad=6):
    """Clip an SVG to a box in points by rewriting the root viewBox."""
    txt = open(path).read()
    x0, y0, x1, y1 = box_pt
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    w, h = (x1 - x0) + pad, (y1 - y0) + pad
    txt = re.sub(r'(<svg[^>]*?)viewBox="[^"]*"', rf'\1viewBox="{x0:.1f} {y0:.1f} {w:.1f} {h:.1f}"',
                 txt, count=1)
    txt = re.sub(r'(<svg[^>]*?)width="[^"]*"', rf'\1width="{w:.1f}pt"', txt, count=1)
    txt = re.sub(r'(<svg[^>]*?)height="[^"]*"', rf'\1height="{h:.1f}pt"', txt, count=1)
    open(path, "w").write(txt)


def visible_share(png):
    """Share of pixels that stand out from the image's own background colour.

    Not the same as ink: ink counts non-white pixels, so a dark background scores ~100%
    while telling you nothing. This takes the modal colour as the background and measures
    what reads *against* it — which is what "did the artwork survive" actually means, and
    works whether the figure is dark-on-light or light-on-dark.
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(png).convert("RGB").resize((150, 150))
    except Exception:
        return None
    px = list(im.getdata())
    modal = collections.Counter(px).most_common(1)[0][0]
    return sum(1 for p in px if sum(abs(a - b) for a, b in zip(p, modal)) > 60) / len(px)


def stripped_deck(deck_abs, index, dest, bg="white"):
    """A copy of the deck with slide `index` reduced to its artwork alone.

    Deletes everything on that slide except the foreground artwork, hides the master's
    background graphics (`showMasterSp="0"` — PowerPoint's "hide background graphics"),
    and forces a white slide background.

    Supersedes the earlier blank-deck rebuild, which copied shape XML into a *fresh*
    presentation and so orphaned every relationship the shapes referenced. On 702 slide 2
    the gear diagram is a single GROUP carrying 13 `r:embed` ids; the copy kept the group
    but none of its images, so the figure rendered as text and highlight boxes on nothing.
    Editing the deck in place keeps the slide part — and its rels — intact.

    `bg="white"` forces a white slide background; `bg="deck"` leaves the master's own fill
    showing. Neither is right for every figure — see the auto-selection in main(). Note
    that declaring *no* fill is not an option: LibreOffice falls back to the master's fill
    anyway, so "transparent" silently means "the deck's navy".
    """
    prs = Presentation(deck_abs)
    slide = list(prs.slides)[index - 1]
    art = foreground(diagram_shapes(slide), (prs.slide_width, prs.slide_height))
    keep = {id(s._element) for s in art}
    for sh in list(slide.shapes):
        if id(sh._element) not in keep:
            sh._element.getparent().remove(sh._element)
    slide._element.set("showMasterSp", "0")   # hides the master's band and logo, not its fill
    if bg == "white":
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    prs.save(dest)
    return dest, art


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--code", action="append", help="only this element code (repeatable)")
    ap.add_argument("--plan", default=PLAN,
                    help="plan to read decks from (default plan/course-plan.yaml)")
    ap.add_argument("--bg", choices=("auto", "white", "deck"), default="auto",
                    help="figure background: white, the deck's own, or auto per figure")
    ap.add_argument("--min-visible", type=float, default=0.15,
                    help="below this visible share, auto re-renders on the deck background")
    args = ap.parse_args()

    plan = yaml.safe_load(open(args.plan))
    files = {}
    for f in glob.glob(os.path.join(COURSE, "*", "*.md")):
        m = re.search(r'^code:\s*"([^"]+)"', open(f).read(), re.M)
        if m:
            files[m.group(1)] = f

    os.makedirs(TMP, exist_ok=True)
    counts = {"picture": 0, "native": 0, "mixed": 0, "skip": 0}
    backgrounds = {}          # stem -> "white" | "deck", recorded for the review page
    needs_manual = []   # pictures whose part could not be read; rendered instead

    for mod in plan["modules"]:
        for el in mod["elements"]:
            code = str(el["code"])
            if args.code and code not in args.code:
                continue
            decks = [d for d in (el.get("spo_decks") or el.get("general_decks") or [])
                     if d.lower().endswith(".pptx")]
            if not decks or code not in files:
                continue
            deck = decks[0]
            assets = os.path.join(os.path.dirname(files[code]), "assets")
            prs = Presentation(os.path.join(HERE, deck))
            size = (prs.slide_width, prs.slide_height)
            pdf = None

            for n, slide in enumerate(prs.slides, 1):
                kind, pics, vecs = classify(slide)
                art = diagram_shapes(slide)
                if kind is None or not art:
                    continue
                if args.dry_run:
                    counts[kind] += 1
                    continue
                os.makedirs(assets, exist_ok=True)

                if kind == "picture":
                    # largest first; a picture can point at a non-image part (linked or
                    # OLE media), in which case fall through to rendering the slide
                    img = None
                    for sh in sorted(pics, key=lambda s: -((s.width or 0) * (s.height or 0))):
                        try:
                            img = sh.image
                            break
                        except Exception:
                            continue
                    if img is not None:
                        out = os.path.join(assets, f"{code}-slide-{n}.{img.ext}")
                        open(out, "wb").write(img.blob)
                        counts["picture"] += 1
                        continue
                    kind = "native"
                    needs_manual.append(f"{code}-slide-{n}.svg")

                # vector paths render a stripped copy of the deck — the artwork on that
                # slide, alone. One copy + one conversion per figure, twice for the few
                # that turn out to need the deck's own background (see below).
                if kind == "native":
                    one = os.path.join(TMP, f"{code}-{n}.pptx")
                    _, art = stripped_deck(os.path.join(HERE, deck), n, one, bg=args.bg
                                           if args.bg != "auto" else "white")
                    src_pdf, page = soffice("pdf", one, TMP), n
                else:
                    if pdf is None:
                        pdf = soffice("pdf", os.path.join(HERE, deck), TMP)
                    src_pdf, page = pdf, n
                    art = foreground(art, size)
                if not src_pdf or not os.path.exists(src_pdf):
                    counts["skip"] += 1
                    continue

                box = bbox(art)
                scale = 72 / 914400                # EMU -> points
                box_pt = tuple(v * scale for v in box) if box else None

                out = os.path.join(assets, f"{code}-slide-{n}.svg")
                subprocess.run(["pdftocairo", "-svg", "-f", str(page), "-l", str(page),
                                src_pdf, out], check=True)
                if box_pt:
                    crop_svg(out, box_pt)
                # SVG master and PNG come from the same render, so they cannot disagree —
                # the previous split (rebuilt deck for one, original slide for the other)
                # is exactly how the broken masters stayed hidden.
                png_root = os.path.join(assets, f"{code}-slide-{n}")
                render_png(src_pdf, page, png_root, box_pt)
                chosen = args.bg if args.bg != "auto" else "white"

                # Some slides draw white text and pale strokes straight onto the deck's
                # dark field. Forcing white erases them — 700 slides 3 and 7 came out ~8%
                # visible, effectively blank. When almost nothing reads against the
                # background, re-render keeping the deck's own fill and take that instead.
                if kind == "native" and args.bg == "auto":
                    vis = visible_share(png_root + ".png")
                    if vis is not None and vis < args.min_visible:
                        alt = os.path.join(TMP, f"{code}-{n}-deck.pptx")
                        stripped_deck(os.path.join(HERE, deck), n, alt, bg="deck")
                        alt_pdf = soffice("pdf", alt, TMP)
                        if alt_pdf and os.path.exists(alt_pdf):
                            subprocess.run(["pdftocairo", "-svg", "-f", str(n), "-l", str(n),
                                            alt_pdf, out], check=True)
                            if box_pt:
                                crop_svg(out, box_pt)
                            render_png(alt_pdf, n, png_root, box_pt)
                            alt_vis = visible_share(png_root + ".png")
                            chosen = "deck"
                            print(f"  {code}-slide-{n}: {vis:.0%} visible on white → "
                                  f"kept the deck background ({alt_vis:.0%})")
                backgrounds[f"{code}-slide-{n}"] = chosen
                counts[kind] += 1

    if backgrounds and not args.dry_run:
        # merge, never replace: a --code run only knows about the figures it rebuilt, and
        # clobbering the file would silently forget every other figure's choice
        path = os.path.join(COURSE, ".figure-backgrounds.json")
        try:
            known = json.load(open(path))
        except (OSError, json.JSONDecodeError):
            known = {}
        known.update(backgrounds)
        with open(path, "w") as fh:
            json.dump(known, fh, indent=2, sort_keys=True)
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"diagram sources: {counts['picture']} extracted images (clean, no background), "
          f"{counts['native']} rebuilt vector (no background)")
    if needs_manual:
        print(f"\n{len(needs_manual)} slides had an unreadable picture part and were "
              f"rendered instead — check these before flavour overlay:")
        for m in needs_manual[:6]:
            print(f"    {m}")
        if len(needs_manual) > 6:
            print(f"    … and {len(needs_manual) - 6} more")
    if args.dry_run:
        print("DRY RUN — nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
