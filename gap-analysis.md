# SPO Online Business Academy — Gap Analysis (planned vs live)

> **SUPERSEDED (2026-07-29).** This describes the 2026-06-11 planner against the
> then-live 17 modules, both of which have since been replaced: the planner was
> rebuilt around the `_SPO` deck series and the live course is now 8 modules.
> The current, regenerable gap list is **`plan/content-gaps.md`** (`gap-report.py`).
> Kept for the mapping rationale and the live-code archaeology.


**Date:** 2026-06-11 · **Plan:** `plan/course-plan.yaml` (8 modules, 71 elements) ·
**Live:** 17 DRAFT modules pulled to `compiled/spo-online-business-academy/`

> Mapping is by **content/SLT match**, not code — the live course was built on the
> old "Archive V1" structure, so its codes have drifted from the new plan. Lesson
> *bodies* were not deep-diffed yet (only titles + SLTs); verify per-module in Phase 4.

## Headline

- **6 of 17 live modules are mis-coded or mis-placed** vs the plan and need re-coding/moving.
- **3 renames** (live title ≠ planned title for the same content).
- **~Module 100 is entirely missing on-platform** (Our Changing World: VUCA / BANI / ExO / Confluence), plus the **Finance Model (305.x)**, most **Purpose sub-modules (301.1–301.6, 302)**, the **Business-model/Value-chain detail (303.x)**, **Market-Biome proposition lessons (401–405)**, and the **module intro videos for 200/300/500**.
- Several **assignments** in the plan have no live counterpart.

## 1. Live → Plan mapping (where each of the 17 live modules actually belongs)

| Live code | Live title | Maps to plan | Verdict |
|---|---|---|---|
| 000 | SPO Academy Orientation | 000 (video) | ✅ match — but missing the `000.1` **Programme Introduction** assignment |
| 201 | Biomes | **202** Understanding Biomes | 🔀 re-code 201→202 |
| 202 | Business Audit | **205** Your Full Value Audit | 🔀 re-code 202→205 |
| 203 | Building Your Dashboard for Growth | **702** Constructing Your Dashboard | 🔀 mis-placed — move 203→702 |
| 301 | Big Purpose | 301 Your Individual Purpose | ✅ match — ✏️ rename "Big Purpose" → "Your Individual Purpose" |
| 320 | Business Model | 306 Value Model **+** 303.1/303.3 | 🧩 consolidated — see §3 |
| 400 | Market Biome | 400 (overview lesson) | ⚠️ overview only; 401–405 lessons missing; no intro |
| 501 | Commercial Assets and Operations | 501 | ✅ match (SLT-3 drifted) |
| 502 | People Assets and Operations | 502 Performance Assets | ✅ match — ✏️ confirm name People vs Performance |
| 601 | External Environment | 601 | ✅ match |
| 602 | Funding Sources | 602 | ✅ match |
| 603 | Community Management | 603 | ✅ match |
| 700 | The Journey | 700 (4D Impact Leadership Framework) | ✅ match — ✏️ title differs |
| 701 | Setting Your Vision | **301.3** Your Vision | 🔀 mis-placed — Vision content under a 700 code; move 701→301.3 |
| 702 | Your Business Plan | **701** Building Your Playbook | 🔀 re-code 702→701 |
| 703 | Scenario Planning | 703 | ✅ match |
| 704 | Your Implementation Plan | 704 Running Your Playbook | ✅ match |

**Net:** the live `700` range is shuffled — plan 701(Playbook)=live 702, plan
702(Dashboard)=live 203, plan 703/704 ok, and live 701 actually holds *Vision*
(belongs in the 300/Purpose range).

## 2. Plan → Live coverage (what's missing, by planned module)

Legend: ✅ present · ⚠️ partial · ❌ missing

### 000 Orientation
- ✅ 000 video (live 000)
- ❌ 000.1 **Programme Introduction** assignment

### 100 Our Changing World — ❌ ENTIRELY MISSING
- ❌ 100 video · ❌ 100.1 VUCA · ❌ 100.2 BANI · ❌ 100.3 ExO · ❌ 100.4 Confluence of Disruptive ExO

### 200 Your Journey Toolkit
- ❌ 200 video (Your Map) · ❌ 201 Your Journey to Success (Edify 4D Journey Framework)
- ✅ 202 Understanding Biomes (= live **201**) · ❌ 203 Full Value Framework · ❌ 204 Real Value Growth Engine
- ✅ 205 Full Value Audit (= live **202**) · ❌ 205 assignment "Edify Full Value Audit"

### 300 Your Why – Your Essence (largest module — 34 planned elements)
- ❌ 300 video (Your Essence)
- ✅ 301 Purpose (= live **301**) · ❌ 301.1 Defining your Entity · ❌ 301.2 Choose Your Lens
- ✅ 301.3 Your Vision (= live **701**) · ❌ 301.4 Your Intent (+ IKIGAI, MTP assignments) · ❌ 301.5 Power & Governance · ❌ 301.6 Impact
- ❌ 302 Your SPO Purpose (+ IKIGAI assignment)
- 🧩 303.1 Business Models / 303.3 Value Chain → folded into live **320**; ❌ 303.2 Edify Full Value BM · ❌ 303.4 Supply Chain · ❌ 303.5 Integrated V/S Chain · ❌ 303.6 Edify Integrated BM · ❌ 303.7 Edify BM Real Value Engine
- ❌ 304 / 304.1 Your SPO Business Model (+ assignment)
- ❌ 305 Finance Model · ❌ 305.1 Foundations · ❌ 305.2 Insight · ❌ 305.3 Strategy · ❌ 305.4 Resiliance
- ⚠️ 306 Value Model → in live **320**; ❌ its sub-lessons Value Types / Commercial Exchange / Social Exchange / Social Impact · ❌ "Your Finance Model" assignment

### 400 Market Biome
- ✅ 400 overview (= live **400**, 5 lessons cover the overview SLTs) — ❌ no intro video
- ❌ 401 Product proposition · ❌ 402 Value Proposition · ❌ 403 Customer Proposition · ❌ 404 Positioning/Market · ❌ 405 Channel/Ecosystem · ❌ assignment
  - _(verify: live 400's 5 lessons may already cover some of these — confirm lesson bodies)_

### 500 Internal Biome
- ❌ 500 video · ✅ 501 Commercial Assets (= live **501**) · ✅ 502 Performance/People Assets (= live **502**) · ❌ assignment

### 600 External Biome
- ❌ 600 video · ✅ 601 (live 601) · ✅ 602 (live 602) · ✅ 603 (live 603) · ❌ assignment

### 700 The Journey
- ✅ 700 video (live 700) · ✅ 701 Building Your Playbook (= live **702**) · ✅ 702 Dashboard (= live **203**) · ✅ 703 (live 703) · ✅ 704 (live 704) · ❌ assignment

## 3. Consolidation note — live 320 "Business Model"

Its 6 SLTs span **three** planned elements: 306 Value Model (define BM, BM-vs-plan),
303.1 Introduction to Business Models (evaluate real-world models), and 303.3 Value
Chain (value-chain components + VCA). Decision needed: keep consolidated, or split to
match the plan's finer structure.

## 4. Action punch-list (for Phase 4)

**A. Re-code / move (content exists, wrong code):**
- 201 → 202 · 202 → 205 · 203 → 702 · 702 → 701 · 701 → 301.3
- _(careful: 702 and 203 both move into the 700-range; sequence the renames to avoid collisions)_

**B. Rename (content matches, title differs):**
- 301 "Big Purpose" → "Your Individual Purpose"
- 700 "The Journey" → confirm vs "4D Impact Leadership Framework"
- 502 "People Assets and Operations" → confirm vs "Performance Assets and Operations"

**C. Create (missing modules/lessons), priority order:**
1. **Module 100** (Our Changing World): video + VUCA, BANI, ExO, Confluence
2. **Finance Model 305** (+ Foundations, Insight, Strategy, Resiliance)
3. **Purpose sub-modules** 301.1, 301.2, 301.4 (+IKIGAI, MTP), 301.5, 301.6, 302
4. **Business model / value chain** 303.2, 303.4, 303.5, 303.6, 303.7, 304/304.1
5. **Market Biome lessons** 401–405 (verify against live 400 lessons first)
6. **Intro videos** for 200, 300, 500; **module-600** intro
7. **Missing elements** 201 Your Journey to Success, 203 Full Value Framework, 204 Real Value Growth Engine, 306 sub-lessons

**D. Add assignments:** 000.1, 205, 304.1, 306 (Your Finance Model), 400, 500, 600, 700.

## Open questions for the course owner
1. Keep live **320** consolidated, or split into 303.1 / 303.3 / 306 per the plan?
2. Confirm the canonical titles in B (renames).
3. Are 401–405 meant to be separate lessons, or are they the 5 lessons already inside live 400?
4. Re-coding live modules: does the platform support changing a module's `course_module_code`, or do these need new modules + retiring the old (on-chain implications)?
