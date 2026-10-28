# SPO Academy course production tooling

The tools Fluid7 used to build the SPO Online Business Academy course on
[Andamio](https://andamio.io): turning a planning spreadsheet and a set of slide decks into
course modules, learning targets and assignments, then importing them to Andamio, where
completions are issued as on-chain credentials.

SPO Academy was funded by Project Catalyst, project 1200212. The live course is at
https://spo.academy and the project completion video is at https://youtu.be/0nnG3V2Fl38.

## What is here, and what is not

This repository holds the **tooling and the course structure**. The course **content** is
not here: the lesson text, slide decks, narration and assignment templates are the
intellectual property of Edify Systems Limited and are licensed separately. See `NOTICE`.

So the pipeline below is complete as code, but you need your own planner and decks to run it
end to end. The scripts expect them under `spoac-dl/` (fetched from Google Drive with
rclone) and write the authored course to `course/`. Neither directory is published.

## The pipeline

| Step | Tool | What it does |
|---|---|---|
| Plan | `plan-from-planner.py` | Regenerates `plan/course-plan.yaml` from the course planner spreadsheet |
| Fetch | `fetch-spo-decks.py` | Downloads the decks the planner links to, re-listing Drive first so a newly saved deck is not missed |
| Extract | `extract.py` | Pulls text and images out of the `.pptx` decks |
| | `decks-to-svg.py`, `extract-diagrams.py`, `svg-review.py` | Render slides to SVG, isolate diagrams for re-theming, review every figure on one page |
| Scaffold | `scaffold.py` | Builds the `course/` tree from the plan, migrating authored text across renames |
| | `graft.py` | Carries existing live content into the new structure |
| Author | `map-narration.py` | Maps deck speaker-note narration into the lessons it belongs to |
| | `sync-from-planner.py` | Pushes the planner's learning targets and module videos into `course/` |
| Check | `gap-report.py` | Reports what still blocks the course: missing sources and inconsistent wording |
| | `assessment-map.py` | Maps each assignment to the learning targets it evidences |
| | `course-docs.py` | Generates the module reference page for the documentation site |
| Import | `convert.py`, `convert-flat.py` | Convert `course/` into Andamio's import format |

## Course structure (open)

`plan/` holds the structure that is published under CC BY-SA 4.0: the module plan, the 39
Student Learning Targets (also published on chain as part of the Andamio course), the
assignment-to-target map and the audits behind them. `gap-analysis.md` is the original
planned-versus-live mapping.

## Other tooling

- `catalyst-submissions/build-report.js` and `check-overflow.js` build the Catalyst project
  completion report from its design source in `catalyst-submissions/report/`, and fail if any
  page's content is clipped. Set `PCR_PDF` to choose where the PDF is written.
- `sessions/build-session1-deck.py` builds a live-session deck in the course's visual system.
- `docs/solutions/` records problems solved along the way, such as Google Slides dropping
  slide backgrounds from generated `.pptx` files.

## Requirements

Python 3 with `python-pptx` and `openpyxl`, rclone with a Google Drive remote, LibreOffice
and Inkscape for rendering, and the [Andamio CLI](https://andamio.io) for import. Node.js and
Chrome for the report build.

## Licence

Code: Apache License 2.0 (`LICENSE`). Course structure and documentation: CC BY-SA 4.0
(`LICENSE-CONTENT`). `NOTICE` sets out what each covers, and what is not licensed here.
