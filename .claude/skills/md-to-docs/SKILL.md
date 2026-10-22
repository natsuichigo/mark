---
name: md-to-docs
description: Convert Markdown files OR PDFs into portfolio-themed, MkDocs-Material-style HTML case-study pages for Mark's portfolio site (the natsuichigo/mark GitHub Pages repo, _deploy/docs/<project>/). This skill is vendored INSIDE that repo at .claude/skills/, so it is available to anyone who clones it. Use this whenever the user wants to write up a project as a case study, turn .md docs or .pdf documents into styled .html pages for the portfolio, convert a PDF to Markdown for publishing, add a new project to the Projects page, or add/update pages in an existing case study (portfolio-site, packer-image-pipeline, ansible-ee-pipeline, platform-lab, or any other set under _deploy/docs/).
---

# Markdown / PDF → Case-Study Pages

Converts normal Markdown into the exact HTML format and styling used in
`natsuichigo/mark/_deploy/docs/<project>/*.html` (the `portfolio-site/` set is
the reference: HTML that clones the MkDocs-Material look, not an actual
`mkdocs build`). Producing byte-compatible output means new pages fit in
seamlessly next to existing ones.

PDFs go through Markdown to get there; there is no PDF→HTML shortcut:

```
PDF --(pdf_to_md.py)--> _src/*.md --(md_to_page.py)--> <slug>.html
```

The Markdown is the deliverable of the first step, not a hidden temp file: it
gets committed to `_src/`, reviewed, and edited. PDF text extraction is lossy
(see "Workflow C"), so that review is a required step.

## When to use this skill

- The user wants a **project written up as a case study** on the portfolio →
  Workflow B (new project), using the case-study page set below.
- The user gives you `.md` files (from any repo, path or scratch location) and
  asks to publish them as pages in the portfolio.
- The user gives you a **PDF** and wants it published → **Workflow C**, which
  converts it to Markdown first.
- The user wants to add or update a page in an existing case study → Workflow A.

Always **confirm which project (existing or new) the page belongs in** (step 0
below) rather than guessing from the file's origin or content.

## Facts come from the project, not from memory

A case study is public and is read by people deciding whether to hire Mark.
Every claim on a page (what was built, which tools, which numbers, what went
wrong) must come from the project's own repository: its README, docs, workflows
and code. Read them before writing.

- Never invent experience, results, metrics, employers or dates.
- If something the page needs is not in the repo (a result, a reason, a
  personal opinion), ask the user, or leave a clearly marked `TODO` for them.
- Be honest about status: a project that is in progress says so.

## The case-study page set

Every project gets the same four pages, so the Projects section reads as one
set. Use these slugs, titles and sections in `docs.config.json`:

| Slug | Title | Section | What it covers |
|---|---|---|---|
| `overview.html` | Overview | The Project | The problem, what was built, the stack, a link to the repo |
| `architecture.html` | Architecture | The Project | Components, repo layout, how they fit together |
| `how-it-works.html` | How It Works | Deep Dive | The pipeline or workflow, step by step |
| `lessons.html` | Lessons & Next Steps | Deep Dive | Decisions and trade-offs, what went wrong, what is next |

A project with more to say can add pages; `portfolio-site` has five. Keep the
first two and the last one.

Tone: first person ("I built…"), short sentences, specific. Lead with what the
project does and why it matters, then how.

## Quick start (the simple version)

Think of it as 4 steps: **figure out the project → get its config → write the
markdown → build and validate.**

0. **Figure out which project the page belongs to: ask, don't assume.**
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/scaffold_project.py --repo-root . --list
   ```
   - Picked an **existing** project → step 1.
   - **New** project → Workflow B below, then come back to step 2.

1. **Get that project's `docs.config.json`.** Every project in this repo
   commits one at `_deploy/docs/<project>/_src/docs.config.json`. Reuse it.
   (`extract_config.py` can rebuild one from a live page if it is ever lost.)

2. **Write the Markdown like a normal doc**, starting with a title line and a
   one-line subtitle, then `##` sections:

   ```markdown
   # How It Works
   One build, from a workflow run to a published, validated image.

   ## Validation Inside the Build
   Each OS has a validator in `tests/`...
   ```

3. **Register the page and build the set.** Add one entry to `nav[]` (slug,
   title, section), save the Markdown as `_src/<slug-without-.html>.md`, then:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/build_project.py --project <project>
   python3 ${CLAUDE_SKILL_DIR}/scripts/validate_pages.py --project <project>
   ```

**One thing to remember:** the sidebar and prev/next links are baked into
*every* page as static HTML. Whenever you add, remove, rename or reorder a page,
**every** page in that set must be regenerated, which `build_project.py` always
does. It refuses to build a partial set, and `validate_pages.py` catches the
inconsistency if one slips through anyway.

## The repo

```bash
git clone https://github.com/natsuichigo/mark.git
cd mark
```

If the user hasn't said where their checkout is, ask rather than guessing a
path; the scripts take `--repo-root`, and writing into the wrong tree is silent.

| Branch | Role |
|---|---|
| `main` | **The one that publishes.** `deploy-pages.yml` triggers on pushes here, for paths `_deploy/**` and the workflow file |
| feature branches | Where work happens; merged into `main` through a pull request |

Pull requests into `main` build the site but do not deploy it, because GitHub
Pages has one live deployment per repository.

Contribution loop:

1. Work on a feature branch and open a pull request into `main`.
2. Run `validate_pages.py` yourself. **Nothing in CI validates these pages**:
   no link checker, no HTML validator, no sidebar test. The deploy workflow
   uploads `_deploy/` exactly as committed.
3. Commit the Markdown source **and** the generated HTML in the same commit.
4. Commit messages: a short type prefix and an imperative summary, e.g.
   `docs: add lessons page to the packer case study`.

Preview locally with `python3 -m http.server -d _deploy`; relative paths
resolve, so styling and navigation render as they will live.

## Where this skill lives

```
mark/.claude/skills/md-to-docs/
├── SKILL.md
├── scripts/
│   ├── pdf_to_md.py           PDF → Markdown for _src/
│   ├── md_to_page.py          one Markdown file → one page
│   ├── build_project.py       every page in a set, from _src/
│   ├── validate_pages.py      the review step
│   ├── scaffold_project.py    a new case-study folder
│   └── extract_config.py      rebuild a docs.config.json from a live page
└── examples/docs.config.example.json
```

Invoke the scripts with repo-relative paths from the repo root, or through
`${CLAUDE_SKILL_DIR}`, which resolves to this folder. Improving the skill is an
ordinary change to the same repo.

## Repo layout you're targeting

```
mark/
├── .claude/skills/md-to-docs/     # this skill
├── .claude/skills/docs-to-deck/   # companion: case study → walkthrough deck
├── .github/workflows/deploy-pages.yml
└── _deploy/                       # THIS FOLDER IS THE PUBLISHED SITE
    ├── index.html                 # Home (hand-written)
    ├── projects/index.html        # one card per case study (hand-written)
    ├── walkthroughs/index.html    # one card per deck (hand-written)
    ├── about/index.html           # skills, certifications, contact
    ├── assets/
    │   ├── theme.css              # THE BRAND: --brand-* colours for every page
    │   ├── hub.css                # layout for the hand-written hub pages
    │   ├── project-colors.css     # GENERATED: per-project button colours (project_colors.py)
    │   ├── favicon.svg / favicon-32.png / apple-touch-icon.png  # browser-tab and phone icons
    │   ├── og-image.png           # 1200x630 link-preview card (LinkedIn, Slack, Teams, X)
    │   ├── logo.svg / logo-dark.svg
    │   ├── site-chrome.css / .js  # the Home · Projects · Walkthroughs · About nav
    │   └── <project>-docs.css     # per-project content component CSS
    └── docs/
        ├── theme.local.css        # maps theme.css onto MkDocs vars (do not touch)
        ├── assets/stylesheets/main.*.min.css  # MkDocs-Material core CSS (do not touch)
        └── <project>/             # one folder per case study
            ├── index.html         # the case study's landing page (card grid)
            ├── overview.html      # content pages generated by this skill
            ├── ...
            ├── assets/            # per-project images, incl. ones pulled out of
            │                      # a PDF (here, NOT in _src/, so pages reach them)
            └── _src/              # the .md sources plus docs.config.json
```

**Commit the Markdown sources and the config.** Without them the generated HTML
is the only source of truth. Note `_src/` sits inside `_deploy/`, so it is
published too: fine for prose, but never put anything private there.

`_deploy/` **is** the published site, so a change there goes live on the next
merge to `main`. Confirm before writing if the user has not clearly asked to
publish.

## Content-page template — exact spec

Every content page (e.g. `docs/portfolio-site/overview.html`) has this fixed shape:

1. `<head>`: title `"{Page Title} — {Site Name}"`, Google Fonts preconnect,
   `rel=prev`/`rel=next` links (drive the page-nav bar), then 3 stylesheets:
   - `{docs_root}assets/stylesheets/main.484c7ddc.min.css`: MkDocs core (shared, at `docs/`)
   - `{docs_root}theme.local.css`: maps `assets/theme.css` onto MkDocs variables
   - `{deploy_root}assets/<project>-docs.css`: this project's content components
2. `.md-toggle`/`.md-overlay` drawer plumbing (verbatim, always present).
3. `<header class="md-header md-header--shadow">`: logo link to `./index.html`,
   hamburger toggle, site name + page name, then `#hdr-page-nav` and the
   **verbatim inline script** that renders Prev | Projects / `<Project>` / Home | Next
   from the `rel=prev`/`rel=next` links (or the `<data id="pnav-prev/next">`
   overrides at the bottom of `<body>`).
4. `.md-sidebar--primary`: flat `<ul class="md-nav__list">` of every page in the
   project, `<li class="md-nav__item md-nav__section-label">Group</li>` between
   groups, `md-nav__link--active` on the current page.
5. `.md-sidebar--secondary`: empty `<ul id="pd-toc">`, filled client-side from
   every `.md-typeset h2` (so **only `##` headings appear in the on-page TOC**).
6. `.md-content > article.md-content__inner.md-typeset {prefix}-typeset`:
   `<h1 class="page-title">` + optional `<p class="page-sub">`, then the body.
7. `<footer class="md-footer">` with `.md-copyright` = `footer_name`, e.g.
   `"Packer Golden Image Pipeline — Mark"`.
8. Verbatim TOC-builder + scroll-spy script, back-to-top button + script, and
   the `<data id="pnav-…">` elements when applicable.

Depth matters for relative paths: for `docs/<project>/*.html` (depth 2 from
`_deploy/`), assets under `docs/` need one `../`, assets under `_deploy/` need
two. The script computes this from the config's `depth`; don't hand-compute it.

## Content styling components available

The per-project CSS (e.g. `portfolio-site-docs.css`) styles, inside
`.{prefix}-typeset`: tables, `<div class="callout">` / `callout warn`,
`<span class="badge badge-blue|green|amber">` + `.badge-row`, `.flow` /
`.flow-step` / `.flow-num` / `.flow-text` / `.flow-arrow` for step diagrams,
`.action-card`, `.role-card`, `.stage-box` (+ `.s1`/`.s2`), `.check-group` /
`.check-group-title` / `.check-list` / `.check`, `<pre class="dir-tree">` (+
`.hl`/`.cm` spans), `.arch-diagram-wrap`/`.arch-diagram`. Write these as raw
HTML inside the Markdown; Python-Markdown passes raw HTML blocks through.

The existing case studies show each one in use; copy from them.

## Project button colour

Each case study's buttons and icon badge take the brand colour of the main
platform or application the project is built on, e.g. Ansible → Red Hat red,
Kubernetes → Kubernetes blue, Packer → Packer blue. Set it with a `"brand"` key
in the project's `_src/docs.config.json`:

```json
"brand": "ansible"      // a known tool name
"brand": "#7b42bc"      // or any hex colour
```

- **Pick the tool the project is mainly *about*,** not every tool it uses
  (a Packer pipeline that runs Ansible is `packer`). If it is unclear, ask the
  user. `project_colors.py --list-tools` lists the known names.
- `build_project.py` regenerates `_deploy/assets/project-colors.css` after
  every build, so changing the brand is: edit the config → build → validate.
  Never edit `project-colors.css` by hand.
- Colours are darkened automatically, keeping the hue, until white button text
  is readable (4.5:1).
- Where it applies: cards on Home and Projects that link to `docs/<project>/`
  (matched by link, no class needed), and the project's own hub page through
  `<body data-project="<project>">`. Amber `.btn.alt` buttons (walkthrough
  slides) stay amber. A project without a brand uses the default blue.
- `validate_pages.py` checks the chain: a known brand, an up-to-date
  `project-colors.css`, `hub.css` importing it, and `data-project` on the hub.

## Favicon and link previews

Every page carries a managed block before `</head>` (between
`<!-- site-meta: … -->` and `<!-- /site-meta -->`): the favicon, the
apple-touch-icon, and Open Graph / Twitter tags so a shared link shows a
title card with `assets/og-image.png`. `site_meta.py` writes it from each
page's own `<title>` and description (or subtitle).

- `build_project.py` runs it after every build, and `scaffold_deck.py` for new
  decks. After **hand-editing** a hub page (Home, Projects, About, a project
  `index.html`), changing its `<title>` or description, or adding a new page,
  run `python3 ${CLAUDE_SKILL_DIR}/scripts/site_meta.py`.
- Never edit inside the block; it is replaced on every run.
- `validate_pages.py` fails a page whose block is missing or stale;
  `site_meta.py --check` covers the pages outside `docs/` too.

## Workflow

### 0. Which project does this page belong to?

1. List what exists and ask the user to choose:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/scaffold_project.py --repo-root . --list
   ```
2. Existing project → **Workflow A**.
3. New project → confirm the slug, then **Workflow B**, then A.
4. A **PDF** source → **Workflow C** first; the project question still comes
   first, because the output goes into that project's `_src/`.

### A. Adding or updating pages in an existing project

1. Open `_deploy/docs/<project>/_src/docs.config.json`. (If it is missing,
   rebuild it from a live page with `extract_config.py --page … --out …` and
   review the nav order it copies.)
2. Write or update the Markdown in `_src/`: `# Page Title`, an optional
   one-paragraph subtitle, then `##` sections. Don't repeat the H1 in the body.
3. A new page: add its `nav[]` entry first, then build the whole set:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/build_project.py --project <project>
   ```
   `md_to_page.py --config … --md … --out …` converts a single page, but only
   use it for a text edit; any nav change needs the whole set.
4. A new page also needs a card on the project's `index.html` (hand-written).
5. Validate:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/validate_pages.py --project <project>
   ```

The generator auto-installs the `markdown` pip package on first run if it is
missing.

### B. A new project case study

1. **Read the project first.** Its README, docs, workflows and the parts of the
   code the pages will describe. The case study is built from these.
2. Pick a kebab-case slug and ask the user for a display name if it is not
   obvious. Then scaffold, cloning the reference set's conventions:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/scaffold_project.py --repo-root . \
     --project my-project --like portfolio-site \
     --site-name "My Project" \
     --docidx-label "My Project" \
     --footer-name "My Project — Mark" \
     --brand terraform
   ```
   `--brand` is the project's main platform/tool (see "Project button
   colour"); ask the user if it is not obvious. This writes:
   - `_deploy/docs/<project>/index.html`: cloned from `--like`, retitled, with
     an empty card grid and the repo/slides buttons commented out.
   - `_deploy/assets/<project>-docs.css`: cloned CSS with the
     `.{prefix}-typeset` class re-targeted (prefix derived from the slug, or
     `--prefix`).
   - `_deploy/docs/<project>/_src/docs.config.json`: an empty `nav[]`, plus
     `"brand"` when given.
   - `_deploy/assets/project-colors.css`: regenerated with the new colour.
   The cloned `index.html` keeps `<body data-project="<project>">`.
3. Fill in the config's `nav[]` with the four case-study pages (see "The
   case-study page set") and write the four Markdown files in `_src/`.
4. Build and validate the set (Workflow A steps 3 and 5).
5. Edit the new `index.html`: the subtitle, the "View repo on GitHub" button in
   `.project-links`, and one card per page with a `section-label` between
   groups. The other case studies' index pages show the finished shape.
6. Add a card for the project to `_deploy/projects/index.html` (title, one-line
   summary, tech-stack chips, case study and repo buttons), and to the Featured
   row on `_deploy/index.html` if the user wants it featured.
7. **Offer a walkthrough deck** with the companion `docs-to-deck` skill. Don't
   build one unasked.

### C. Converting a PDF

`pdf_to_md.py` turns the PDF into Markdown in `_src/`; from there it is an
ordinary Workflow A. **The Markdown is reviewed and committed**: it becomes the
source the pages are rebuilt from.

1. Decide the shape first: **one page** or **a page per chapter**? Ask if it
   isn't obvious.

2. Convert. One page:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/pdf_to_md.py \
     --pdf ~/Downloads/design-notes.pdf \
     --out _deploy/docs/my-project/_src/design.md \
     --drop-heading "Table of Contents" \
     --sub "The design decisions behind the pipeline."
   ```

   Or one page per section, writing the `nav[]` entries as it goes:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/pdf_to_md.py \
     --pdf ~/Downloads/report.pdf --pages 3-40 \
     --split h1 --out-dir _deploy/docs/my-project/_src \
     --config _deploy/docs/my-project/_src/docs.config.json --update-config \
     --section "Deep Dive"
   ```

   `--split h1` gives one page per `#`, `--split h2` per `##`. When splitting,
   each section's heading becomes its page's `#` and its children are promoted
   a level, so they stay `##` and keep showing in the on-page TOC.

3. **Read the report it prints, then read the Markdown.** The report names the
   files with problems, because these defects are invisible until someone reads
   the live page:

   | Report says | What to do |
   |---|---|
   | No `##` headings in *file* | Empty TOC and no right sidebar. Promote real sections to `##`. |
   | Table header wrapped into the first body row | Merge that row back into the header. |
   | Almost no body text in *file* | A heading with nothing under it. Delete the file and its `nav[]` entry. |
   | *n* bold-only lines look like headings | Rerun with `--bold-headings`. |
   | Pages with no text extracted | Scanned pages. `--ocr force`, or transcribe by hand. |
   | Extra `#` demoted to `##` | Fine for one page; if they are chapters, use `--split h1`. |
   | IGNORED on the *layout* engine | That flag only works on `--engine legacy`. |

   Then read the `.md` for what no script can detect: **bullets that lost their
   `-`**, headings that extracted as body text, commands and config that need
   fencing as code blocks, and interleaved text from two-column layouts.

4. Register the slugs in `docs.config.json` if you didn't use `--update-config`,
   then build and validate as usual.

5. Images worth keeping must land next to the generated `.html`, **not** in
   `_src/`; `--image-dir` is required for that reason:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/pdf_to_md.py --pdf notes.pdf \
     --out _deploy/docs/my-project/_src/design.md \
     --images --image-dir _deploy/docs/my-project/assets \
     --image-href ./assets --image-prefix my-project
   ```

   Alt text comes out as a placeholder (`Figure from PDF page 12`); replace it
   with a real description.

6. Commit the `.md` to `_src/`. The **PDF itself is usually not committed**:
   `_src/` is published. Commit it only if it is small and meant to be public.

#### Which engine you get

`pymupdf4llm` ships two back ends and chooses at import time. The newer
**layout** engine is much better at headings and tables, so let it pick unless
you need a legacy-only flag (`--margin-top`/`--margin-bottom`,
`--table-strategy`). The script passes each engine only its own flags and
reports anything it had to ignore; the report names the engine that ran.

## Script reference

`scripts/pdf_to_md.py`: converts a PDF into Markdown shaped for
`md_to_page.py` (one leading `# Title`, optional subtitle, `##` sections).
Auto-installs `pymupdf`/`pymupdf4llm` on first run.
- **Heading levels.** Promotes everything if the shallowest heading is deeper
  than `#`; keeps the first `#` as the title and demotes later ones to `##`.
  Strips `**bold**` markers out of heading text.
- **Page furniture.** Drops running headers/footers, bare page numbers and the
  `-----` page-break rules.
- **Splitting.** `--split h1|h2` writes one file per section and prints/appends
  the `nav[]` entries.
- **OCR.** Pages with no text layer go through `tesseract` (`--ocr auto`, the
  default; `force` for every page, `off` to disable).
- **Images.** `--images` writes them and rewrites the refs relative to the page,
  renaming them `<prefix>-p012-03.png`.
- **A report** naming what needs review, per file.
- Flags: `--pdf`, `--out` / `--out-dir`, `--split`, `--pages`, `--title`,
  `--sub`, `--drop-heading` (repeatable), `--bold-headings`, `--unwrap`,
  `--keep-repeats`, `--keep-tags`, `--repeat-threshold`, `--preamble-min`,
  `--margin-top`/`--margin-bottom`, `--table-strategy`, `--engine`,
  `--images`, `--image-dir`, `--image-href`, `--image-prefix`, `--image-dpi`,
  `--ocr`, `--ocr-lang`, `--ocr-dpi`, `--config`, `--update-config`,
  `--section`.

`scripts/md_to_page.py`: converts one Markdown file into one content page.
- Splits a leading `# Title` + subtitle paragraph out of the body.
- Renders the body with Python-Markdown (`extra`, `sane_lists`, `tables`,
  `fenced_code`, `toc`).
- Looks up the file's slug in `nav[]` to build the sidebar and compute
  prev/next from neighbouring entries (one flat sequence; sections are labels).
- The **subtitle** is escaped, then inline code spans are converted, so
  backticks work but no other Markdown does. A `nav[]` entry may carry a
  `"sub"` key that overrides the subtitle.
- The header's page-nav links to `projects/index.html` ("Projects"), the
  project's own index, and Home.
- Flags: `--config`, `--md`, `--out`, `--slug`.

`scripts/build_project.py`: regenerates EVERY page in a set from `_src/`.
- Converts `_src/<slug>.md` → `<slug>.html` for each `nav[]` entry.
- Then regenerates `project-colors.css` from every config's `"brand"`, and
  re-applies the favicon / link-preview block (`site_meta.py`).
- **Refuses to build a partial set**: a nav entry with no source is reported and
  nothing is written. Orphan sources not in `nav[]` are reported too.
- Flags: `--repo-root`, `--deploy-dir`, `--project`, `--src-dir` (default
  `_src`), `--check` (report source coverage only).

`scripts/validate_pages.py`: the review step, because nothing in CI checks
these pages.
- Sidebar agreement across pages, exactly one active link, an unbroken
  prev/next chain, internal links and relative assets resolving, unrendered
  Markdown tables and code spans, placeholder tags the browser eats, tag
  balance, `_src/` source coverage, and the project button colour (brand
  known, `project-colors.css` current, `data-project` on the hub), the
  favicon / link-preview block on every page, and every live relative link on
  the hub page (e.g. a "Walkthrough slides" button uncommented before its deck
  exists).
- **Two severities.** With `_src/docs.config.json` present, structural findings
  are FAILURES; without one, WARNINGS. Broken links, unresolvable assets,
  unrendered Markdown and unbalanced tags always fail.
- Flags: `--repo-root`, `--deploy-dir`, `--project`, `--all`, `--quiet`.
- Exit 0 on warnings, 1 on any failure.

`scripts/scaffold_project.py`: creates a new project folder cloned from an
existing one's CSS and `index.html`, plus a starter config.
- Flags: `--repo-root`, `--deploy-dir` (default `_deploy`), `--project`,
  `--like`, `--site-name`, `--docidx-label`, `--footer-name`, `--prefix`,
  `--config-out`, `--brand`, `--list`, `--force`.
- An **empty** target folder is accepted without `--force`. Real files require
  `--force`, which overwrites `index.html` and the CSS but never touches
  generated pages or `_src/`.

`scripts/project_colors.py`: generates `_deploy/assets/project-colors.css`
from each config's `"brand"` key (see "Project button colour").
- A known tool name (`ansible`, `kubernetes`, `packer`, `terraform`, `aws`,
  `docker`, `github`, …) or a hex colour; darkened for readable white text.
- Run automatically by `build_project.py` and `scaffold_project.py --brand`.
- Flags: `--repo-root`, `--deploy-dir`, `--check` (exit 1 if out of date),
  `--list-tools`.

`scripts/site_meta.py`: adds / refreshes the favicon and link-preview block on
every page of the site (see "Favicon and link previews"). Skips redirect stubs.
- Run automatically by `build_project.py` and `scaffold_deck.py`.
- Flags: `--repo-root`, `--deploy-dir`, `--check` (exit 1 if any page is
  missing or stale).

`scripts/extract_config.py`: rebuilds a `docs.config.json` from a deployed
page (title, CSS file, typeset prefix, index label, footer, depth and the nav
list read from the sidebar).
- Flags: `--page`, `--out` (default: stdout).

## Verified against

All four case studies (`portfolio-site`, `packer-image-pipeline`,
`ansible-ee-pipeline`, `platform-lab`) are generated by `build_project.py` from
`_src/`, and `validate_pages.py --all` passes with no warnings. Re-run it after
changing a script.
