---
title: Google Slides drops slide-level pptx backgrounds, hiding white text
date: 2026-09-28
category: integration-issues
module: spoac-course/sessions
problem_type: integration_issue
component: tooling
symptoms:
  - "Dark title and closing slides render white in Google Slides after uploading a generated .pptx"
  - "White heading text is invisible because it sits on the white background Slides substituted"
  - "The same file renders correctly in LibreOffice, so a local PDF check passes"
root_cause: wrong_api
resolution_type: code_fix
severity: medium
tags: [pptx, google-slides, python-pptx, decks, rendering, libreoffice]
---

# Google Slides drops slide-level pptx backgrounds, hiding white text

## Problem

Decks generated with `python-pptx` set their background as a slide-level property
(`<p:bg>` on the slide). Google Slides ignores that element on import, so every dark
slide arrives white. Any text coloured white for a dark background then renders white
on white and is invisible to the presenter and the audience.

## Symptoms

- Title and closing slides appear blank or show only the accent-coloured subtitle.
- Thumbnails in the Slides filmstrip look empty where a dark slide should be.
- The generated file looks correct everywhere else, which delays the diagnosis.

## What Didn't Work

- **Rendering to PDF with LibreOffice and inspecting the pages.** LibreOffice honours
  `<p:bg>`, so the check passed and gave false confidence. A local render is not a
  proxy for what Google Slides does with the same file.
- **Re-uploading the same file.** The import is deterministic; nothing changes.

## Solution

Draw the background as a full-bleed rectangle as the first shape on the slide, instead
of setting a slide-level background. In `sessions/build-session1-deck.py`:

```python
def slide(bg=WHITE):
    s = prs.slides.add_slide(BLANK)
    for sh in list(s.shapes):
        sh._element.getparent().remove(sh._element)
    # Full-bleed rectangle rather than <p:bg>: Google Slides silently drops a
    # slide-level background on pptx import, which turns a dark slide white and
    # hides every piece of white text on it. A shape survives the round trip.
    if bg != WHITE:
        r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        r.fill.solid(); r.fill.fore_color.rgb = rgb(bg)
        r.line.fill.background(); r.shadow.inherit = False
        if r.has_text_frame: r.text_frame.clear()
    return s
```

Shapes carry their own fill, so the colour survives the import.

## Why This Works

A slide-level `<p:bg>` is presentation-format metadata that an importer may honour,
ignore, or override with its own theme. A drawn shape is content, and content is what
an importer is obliged to reproduce. Anything that must survive a round trip into
another tool belongs in the content layer rather than in a property the importing
application is free to reinterpret.

## Prevention

- **Verify in the destination application, not a local renderer.** If a deck is going
  to Google Slides, look at it in Google Slides. LibreOffice and PowerPoint agree with
  each other far more often than either agrees with Slides.
- Treat this as one instance of a wider rule that bit twice in the same session: a
  file that generates without error is not a file that renders correctly elsewhere,
  just as an upload that returns success is not a video that has processed.
- When generating decks for Slides, prefer shapes and text over theme, master, and
  background properties. Effects such as shadows are the next most likely casualty.

## Related Issues

- `sessions/build-session1-deck.py` carries the reason as a comment at the point of
  the workaround, so sessions 2 to 4 inherit it.
