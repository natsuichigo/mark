# Lessons & Next Steps
What the no-build approach costs, what the clean-up taught me, and what I would add next.

## Trade-offs of Having No Build Step

<div class="stage-box s1">
<h3>What it gives me</h3>
<ul>
<li>Deployment cannot break a page: CI uploads exactly what I committed.</li>
<li>No generator, theme or plugin versions to keep up to date.</li>
<li>A one-job workflow with no secrets.</li>
</ul>
</div>

<div class="stage-box s2">
<h3>What it costs</h3>
<ul>
<li>Generated HTML is committed, so diffs are larger than the Markdown change behind them.</li>
<li>The sidebar is baked into every page, so adding one page rewrites all of them.</li>
<li>Nothing in CI checks the pages; the checks only help if I run them.</li>
</ul>
</div>

## What the Clean-Up Taught Me

Turning a team portal into a portfolio was mostly removal, and removal is where
hidden dependencies show up.

- **A disabled step can still be load-bearing.** The template's deploy workflow had
  the step that generated a dashboard data file switched off, but a later step still
  failed the build if that file was missing. Deleting a "generated" file would have
  broken every deployment, including ones unrelated to the dashboard. I removed the
  generator, the check and the dashboard together.
- **Fewer moving parts, fewer secrets.** The template needed a personal access
  token, a GitHub App key, status-page tokens and a Teams webhook. The portfolio
  needs none, and its workflow drops to `contents: read`.
- **Rename URLs, keep the old ones working.** `/documentation/` became `/projects/`
  and `/presentations_hub/` became `/walkthroughs/`. Each old path keeps a small
  redirect page so existing links still land somewhere.
- **Change the tools, not just the pages.** The page generator and deck builder had
  the old paths and team wording built in. Updating the skills means the next case
  study comes out right without hand-fixing.

## Next Steps

| Next step | Why |
|---|---|
| Run a link checker in the `build` job | Catches broken links in CI instead of relying on me running the validators |
| Run `validate_pages.py` in CI on pull requests | Same checks, enforced on every change |
| A walkthrough deck for each project | Every case study gets a short visual version |
| A Platform Lab status page | Show the home lab's live health once it runs services worth monitoring |
