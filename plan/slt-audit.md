# Audit — the 39 learning targets live on Andamio

Assessed 2026-07-30 against the four tests a learning target has to pass: the verb names
something **observable**, it claims a **single capability**, it is in the **learner's
voice**, and the module's **assignment actually evidences it**.

| verdict | count | what it means |
|---|---|---|
| Sound | 10 | observable, in voice, evidenced — keep the text |
| Reword | 4 | the claim is right, the wording or the voice is not |
| No assessable claim | 24 | "understand X" / "familiar with X" — nothing to assess |
| Duplicate | 1 | two lessons carry the same target verbatim |

**21 of the 39 are machine-generated.** `convert.py` falls back to
`f"I can understand {title}."` when an element file has no target of its own, so those
21 are a lesson title with a stem bolted on. They were never authored, which is why the
column K exercise is a rewrite rather than a restoration.

**The assignments are stronger than the targets.** Module 400's assignment asks the
operator to state five propositions as defensible claims, while
its targets claim only that the learner understands each proposition. The evidence is
already there and already harder than the claim; in most modules the fix is to describe
what the assignment demands.

## By module

### 000 SPO Academy Orientation

| # | target | verdict |
|---|---|---|
| 1 | I can understand the objectives of this course and how it applies to me. | **no claim** — and mismatched: the assignment asks for the operator's starting point, not for the course's objectives |

### 100 Our Changing World

| # | target | verdict |
|---|---|---|
| 1 | I can define VUCA and explain how the world shifted from *complicated* to VUCA. | sound |
| 2 | I can define BANI and each of its four elements. | sound |
| 3 | I can define an exponential technology and contrast exponential vs linear growth. | sound |
| 4 | I can explain what "Ultra-BANI" means and how compounding differs from individual … | sound |

The only module written throughout to standard. One note: the targets stop at define and
explain while the assignment asks the operator to point each lens at their own pool. The
targets under-claim what is actually being assessed.

### 200 Your Map

| # | target | verdict |
|---|---|---|
| 1 | I can understand Your Journey to Success. | **no claim** (generated) |
| 2 | I can understand Edify 4D Journey Framework. | **no claim** (generated) |
| 3 | I will be able to define and differentiate internal and external biomes in business. | sound |
| 4 | I can understand Full Value Framework. | **no claim** (generated) |
| 5 | I will be able to apply this integrated framework to be to make an initial Assignment of where my organisation sits across these key holistic performance areas | reword — the claim is right and the assignment evidences it, but the sentence is garbled and "this framework" does not survive being read on its own |
| 6 | I can understand Integrated Value Asset Build. | **no claim** (generated) |
| 7 | I will be familiar with the Full Value Audit framework, and its major elements: Purpose, Commercial Operations, Commercial Assets, and Cultural Capabilities. | **no claim** — "be familiar with" is not assessable, though the element list is a good basis for one that is |

### 300 Defining Your Essence

| # | target | verdict |
|---|---|---|
| 1 | I will have outlined my Purpose using the IKIGAI framework | sound — names a product, and the assignment collects it |
| 2–6 | I can understand Defining your Entity / your Lens / Power and Governance / Impact / Finance Model | **no claim** (generated ×5) |
| 7 | Clearly define what a business model is and articulate its importance for SPOs. | reword — observable, but written as an instruction to the teacher rather than a claim by the learner |
| 8–10 | I can understand Commercial Exchange / Social Exchange Model / Social Impact model | **no claim** (generated ×3) |

Eight of ten have no assessable claim, against an assignment that asks the operator to
fill a canvas from purpose through to how the pool sustains itself. The widest gap in the
course between what is claimed and what is assessed.

### 400 Market Biome

| # | target | verdict |
|---|---|---|
| 1 | I will be able to Define the Market Biome and explain its relevance to an organization. | sound — though "an organization" should be their pool |
| 2–6 | I can understand Product / Value / Customer / Positioning / Partner proposition | **no claim** (generated ×5) |

The cheapest module to fix: the assignment already names exactly what each proposition
must contain, so each target can be lifted straight from it.

### 500 Internal Biome

| # | target | verdict |
|---|---|---|
| 1 | I will be able to explain the concept and purpose of a 360 Internal Business Audit. | sound |
| 2 | I will be able to explain the concept and purpose of a 360 Internal Business Audit. | **duplicate** — identical to 1, so the Capability lesson carries the Revenue lesson's target |
| 3 | I can understand Commercial Assets. | **no claim** (generated) |
| 4 | I can understand Relationship Assets. | **no claim** (generated) |

### 600 Understanding the External Biome

| # | target | verdict |
|---|---|---|
| 1 | I can understand External Environment. | **no claim** (generated) |
| 2 | I will be able to understand Organisational Funding Mechanisms | **no claim** — "be able to understand" hedges the verb away |
| 3 | I can evaluate and Manage Key Organisational Relationships | reword — evaluate is assessable, but it is two claims in one and mid-sentence capitals |

### 700 4D Impact Leadership Framework

| # | target | verdict |
|---|---|---|
| 1 | I will understand the key components of the Edify Business Planning Framework. | **no claim** |
| 2 | I will be able to extract Key Insights from my qualitative Assignments to identify top areas for organisational development. | sound — and well matched to the capstone assignment |
| 3 | See how to apply strategic thinking to different market conditions. | reword — not in the learner's voice, and "see how to" claims observation rather than capability |
| 4 | I will understand how to create a structured Implementation Plan for business execution. | reword — the real claim is *create*; "understand how to create" hedges it into unassessability |

## What follows

1. **Rewrite from the assignment, not from the lesson title.** The assignments already
   state what the operator has to produce. A target that names that product is
   observable by construction, and the credential then claims something real.
2. **Fix the 500 duplicate** whichever way the targets land — two lessons cannot share
   one target when each target owns one lesson slot.
3. **Kill the fallback.** While `convert.py` answers a missing target with
   "I can understand {title}.", any element that loses its target silently regains a
   non-target. Better to fail the conversion and make the gap visible.
4. **Check 000.** Its single target is about the course; its assignment is about the
   operator's pool. One of the two is describing the wrong thing.
