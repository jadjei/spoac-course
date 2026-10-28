#!/usr/bin/env python3
"""Render every deck slide to SVG — vector, not raster.

Two artifacts per deck, because neither alone is sufficient:

  extracted/svg/<deck path>/slide-N.svg   per-slide, self-contained. Text is converted
                                          to outlines by cairo, so it renders identically
                                          anywhere with no font dependency. This is what
                                          gets referenced from course/ lessons.
  extracted/svg/<deck path>/_master.svg   LibreOffice's own export: all slides in one
                                          file with live <text>/<tspan> and named fonts
                                          (Poppins, Noto Sans). Editable and searchable,
                                          but renders correctly only where those fonts
                                          exist. Kept as the source for future edits.

Roughly 60% of slides carry native PowerPoint vector shapes, which survive as SVG paths.
Pictures embedded in the decks were raster to begin with and stay raster inside the SVG —
no pipeline can vectorise those faithfully.

LibreOffice runs on the host via flatpak (this repo is worked on from a toolbox
container), so paths handed to it must be host-visible — anything under /var/home is.

Usage:
    python3 decks-to-svg.py                      # all decks under spoac-dl/
    python3 decks-to-svg.py --src spoac-dl/spo-decks
    python3 decks-to-svg.py --no-master          # skip the editable masters
"""
import argparse, glob, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "extracted", "svg")
TMP = os.path.join(HERE, "spoac-dl", "pdf-tmp")
SOFFICE = ["flatpak-spawn", "--host", "flatpak", "run", "org.libreoffice.LibreOffice"]


def soffice(fmt, src, outdir):
    os.makedirs(outdir, exist_ok=True)
    r = subprocess.run(SOFFICE + ["--headless", "--convert-to", fmt, "--outdir", outdir, src],
                       capture_output=True, text=True, timeout=600)
    m = re.search(r"-> (\S.*?) using filter", r.stdout)
    return m.group(1).strip() if m else None


def page_count(pdf):
    r = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True)
    m = re.search(r"^Pages:\s+(\d+)", r.stdout, re.M)
    return int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "spoac-dl"),
                    help="tree to scan for .pptx (default: spoac-dl/)")
    ap.add_argument("--no-master", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-render decks already done")
    args = ap.parse_args()

    decks = sorted(p for p in glob.glob(os.path.join(args.src, "**", "*.pptx"), recursive=True)
                   if not os.path.basename(p).startswith("~$"))
    print(f"{len(decks)} decks under {os.path.relpath(args.src, HERE)}\n")
    os.makedirs(TMP, exist_ok=True)

    n_slides = failed = skipped = 0
    for i, deck in enumerate(decks, 1):
        rel = os.path.relpath(deck, os.path.join(HERE, "spoac-dl"))
        dest = os.path.join(OUT, os.path.splitext(rel)[0])
        name = os.path.basename(deck)[:54]

        if not args.force and glob.glob(os.path.join(dest, "slide-*.svg")):
            skipped += 1
            continue

        pdf = soffice("pdf", deck, TMP)
        if not pdf or not os.path.exists(pdf):
            print(f"  [{i}/{len(decks)}] ✗ {name} — PDF conversion failed")
            failed += 1
            continue

        os.makedirs(dest, exist_ok=True)
        pages = page_count(pdf)
        for p in range(1, pages + 1):
            subprocess.run(["pdftocairo", "-svg", "-f", str(p), "-l", str(p), pdf,
                            os.path.join(dest, f"slide-{p}.svg")], check=True)
        n_slides += pages

        if not args.no_master:
            master = soffice("svg", deck, dest)
            if master and os.path.exists(master):
                shutil.move(master, os.path.join(dest, "_master.svg"))

        os.remove(pdf)
        print(f"  [{i}/{len(decks)}] ✓ {name}  {pages} slides")

    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n{n_slides} slide SVGs → {os.path.relpath(OUT, HERE)}"
          f"  ({skipped} decks skipped, {failed} failed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
