# How Deployment Works
From a push to `main` to a live page, in one short workflow.

One workflow publishes the site: `.github/workflows/deploy-pages.yml`. It has two
jobs. `build` uploads `_deploy/` as a Pages artifact, and `deploy` publishes it.
Nothing in it builds or changes a page.

<div class="flow">
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Push to <code>main</code></strong><span>Touching <code>_deploy/**</code> or the workflow file</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong><code>build</code> job</strong><span>Checkout → <code>configure-pages</code> → upload <code>_deploy/</code> as the Pages artifact</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong><code>deploy</code> job</strong><span><code>needs: build</code>, <code>environment: github-pages</code> → <code>actions/deploy-pages</code> → a run summary with links to the live site</span></div></div>
</div>

## What Triggers It

```yaml
on:
  push:
    branches: [main]
    paths: ['_deploy/**', '.github/workflows/deploy-pages.yml']
  pull_request:
    branches: [main]
    paths: ['_deploy/**', '.github/workflows/deploy-pages.yml']
  workflow_dispatch:
```

- **Branch-gated.** Only `main` publishes. The `portfolio` ruleset in my
  [github-rulesets](https://github.com/natsuichigo/github-rulesets) repo protects it:
  changes go through a pull request, and force-pushes and deletion are blocked.
- **Path-gated.** A change outside `_deploy/`, such as a `README.md` edit, does not
  deploy. `workflow_dispatch` runs it by hand when needed.
- **Pull requests build but do not publish.** GitHub Pages has one live deployment
  per repository, so publishing an unmerged PR would overwrite the live site. The
  `deploy` job is skipped for pull requests, and the built artifact stays on the run
  for inspection.

## Permissions

```yaml
permissions:
  contents: read      # checkout
  pages: write        # publish to Pages
  id-token: write     # OIDC, required by deploy-pages
```

The workflow needs no secrets. The Pages source must be set to **GitHub Actions**
(Settings → Pages → Source).

## Concurrency

```yaml
concurrency:
  group: pages-${{ github.event.pull_request.number || 'production' }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

Production deploys share one group and queue, so two merges never race. Each pull
request gets its own group and cancels its superseded runs.

## Pinned Actions

Every action is pinned to a full commit SHA rather than a tag, for example
`actions/checkout@de0fac2e…`. A tag can be moved to point at different code; a SHA
cannot.

## What CI Does Not Check

<div class="callout warn">
<p><strong>Nothing in CI validates the pages.</strong> There is no link checker or HTML validator in the workflow, so a broken link would deploy. I run the checks myself before pushing: <code>validate_pages.py</code> for case studies, <code>validate_deck.py</code> and <code>screenshot_deck.py</code> for decks. Adding a link check to the <code>build</code> job is on the <a href="./lessons.html">next steps</a> list.</p>
</div>
