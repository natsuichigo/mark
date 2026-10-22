# The Claude Skills
md-to-docs and docs-to-deck: Markdown in, case-study pages and slide decks out.

The authoring tools are two [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills)
committed in the repo under `.claude/skills/`. A skill is a folder with a
`SKILL.md` that tells Claude Code when and how to use it, plus the scripts it runs.
Because they are in the repo, there is nothing to install: clone it, open Claude
Code in the folder, and the skills are available. The scripts also run on their own
with plain `python3`.

## md-to-docs: Markdown to a Case-Study Page

<div class="flow">
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Scaffold the project</strong><span><code>scaffold_project.py</code> creates <code>docs/&lt;project&gt;/</code>, its CSS, its index page and a starter <code>_src/docs.config.json</code></span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>Write the Markdown</strong><span>One file per page in <code>_src/</code>, plus one <code>nav[]</code> entry per page in the config</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>Build the set</strong><span><code>build_project.py --project &lt;project&gt;</code> regenerates every page</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>Validate</strong><span><code>validate_pages.py --project &lt;project&gt;</code> before committing</span></div></div>
</div>

A page's Markdown starts with a title and a one-line subtitle, then ordinary `##`
sections:

```markdown
# Architecture
The repo layout, the two kinds of page, and which files are generated.

## The Repository
...
```

`md_to_page.py` wraps that in the full page: header, sidebar, table of contents,
previous/next links and footer. Source files can also be PDFs: `pdf_to_md.py`
converts them to Markdown first, for review before publishing.

<div class="callout">
<p><strong>The sidebar is baked into every page.</strong> Adding, removing or reordering a page changes the sidebar on all of them, so <code>build_project.py</code> always rebuilds the whole set, never one page.</p>
</div>

### What the validator checks

<div class="check-group"><div class="check-group-title">Structure</div><div class="check-list"><span class="check">All pages share one sidebar</span><span class="check">Exactly one active link</span><span class="check">Unbroken prev/next chain</span><span class="check">Page skeleton intact</span></div></div>
<div class="check-group"><div class="check-group-title">Links</div><div class="check-list"><span class="check">Same-set .html links resolve</span><span class="check">Relative CSS/JS/images resolve</span></div></div>
<div class="check-group"><div class="check-group-title">Rendering</div><div class="check-list"><span class="check">No unrendered Markdown tables</span><span class="check">No literal code spans</span><span class="check">Clean subtitles</span></div></div>
<div class="check-group"><div class="check-group-title">Hygiene</div><div class="check-list"><span class="check">Tags balanced</span><span class="check">Every page has a Markdown source</span></div></div>

### Every case study has the same shape

| Page | What it covers |
|---|---|
| Overview | The problem, what I built, the stack, a link to the repo |
| Architecture | The main components and how they fit together |
| How It Works | The pipeline or workflow, step by step |
| Lessons & Next Steps | Trade-offs, what I would change, what comes next |

## docs-to-deck: Case Study to Walkthrough Deck

The second skill builds a reveal.js walkthrough deck from a project's published
case-study pages, so the slides and the pages tell the same story.

<div class="flow">
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Pick the audience</strong><span><code>overview</code> for a recruiter, <code>deep-dive</code> for a technical interview, <code>talk</code> for a meetup</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>Gather the facts</strong><span><code>deck_facts.py</code> lists the project's pages and an agenda shaped by the deck type</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>Write a deck plan</strong><span>JSON: slides as declared blocks; <code>scaffold_deck.py</code> renders them into the house components</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>Validate and look</strong><span><code>validate_deck.py</code> checks structure; <code>screenshot_deck.py</code> renders every slide in Playwright and measures overflow</span></div></div>
</div>

<div class="callout">
<p><strong>Why render screenshots?</strong> A slide that overflows still passes every structural check. The only reliable test is to render each slide at real viewport sizes and measure it, so the skill does exactly that.</p>
</div>
