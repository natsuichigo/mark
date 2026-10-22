# Overview
What this site is, why it has no build step, and the stack behind it.

This portfolio is a static GitHub Pages site. Every page you can open — the home
page, the project case studies, the slide decks — is served from **one folder,
`_deploy/`, on the `main` branch** of [natsuichigo/mark](https://github.com/natsuichigo/mark).
There is no static-site generator, no framework and no build step in CI.

The case-study pages look like a Material-for-MkDocs site, but they are plain HTML.
I write each page in Markdown, and a Python script vendored in the repo as a
Claude Code skill turns it into a page before I commit.

<div class="callout">
<p><strong>The one-sentence version.</strong> I commit HTML into <code>_deploy/</code> on <code>main</code>, and a GitHub Actions workflow uploads that folder to GitHub Pages exactly as it is.</p>
</div>

## Why Build It This Way

<div class="badge-row">
    <span class="badge badge-blue">No build step</span>
    <span class="badge badge-green">Markdown source</span>
    <span class="badge badge-amber">Checks run locally</span>
</div>

- **What I commit is what visitors get.** There is no generator version to pin, no
  theme plugin to upgrade, and nothing in CI that can turn a working page into a
  broken one.
- **Writing stays in Markdown.** Each case study keeps its Markdown sources in
  `_src/` next to the generated HTML, so a change is a Markdown edit and a re-run.
- **The tooling travels with the repo.** The generators live in `.claude/skills/`,
  so anyone who clones the repo, including Claude Code, has the same toolchain.

## The Stack

| Layer | What I used |
|---|---|
| Hosting | GitHub Pages, source set to **GitHub Actions** |
| Deployment | One workflow: `.github/workflows/deploy-pages.yml` |
| Page generator | `md_to_page.py` (Python + `markdown`), part of the `md-to-docs` skill |
| Slide decks | reveal.js, scaffolded and checked by the `docs-to-deck` skill |
| Styling | One brand file, `assets/theme.css`, read by every page and deck |
| Checks | `validate_pages.py`, `validate_deck.py` and a Playwright screenshot pass, run before I push |

## What Gets Published

The site root maps directly onto `_deploy/`:

| URL path | Folder | What it is |
|---|---|---|
| `/` | `_deploy/index.html` | Home page |
| `/projects/` | `_deploy/projects/` | One card per project case study |
| `/docs/<project>/` | `_deploy/docs/<project>/` | A case study: an index page plus generated content pages |
| `/walkthroughs/` | `_deploy/walkthroughs/` | One card per slide deck |
| `/presentations/<slug>/` | `_deploy/presentations/<slug>/` | A reveal.js deck |
| `/about/` | `_deploy/about/` | Skills, certifications and contact details |

## Where It Came From

The site started as a team-portal template: a documentation hub, handover decks,
a support portal that raised GitHub Issues, requests dashboards and a status page.
I kept the parts that suit a portfolio (the brand file, the Markdown-to-page
generator and the deck tooling) and removed the rest: the support portal, the
dashboards, the status page, eleven issue templates, five workflows and the
encrypted browser configs they needed. The [Lessons](./lessons.html) page covers
what that clean-up taught me.
