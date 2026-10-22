# `_deploy/` — the published site

Everything in this folder is uploaded to GitHub Pages **as-is** by
`.github/workflows/deploy-pages.yml` on every push to `main`. There is no
build step: what you commit here is what visitors get.

## Structure

```text
_deploy/
├── .nojekyll              # required — stops Pages ignoring _-prefixed folders
├── index.html             # Home
├── 404.html               # GitHub Pages "not found" page (links via <base href="/mark/">)
├── projects/              # one card per case study
├── walkthroughs/          # one card per slide deck
├── about/                 # skills, certifications, contact
├── assets/
│   ├── theme.css          # THE BRAND — every colour on the site comes from here
│   ├── hub.css            # layout for the hand-written hub pages
│   ├── logo.svg           # monogram logo (white, for dark backgrounds)
│   ├── logo-dark.svg      # the same logo for light backgrounds (deck headings)
│   ├── favicon.svg, favicon-32.png, apple-touch-icon.png  # tab / phone icons
│   ├── og-image.png       # link-preview card; tags added by md-to-docs site_meta.py
│   ├── project-colors.css # GENERATED per-project button colours (project_colors.py)
│   ├── site-chrome.*      # shared Home · Projects · Walkthroughs · About nav
│   └── <project>-docs.css # content styles for one case study
├── docs/
│   ├── theme.local.css    # maps theme.css onto MkDocs-Material variables
│   ├── assets/stylesheets # MkDocs-Material core CSS (third-party, MIT)
│   └── <project>/         # one case study (sources in _src/)
├── presentations/         # reveal.js decks + the shared layout-fix.css
├── documentation/         # redirect → projects/ (old URL)
└── presentations_hub/     # redirect → walkthroughs/ (old URL)
```

## Editing

- **Case-study content pages** (`docs/<project>/*.html` other than
  `index.html`) are generated from `docs/<project>/_src/*.md`. Edit the
  Markdown, then run
  `python3 .claude/skills/md-to-docs/scripts/build_project.py --project <project>`
  and `validate_pages.py --project <project>`.
- **Decks** (`presentations/<slug>/index.html`) are generated from
  `presentations/<slug>/_src/deck.plan.json` by
  `.claude/skills/docs-to-deck/scripts/scaffold_deck.py`.
- **Hub pages** (`index.html`, `projects/`, `walkthroughs/`, `about/`, each
  case study's `index.html`) are hand-written. Edit them directly.

Anything under `_deploy/`, including `_src/`, is public once pushed.

Preview locally with `python3 -m http.server -d _deploy` from the repo root.
