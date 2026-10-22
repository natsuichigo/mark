---
name: docs-to-deck
description: Build a portfolio-themed reveal.js walkthrough deck for one of Mark's projects from its published case-study pages, in the natsuichigo/mark repo (_deploy/presentations/<slug>/). This skill is vendored INSIDE that repo at .claude/skills/, so a clone carries it. Use this whenever the user wants a presentation, slide deck, walkthrough, project tour, interview deck or talk built from a case study already on the site, or wants to update an existing deck. ALWAYS establish who the deck is for (overview for recruiters, deep-dive for a technical interview, or talk for a meetup) before writing any slides.
---

# Case Study → Walkthrough Deck

Builds a presentation in the exact reveal.js format already deployed in
`natsuichigo/mark/_deploy/presentations/<slug>/index.html`, with its content
taken from that project's published case-study pages, not from memory.

Companion to **`md-to-docs`**, which produces the case-study pages this skill
reads. The pipeline is:

```
project repo → case study (md-to-docs) → walkthrough deck (THIS SKILL)
```

The deck comes last because it summarises the case study; building it first
means rebuilding it.

## STEP 0 — Ask who the deck is for. Before anything else.

**Do not write a single slide until you know the deck type.** It decides the
deck's length, depth and tone, and roughly half its slides.

| Deck type | Audience | What the deck is |
|---|---|---|
| **`overview`** | Recruiters, hiring managers | Short and outcome-first: the problem, what was built, what it gives you, links. Five or six content slides, little code. |
| **`deep-dive`** | Engineers, a technical interview | Architecture, how it works, design decisions and trade-offs, what went wrong. Code and config where they explain something. |
| **`talk`** | A meetup or team talk | Story-led: the itch, the first version and where it broke, the fix, the lessons. |

If the user isn't sure, suggest `overview` for a portfolio link and
`deep-dive` for an interview. Record the answer in the plan (`deck_type`,
`audience`) so the next update doesn't have to re-ask.

## Where this skill lives

```
mark/.claude/skills/docs-to-deck/
├── SKILL.md
├── scripts/
│   ├── deck_facts.py        what the case study actually has, plus an agenda skeleton
│   ├── blocks.py            renders declared content into the house components
│   ├── scaffold_deck.py     writes the deck: shell, agenda wiring, slides via blocks.py,
│   │                        plus the favicon / link-preview tags (md-to-docs site_meta.py)
│   ├── validate_deck.py     structure AND layout, from the source
│   ├── ensure_render_env.py venv + playwright + browser; on Linux, rootless system libs
│   └── screenshot_deck.py   renders every slide and measures overflow per viewport
└── examples/deck.plan.example.json
```

## What you are targeting

```
_deploy/presentations/
├── layout-fix.css                  # the shared deck layer — DO NOT EDIT (colours: assets/theme.css)
├── index.html                      # redirects to walkthroughs/
└── <slug>/
    ├── index.html                  # the deck (generated)
    ├── _src/deck.plan.json         # its plan — commit it, so the deck can be rebuilt
    └── assets/                     # screenshots, if any
```

`portfolio-site/` is the reference deck. `_deploy/walkthroughs/index.html` is
the hub every deck is linked from, hand-edited like the other hub pages. Use
the case study's slug as the deck's slug.

`_deploy/` **is the published site**, so a deck goes live on the next merge to
`main`. Confirm before writing if the user has not asked to publish.

## Workflow

### 1. Establish the deck type

**Step 0 above.** Then gather the facts:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/deck_facts.py --repo-root . --list
python3 ${CLAUDE_SKILL_DIR}/scripts/deck_facts.py --repo-root . \
  --project packer-image-pipeline --deck-type overview
```

### 2. Read the facts, don't invent them

`deck_facts.py` reports, for the project you named:

- the case study's name, subtitle and repo link, from its index page
- every published page, grouped by section: the deck's spine
- which page to read for which slide (overview, architecture, how it works,
  lessons)
- whether a deck already exists (update it rather than starting again)
- the agenda skeleton for the deck type

Then **read those pages**, and the project's repo where a slide needs more
detail. Numbers on a slide (OS counts, stages, page counts) come from the
pages or the repo, never from an earlier deck or from memory. If the case study
does not exist yet, build it with `md-to-docs` first.

### 3. Build the deck

Write the plan to `_deploy/presentations/<slug>/_src/deck.plan.json` (see
`examples/deck.plan.example.json` for the schema), then:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/scaffold_deck.py --repo-root . \
  --plan _deploy/presentations/<slug>/_src/deck.plan.json
```

This writes `_deploy/presentations/<slug>/index.html` with the title slide
(Mark's name and a button to the case study), the agenda (cards wired to the
right slide indices), the deck-nav bar, a "Back to Walkthroughs" bar, and the
reveal.js init copied verbatim from `--like` (default: `portfolio-site`).
Re-run with `--force` after editing the plan.

Agenda wiring is the part that breaks by hand: every card carries
`data-slide-target`/`-start`/`-end` that must match its slide's real index, and
the nav label hard-codes the slide count. The scaffolder computes all of it.

**Give each slide a `blocks` list and the content is generated too.** A slide
without one comes in as a titled placeholder, so a plan can be filled in slide
by slide, but prefer `blocks`: the renderer cannot produce the markup that
breaks a deck.

```json
{ "title": "Two Stages for AWS Linux", "icon": "fa-hard-drive", "blocks": [
  { "box": "navy", "icon": "fa-circle-question", "lead": "The problem:",
    "text": "<code>amazon-ebs</code> cannot repartition an existing AMI's disk." },
  { "panels": [
    { "tone": "blue", "title": "Stage 1", "icon": "fa-1", "blocks": [
      { "list": ["Builds the disk from scratch", "Custom CIS partition layout"] } ] },
    { "tone": "green", "title": "Stage 2", "icon": "fa-2", "blocks": [
      { "para": "Boots the Stage 1 AMI and runs Ansible against it." } ] } ] },
  { "pre": "resolve ─┬─► build-aws ────┬─► summary\n         └─► build-vmware ─┘",
    "scale": "flow" }
] }
```

Block types: `para` (+`muted`), `list` (+`tight`), `box`, `panels`, `cols`,
`table` (+`compact`, per-row `tone`, per-cell `tone`/`rowspan`), `pre`
(+`scale`), `pillars`, `buttons`, `shot`, `legend`, `stats`. Prose passes
through unescaped, so inline `<strong>`, `<code>` and `&mdash;` work.

**Show, don't list.** A deck of only tables and bullets describes a project
instead of showing it:

- `shot`: a framed screenshot (`size` `sm|md|lg`), with `alt` (required), `url`
  for the frame's address bar, `href`, `caption`, and
  `markers: [{"n": 1, "x": 30, "y": 40}]` placed in % of the image.
- `legend`: the numbered key to a shot's markers; put it in the next `cols` column.
- `stats`: big-number tiles. Real counts only, read from the repo.
- `buttons`: end the deck with links to the case study and the repo.

Screenshots go in `_deploy/presentations/<slug>/assets/`, rendered from the
committed `_deploy/` files with the same Playwright environment as
`screenshot_deck.py`.

What the renderer does that hand-writing does not:

- **A `box` inside `panels` renders as `<p><strong>…</strong> …</p>`**, not a
  `.box`, because a box in a `.split-panel` overlaps the next block (4a).
- **Rejects a tone the shared sheet does not define**: `{"box": "purple"}`
  fails loudly instead of rendering as nothing.
- **Emits the local CSS the blocks need**, derived from the shared rules, only
  for the blocks actually used.
- **Catches malformed tables**: a row whose cell count does not match the
  headers, counting `rowspan`.

Render blocks on their own while drafting:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/blocks.py --blocks slide.json
python3 ${CLAUDE_SKILL_DIR}/scripts/blocks.py --demo
```

### 4. Writing slides by hand

Only when a slide needs something `blocks` has no type for. Use the house
components rather than new CSS; `layout-fix.css` already styles:

- `.box` + `box-navy|blue|green|yellow|red`: the callout of choice
- `.cols split-panels` + `.split-panel split-panel-navy|blue|green|yellow|red`
- `.pill pill-navy|blue|green|yellow|red`, `.btn`
- `.decision-branch`, `.branch-box`, `.diamond-options` for decision trees
- `.today-pillars` / `.before-pillars` for before-and-after framing
- `.agenda-grid`/`.agenda-card`, `ul.tight`, `.cell-green|orange|red|yellow`
  and `.row-*` for table shading, plain `<table>`

Per-deck CSS goes in an inline `<style>` in that deck. **Never edit
`layout-fix.css`**: every deck shares it. Hand edits are lost on the next
`scaffold_deck.py --force`, so prefer adding the content to the plan.

### 4a. Layout rules that bite

The first four once cost a full deck rebuild after it was reported as
"inconsistent font sizing, some pages have content over each other". None
show up in a structural check, and all five are checked by `validate_deck.py`.

**Render the deck before you ship it** where you can (section 5a). The rules
explain *why* a slide is broken once you see that it is.

**1. Never put a `.box` inside a `.split-panel`.** `.split-panel` is
`height: 100%` with no `overflow` handling, and a nested `.box` adds its own
margin and a `:hover` transform, so it escapes the panel and lands on whatever
follows. Put only `h3` + `p`/`ul.tight` in a panel; for emphasis use
`<p><strong>…</strong> …</p>`.

**2. Size everything with `clamp(<rem>, <vw>, <rem>)`, never a bare `em`.**
`layout-fix.css` sizes every element that way, so the deck scales as one set.
Derive a smaller variant from the shared rule: `.reveal table` is
`clamp(0.825rem, 1.25vw, 1.075rem)`, so a compact table is
`clamp(0.7rem, 1.06vw, 0.92rem)`. An `em` on an inline child of a clamped
parent is fine; an `em` on a component is a bug.

**3. ASCII diagrams need `white-space: pre`.** The shared `.reveal pre` sets
`pre-wrap` + `word-break: break-word`, which wraps a wide diagram mid-line.
Use the `pre` block (it adds the guard) and keep lines short: past ~70
columns, use `"scale": "flow-sm"`; past 118 the renderer refuses it.

**4. Reuse a house component before inventing a class.** A class with no rule
behind it renders as nothing; a deck once shipped a `.cell-blue` when the
sheet only has `cell-green|yellow|orange|red`.

**5. Content must start below the fixed top bar.** The "Back to Walkthroughs"
bar is `position: fixed` and `--deck-bar-h` (54px) tall. Slides are absolutely
positioned at `top: 0`, so padding on `.reveal` does nothing; the offset has to
be in the section's own top padding: `calc(var(--deck-bar-h) + 3vh)`. A deck
once shipped with the bar covering every slide's heading because the padding
was on `.reveal`. If you change the bar's height, change `--deck-bar-h`, and
never override the section's top padding in a deck's own `<style>`.
`validate_deck.py` checks the shared rule; `screenshot_deck.py` measures
whether any slide's first element starts under the bar.

### 5. Validate — nothing in CI looks at a deck

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_deck.py --repo-root . --deck <slug>
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_deck.py --repo-root . --all
```

**Structure:** the slide count against the nav label, every agenda target in
range, the inline scripts parsing under `node --check`, tag balance, every
relative `href`/`src` resolving from the deck's folder, the "Back to
Walkthroughs" link present, `layout-fix.css` linked, and the deck registered
on the Walkthroughs page.

**Layout**, per section 4a: `.box` in a `.split-panel` (a FAILURE), local font
sizes that skip `clamp()`, wide `<pre>` blocks, classes with no rule, and slide
padding that doesn't clear the fixed top bar (a FAILURE).

### 5a. Render it and look at it

The validator reads the source. A browser is the only way to catch a slide that
is simply too tall.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/ensure_render_env.py      # once per machine
python3 ${CLAUDE_SKILL_DIR}/scripts/screenshot_deck.py --repo-root . --deck <slug>
```

`ensure_render_env.py` is idempotent and works on Windows, macOS and Linux. It
creates a venv in the user cache (`~/.cache/deck-render` on Linux), installs
`playwright`, downloads the Firefox build Playwright pins, checks a browser
launches, and writes a descriptor the screenshot tool reads.

On Linux it also tries to supply missing system libraries without root, by
downloading the providing packages from public mirrors into a user-owned
prefix. On Fedora/WSL that is not always enough; if it cannot finish, it prints
the exact `sudo dnf install …` line to run, and decks can't be rendered until
then. Fall back on `validate_deck.py` and say so.

`screenshot_deck.py` writes a PNG per slide and measures overflow at several
viewports (default `1920x1080,1600x900,1366x768`). **Check the smallest**: a
deck can fit at 1920x1080 and run over at 1366x768, the most common projector.

> Both scripts download a lot on first run (a venv and a browser). Run
> `ensure_render_env.py` in the background; it can exceed a short timeout.

### 6. Register it

1. Add an `<a class="card">` to `_deploy/walkthroughs/index.html`, pointing at
   `../presentations/<slug>/index.html`. The validator reports a deck missing
   from it.
2. On the case study's `_deploy/docs/<slug>/index.html`, uncomment the
   "Walkthrough slides" button in `.project-links`.

## Deck shape by deck type

The agenda skeleton `deck_facts.py` prints:

**`overview`**: for someone deciding in five minutes whether to read more.

1. The problem, in one slide
2. What I built
3. How it works, at a glance
4. Results: what it gives you
5. Stack and links

**`deep-dive`**: for an engineer who will ask "why?".

1. The problem and the constraints
2. Architecture: the components and how they fit
3. How it works, step by step
4. Design decisions and the trade-offs behind them
5. What went wrong, and what I changed
6. Next steps
7. Links: repo and case study

**`talk`**: for a room that wants a story.

1. The itch: why I started
2. The first version, and where it broke
3. The idea that fixed it
4. How it works now
5. What I learned
6. Try it yourself: links

## Honesty rules

A deck is a public claim about Mark's work, and it gets quoted back in
interviews.

- Every fact comes from the case study or the project's repo. Never invent
  results, metrics, users, employers or dates.
- If a project is in progress, the deck says so. Don't present planned work as
  done.
- If a slide needs something the case study doesn't cover, ask the user or
  leave the slide out. Don't fill it with something plausible.
- Don't cite a page you haven't opened. `validate_deck.py` catches a link that
  doesn't resolve, not a claim the page doesn't make.

## Verified against

`_deploy/presentations/portfolio-site/index.html`, generated by
`scaffold_deck.py` from its committed `_src/deck.plan.json`. It is the
reference shell: the scaffolder copies its reveal.js init, deck-nav and
agenda-navigation script verbatim (`--like portfolio-site`, the default), and
`validate_deck.py --all` passes with no warnings.
