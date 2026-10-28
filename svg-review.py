#!/usr/bin/env python3
"""Review every extracted figure on one page, and open any of them in Inkscape.

`extract-diagrams.py` writes two files per figure: a `.svg` master for theming and a
`.png` beside it for the platform (Andamio's CDN rejects SVG). Both come from the same
render, so they should agree — but a figure can still be *wrong*: the pptx may hide the
artwork behind furniture, or a shape may not survive LibreOffice's conversion. That is
only visible by looking, and recursing through eight asset directories to look is the
tedium this replaces.

Three panes per figure: the **original slide** rendered whole (the control), the **SVG
master**, and the **PNG** the platform serves. The control is the same LibreOffice
renderer with nothing stripped or cropped, so a wrong-looking figure separates into
"the extraction did this" versus "the renderer did this" versus "the deck is like that" —
700 slide 3 reads instantly once you see the source: four legend bullets stranded at the
far left, the diagram in a card at the right, so the crop spans both. It is *not*
PowerPoint's own rendering; Impress quirks (SmartArt, font substitution) show up in all
three panes alike.

Figures are scored two ways — ink coverage, and the widest blank column band — and
anything past either threshold sorts to the top with the reason. That is triage, not a
verdict: a sparse but correct figure will be flagged, and a dense but wrong one will not.
The score only decides reading order.

    python3 svg-review.py                 # write review/figures.html, print the summary
    python3 svg-review.py --serve         # same page, plus working Inkscape buttons
    python3 svg-review.py --open 702-slide-2      # straight to Inkscape
    python3 svg-review.py --no-originals          # skip the control pane (no deck renders)
    python3 svg-review.py --refresh-originals     # re-render them after a deck changes

Original-slide renders are cached under review/originals/ (gitignored) — one deck
conversion each, reused until --refresh-originals.

Inkscape is a flatpak on the host, so it is reached through `flatpak-spawn`; the paths
handed to it must be host-visible (anything under /var/home is).
"""
import argparse, collections, glob, html, http.server, json, os, re, socketserver, subprocess, sys, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.join(HERE, "course")
OUT = os.path.join(HERE, "review", "figures.html")
INKSCAPE = ["flatpak-spawn", "--host", "flatpak", "run", "org.inkscape.Inkscape"]
SOFFICE = ["flatpak-spawn", "--host", "flatpak", "run", "org.libreoffice.LibreOffice"]
CACHE = os.path.join(HERE, "review", "originals")     # rendered originals, gitignored


def measure(png):
    """(ink, gap) for a PNG, or (None, None) when it cannot be read.

    ink  share of pixels that differ from the figure's own background — near zero means
         the artwork did not survive.
    gap  widest run of entirely blank columns, as a share of width. Catches the other
         failure: artwork that IS intact but sits beside something stranded far away, so
         the crop spans a desert. 700 slide 3 is the case — four orphaned legend dots at
         the left edge, the real diagram at the right, half the figure empty between them.
         Ink coverage cannot see this; the two together cover both ways a figure goes bad.
    """
    try:
        from PIL import Image
    except ImportError:
        return None, None
    try:
        im = Image.open(png).convert("RGB").resize((200, 200))
    except Exception:
        return None, None
    px = list(im.getdata())
    w = 200
    # Background is the modal colour, not white. Figures whose artwork is light-on-dark
    # keep the deck's dark field on purpose, and a white-assuming metric reads those as
    # 100% ink with no gaps — blind exactly where a figure is most likely to be wrong.
    bg = collections.Counter(px).most_common(1)[0][0]
    marked = [sum(abs(a - b) for a, b in zip(p, bg)) > 60 for p in px]
    ink_share = sum(marked) / len(marked)
    blank = [not any(marked[r * w + c] for r in range(w)) for c in range(w)]
    widest = run = 0
    for c in blank:
        run = run + 1 if c else 0
        widest = max(widest, run)
    return ink_share, widest / w


def plan_decks():
    """code -> deck path, from the plan. Same precedence extract-diagrams.py uses."""
    import yaml
    try:
        plan = yaml.safe_load(open(os.path.join(HERE, "plan", "course-plan.yaml")))
    except OSError:
        return {}
    out = {}
    for mod in plan.get("modules", []):
        for el in mod.get("elements", []):
            decks = el.get("spo_decks") or el.get("general_decks") or []
            pptx = next((d for d in decks if d.lower().endswith(".pptx")), None)
            if pptx:
                out[str(el["code"])] = pptx
    return out


def original_png(code, slide, decks, cache, refresh=False):
    """The untouched slide, rendered whole. Returns a path, or None if it can't be made.

    This is the control for the other two panes: same LibreOffice renderer, nothing
    stripped, nothing cropped. It is *not* PowerPoint's own rendering — if Impress
    mis-renders something (SmartArt and font substitution are the usual suspects) it will
    mis-render it here too. That is the point: it shows what the pipeline saw, so a figure
    that looks wrong can be blamed on the extraction or on the renderer, not guessed at.
    """
    deck = decks.get(code)
    if not deck:
        return None
    out = os.path.join(cache, f"{code}-slide-{slide}.png")
    if os.path.exists(out) and not refresh:
        return out
    deck_abs = os.path.join(HERE, deck)
    if not os.path.exists(deck_abs):
        return None
    pdf = os.path.join(cache, os.path.splitext(os.path.basename(deck))[0] + ".pdf")
    if not os.path.exists(pdf) or refresh:
        os.makedirs(cache, exist_ok=True)
        r = subprocess.run(SOFFICE + ["--headless", "--convert-to", "pdf",
                                      "--outdir", cache, deck_abs],
                           capture_output=True, text=True, timeout=600)
        m = re.search(r"-> (\S.*?) using filter", r.stdout)
        if not m:
            return None
        pdf = m.group(1).strip()
    subprocess.run(["pdftocairo", "-png", "-singlefile", "-r", "90",
                    "-f", str(slide), "-l", str(slide), pdf, os.path.splitext(out)[0]],
                   check=False)
    return out if os.path.exists(out) else None


def svg_stats(path):
    """Rough content census of an SVG: how many marks of each kind it carries."""
    try:
        txt = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return {}
    return {k: len(re.findall(rf"<{k}\b", txt))
            for k in ("path", "image", "text", "rect", "g")}


def references(code, slide):
    """Lesson files citing this figure, so a bad one leads straight to its lesson."""
    stem = f"{code}-slide-{slide}"
    out = []
    for md in glob.glob(os.path.join(COURSE, "*", "*.md")):
        try:
            if re.search(rf"assets/{re.escape(stem)}\.(png|jpg|jpeg|svg)", open(md).read()):
                out.append(os.path.relpath(md, HERE))
        except OSError:
            continue
    return out


def collect(originals=True, refresh=False):
    decks = plan_decks() if originals else {}
    try:
        bgs = json.load(open(os.path.join(COURSE, ".figure-backgrounds.json")))
    except (OSError, json.JSONDecodeError):
        bgs = {}
    figs = []
    for svg in sorted(glob.glob(os.path.join(COURSE, "*", "assets", "*.svg"))):
        base = os.path.splitext(svg)[0]
        stem = os.path.basename(base)
        m = re.match(r"(.+)-slide-(\d+)$", stem)
        if not m:
            continue
        code, slide = m.group(1), int(m.group(2))
        png = next((f"{base}{e}" for e in (".png", ".jpg", ".jpeg")
                    if os.path.exists(f"{base}{e}")), None)
        cov, gap = measure(png) if png else (None, None)
        figs.append(dict(
            stem=stem, code=code, slide=slide,
            module=os.path.basename(os.path.dirname(os.path.dirname(svg))),
            svg=svg, png=png,
            svg_bytes=os.path.getsize(svg),
            png_bytes=os.path.getsize(png) if png else 0,
            ink=cov, gap=gap,
            stats=svg_stats(svg),
            refs=references(code, slide),
            original=(original_png(code, slide, decks, CACHE, refresh)
                      if originals else None),
            bg=bgs.get(stem),
        ))
    return figs


def why(f, threshold, gap_max):
    """Reasons this figure wants a human eye, worst first. Empty means it looks fine."""
    out = []
    if f["ink"] is not None and f["ink"] < threshold:
        out.append("almost no ink")
    if f["gap"] is not None and f["gap"] > gap_max:
        out.append(f"{f['gap'] * 100:.0f}% blank band — stranded shape?")
    if not f["png"]:
        out.append("no raster")
    if not f["refs"]:
        out.append("unreferenced")
    return out


def page(figs, threshold, gap_max, serve):
    rows = []
    for f in figs:
        cov = f["ink"]
        reasons = why(f, threshold, gap_max)
        flag = bool(reasons)
        cov_txt = "—" if cov is None else f"{cov * 100:.1f}%"
        gap_txt = "—" if f["gap"] is None else f"{f['gap'] * 100:.0f}%"
        stats = " · ".join(f"{k}:{v}" for k, v in f["stats"].items() if v)
        refs = "<br>".join(html.escape(r) for r in f["refs"]) or \
               "<em>not referenced by any lesson</em>"
        png_rel = os.path.relpath(f["png"], os.path.dirname(OUT)) if f["png"] else ""
        svg_rel = os.path.relpath(f["svg"], os.path.dirname(OUT))
        orig_rel = os.path.relpath(f["original"], os.path.dirname(OUT)) if f["original"] else ""
        button = (f'<button onclick="openIn(\'{html.escape(f["svg"])}\')">'
                  f'Open in Inkscape</button>' if serve else
                  f'<code class="cmd">{html.escape(inkscape_cmd(f["svg"]))}</code>')
        rows.append(f"""
        <article class="{'suspect' if flag else ''}" id="{html.escape(f['stem'])}">
          <header>
            <h2>{html.escape(f['stem'])} {'<span class="badge">' + html.escape('; '.join(reasons)) + '</span>' if flag else ''}</h2>
            <div class="meta">{html.escape(f['module'])} · slide {f['slide']} ·
              ink {cov_txt} · widest blank band {gap_txt} ·
              {'bg: ' + html.escape(f['bg']) + ' · ' if f.get('bg') else ''}
              svg {f['svg_bytes'] // 1024}k · png {f['png_bytes'] // 1024}k</div>
          </header>
          <div class="pair">
            <figure><figcaption>Original slide <span class="hint">(control)</span></figcaption>
              {'<img src="' + html.escape(orig_rel) + '" loading="lazy">' if orig_rel
               else '<p class="warn">deck not resolved from the plan</p>'}</figure>
            <figure><figcaption>SVG master <span class="hint">(theming)</span></figcaption>
              <img src="{html.escape(svg_rel)}" loading="lazy"></figure>
            <figure><figcaption>PNG <span class="hint">(on the platform)</span></figcaption>
              {'<img src="' + html.escape(png_rel) + '" loading="lazy">' if png_rel
               else '<p class="warn">no raster — this figure cannot be uploaded</p>'}</figure>
          </div>
          <div class="foot"><div class="stats">{html.escape(stats)}</div>
            <div class="refs">{refs}</div>{button}</div>
        </article>""")

    n_flag = sum(1 for f in figs if why(f, threshold, gap_max))
    script = """
      <script>
      async function openIn(path) {
        const r = await fetch('/open', {method:'POST',
          headers:{'Content-Type':'application/json'}, body: JSON.stringify({path})});
        if (!r.ok) alert('could not open: ' + await r.text());
      }
      </script>""" if serve else ""

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>SPOAC figures — review</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 1100px;
         padding: 2rem 1rem 4rem; }}
  h1 {{ margin-bottom: .2rem; }}
  .summary {{ color: #666; margin-bottom: 2rem; }}
  article {{ border: 1px solid #ccc4; border-radius: 10px; padding: 1rem 1.2rem;
             margin-bottom: 1.5rem; }}
  article.suspect {{ border-color: #d9534f; background: #d9534f0e; }}
  header {{ display: flex; justify-content: space-between; align-items: baseline;
            flex-wrap: wrap; gap: .5rem; }}
  h2 {{ font-size: 1.05rem; margin: 0; font-family: ui-monospace, monospace; }}
  .badge {{ background: #d9534f; color: #fff; border-radius: 4px; padding: 0 .4rem;
            font-size: .72rem; vertical-align: middle; }}
  .meta {{ color: #777; font-size: .82rem; }}
  .pair {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin: .8rem 0; }}
  .hint {{ opacity: .7; }}
  figure {{ margin: 0; }}
  figcaption {{ font-size: .75rem; color: #777; margin-bottom: .3rem; }}
  img {{ max-width: 100%; border: 1px solid #ccc6; border-radius: 6px;
         background: repeating-conic-gradient(#0000 0 25%, #8881 0 50%) 0 0 / 16px 16px; }}
  .foot {{ display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;
           font-size: .8rem; color: #666; }}
  .refs {{ flex: 1; }}
  .cmd {{ font-size: .72rem; background: #8881; padding: .3rem .5rem; border-radius: 5px;
          user-select: all; }}
  button {{ font: inherit; padding: .35rem .8rem; border-radius: 6px; cursor: pointer;
            border: 1px solid #888; background: #8881; }}
  .warn {{ color: #d9534f; }}
  @media (max-width: 900px) {{ .pair {{ grid-template-columns: 1fr; }} }}
</style></head><body>
<h1>SPOAC figures</h1>
<p class="summary">{len(figs)} figures · <strong>{n_flag}</strong> flagged and sorted first.
  Ink is the share of non-white pixels; the blank band is the widest empty column run,
  which catches artwork stranded beside a gap. Triage only, not a verdict.
  The left pane is the untouched slide through the same LibreOffice renderer — a control
  for what the pipeline saw, not PowerPoint's own rendering.
  {'Buttons open the SVG master in Inkscape.' if serve
   else 'Run with <code>--serve</code> for working Inkscape buttons.'}</p>
{''.join(rows)}
{script}
</body></html>"""


def inkscape_cmd(svg):
    return " ".join(INKSCAPE + [f'"{svg}"'])


def open_inkscape(svg):
    if not os.path.exists(svg):
        raise FileNotFoundError(svg)
    return subprocess.Popen(INKSCAPE + [svg],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def serve(port, figs, threshold):
    # serve from the repo root, not review/: the page references ../course/**/assets/*,
    # and SimpleHTTPRequestHandler refuses to escape its root, so those 404 otherwise
    root = HERE
    allowed = {f["svg"] for f in figs}          # only ever open a figure we listed

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root, **kw)

        def do_POST(self):
            if self.path != "/open":
                return self.send_error(404)
            n = int(self.headers.get("Content-Length", 0))
            try:
                path = json.loads(self.rfile.read(n)).get("path", "")
            except json.JSONDecodeError:
                return self.send_error(400, "bad json")
            if path not in allowed:
                return self.send_error(403, "not a listed figure")
            try:
                open_inkscape(path)
            except Exception as e:
                return self.send_error(500, str(e))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *a):
            pass

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as srv:
        rel = os.path.relpath(OUT, HERE).replace(os.sep, "/")
        print(f"review at http://127.0.0.1:{port}/{rel}   (ctrl-c to stop)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true", help="serve the page with Inkscape buttons")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--open", metavar="STEM", help="open one figure in Inkscape and exit")
    ap.add_argument("--suspect-below", type=float, default=0.03,
                    help="ink coverage under this is flagged (default 0.03)")
    ap.add_argument("--gap-above", type=float, default=0.25,
                    help="widest blank column band over this is flagged (default 0.25)")
    ap.add_argument("--no-originals", action="store_true",
                    help="skip the original-slide pane (avoids rendering the decks)")
    ap.add_argument("--refresh-originals", action="store_true",
                    help="re-render the cached original slides")
    args = ap.parse_args()

    figs = collect(originals=not args.no_originals, refresh=args.refresh_originals)
    if not figs:
        sys.exit("no figures found — run extract-diagrams.py first")

    if args.open:
        hit = next((f for f in figs if f["stem"] == args.open), None)
        if not hit:
            sys.exit(f"no figure named {args.open}")
        open_inkscape(hit["svg"])
        print(f"opening {hit['svg']}")
        return 0

    figs.sort(key=lambda f: (not why(f, args.suspect_below, args.gap_above),
                             f["ink"] if f["ink"] is not None else 1, f["stem"]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(page(figs, args.suspect_below, args.gap_above, args.serve))

    flagged = [f for f in figs if why(f, args.suspect_below, args.gap_above)]
    missing = [f for f in figs if not f["png"]]
    no_orig = [f for f in figs if not f["original"]]
    print(f"{len(figs)} figures → {os.path.relpath(OUT, HERE)}")
    if no_orig and not args.no_originals:
        print(f"{len(no_orig)} without an original-slide render: "
              + ", ".join(f["stem"] for f in no_orig[:8]))
    if missing:
        print(f"{len(missing)} without a raster (cannot be uploaded): "
              + ", ".join(f["stem"] for f in missing[:8]))
    print(f"{len(flagged)} flagged for a look:")
    for f in flagged[:12]:
        print(f"    {f['stem']:18} {'; '.join(why(f, args.suspect_below, args.gap_above))}")
    if len(flagged) > 12:
        print(f"    … and {len(flagged) - 12} more")
    if args.serve:
        serve(args.port, figs, args.suspect_below)
    return 0


if __name__ == "__main__":
    sys.exit(main())
