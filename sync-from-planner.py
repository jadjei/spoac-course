#!/usr/bin/env python3
"""Push the planner's learning targets and module videos into `course/`.

Two things the planner owns and the element files have to carry:

  * **One learning target per lesson.** Andamio gives each target one lesson slot, so a
    lesson without a target of its own has nowhere to live. The planner's column is
    authoritative; this overwrites whatever the element file holds.
  * **The module video.** Andamio's import has no video node — an `<iframe>` is dropped
    on the way in — so the closest thing to an embed is YouTube's own thumbnail, which
    survives as an imageBlock with its remote src, plus a link line beneath it. A linked
    thumbnail does not work: `[![alt](img)](url)` collapses to an empty link and the
    image is lost.

    The block goes at the top of the module's **first lesson**, not its introduction.
    Andamio stores introductions and serves them over the API but renders them nowhere:
    the module page shows targets, lessons and the assignment, and `/introduction` is
    not a route. A video placed there is unreachable for a learner. The first lesson is
    the first thing they open.

Idempotent: the video block is replaced if already present, never stacked.

Usage:
    python3 sync-from-planner.py            # write
    python3 sync-from-planner.py --check    # report only
"""
import argparse
import glob
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(HERE, "plan", "course-plan.yaml")
COURSE = os.path.join(HERE, "course")

VIDEO_MARK = "<!-- module-video -->"
SLT_SECTION = re.compile(r"(## Student Learning Targets\s*\n)(.*?)(?=\n## |\Z)", re.S)
VIDEO_BLOCK = re.compile(re.escape(VIDEO_MARK) + r".*?" + re.escape(VIDEO_MARK) + r"\n*",
                         re.S)


def video_block(url, title, code):
    """Thumbnail plus link, with the thumbnail served from the platform's own CDN.

    Hotlinking `img.youtube.com` looked right in the payload and rendered as a broken
    image in the app, while every figure served from the platform's storage renders
    fine. So the thumbnail ships as an ordinary asset, uploaded on import like any
    other figure, and the link sits under it as a plain line rather than a blockquote,
    which the renderer was wrapping in stray quotation marks.
    """
    if not re.search(r"(?:youtu\.be/|v=)([\w-]+)", url):
        return ""
    return (f"{VIDEO_MARK}\n"
            f"![{title}, module video](assets/{code}-video.jpg)\n\n"
            f"**Module video:** [watch {title} on YouTube]({url})\n"
            f"{VIDEO_MARK}\n\n")


def files_by_code():
    out = {}
    for f in glob.glob(os.path.join(COURSE, "*", "*.md")):
        m = re.search(r'^code:\s*"([^"]+)"', open(f).read(), re.M)
        if m:
            out[m.group(1)] = f
    return out


def set_target(text, target):
    block = f"## Student Learning Targets\n\n1. {target}\n\n"
    if SLT_SECTION.search(text):
        return SLT_SECTION.sub(lambda m: f"{m.group(1)}\n1. {target}\n", text, count=1)
    if "## Content" in text:                      # scaffolded without the section
        return text.replace("## Content", block + "## Content", 1)
    return text.rstrip() + "\n\n" + block


def set_video(text, block):
    text = VIDEO_BLOCK.sub("", text)
    if not block:
        return text
    m = re.search(r"^## Content\s*\n+", text, re.M)
    if not m:
        return text.rstrip() + "\n\n" + block
    # under the Content heading, above the narration, where a learner meets it first
    return text[:m.end()] + block + text[m.end():]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    plan = yaml.safe_load(open(PLAN))
    files = files_by_code()
    targets = videos = missing = 0

    for mod in plan["modules"]:
        # the video belongs to the module, and lands on its first lesson by code order,
        # which is the lesson convert.py will emit as lesson-1
        lessons = sorted((el for el in mod["elements"]
                          if el.get("type") == "lesson" and not el.get("deferred")),
                         key=lambda e: str(e["code"]))
        video_host = str(lessons[0]["code"]) if lessons else None
        video_url = next((el.get("video_url") for el in mod["elements"]
                          if el.get("video_url")), "")
        for el in mod["elements"]:
            code = str(el["code"])
            path = files.get(code)
            if not path or el.get("deferred"):
                continue
            before = open(path).read()
            text = before
            if el.get("slts") and el.get("type") in ("lesson", "video", "overview"):
                text = set_target(text, el["slts"][0])
            # strip any block wherever it used to sit, then place it on the host lesson
            text = set_video(text, "")
            if video_url and code == video_host:
                text = set_video(text, video_block(video_url, mod.get("title") or code,
                                                   mod["code"]))
            if text != before:
                if el.get("slts"):
                    targets += 1
                if video_url and code == video_host:
                    videos += 1
                if not args.check:
                    open(path, "w").write(text)
            if el.get("type") == "lesson" and not el.get("slts"):
                missing += 1
                print(f"  ! {code}: no learning target in the planner")

    verb = "would update" if args.check else "updated"
    print(f"{verb} {targets} targets, {videos} module videos"
          + (f"; {missing} lesson rows still have no target" if missing else ""))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
