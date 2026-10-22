# Architecture
Three EE definitions, three workflows, and the composite actions they share.

## The Lifecycle

<pre class="dir-tree">
ci-base-latest  (core 2.18 / py3.13) ──┐
                                       ├──&gt; ci-dev ──&gt; dev repo  (vX, core216-vX)
ci-base-compat  (core 2.16 / py3.12) ──┘                    │
                                                            │  manual + approval
                                                            ▼
                                          ee-promote-prod ──&gt; prod repo (same tags)
</pre>

## Repository Layout

<pre class="dir-tree">
ansible-execution-image-pipeline/
├── <span class="hl">execution-environments/</span>
│   ├── base-core-2.18/            <span class="cm"># definition, validation.yml, latest-target-test.yml</span>
│   ├── base-core-2.16/            <span class="cm"># definition, validation.yml, compat-target-test.yml</span>
│   └── derived/                   <span class="cm"># definition template (__EE_BASE_IMAGE__), validation.yml</span>
└── .github/
    ├── <span class="hl">workflows/</span>
    │   ├── ee-build-dev.yml       <span class="cm"># push to dev / manual: build + test + push to dev</span>
    │   ├── ee-tech-preview.yml    <span class="cm"># manual: derived EE from a chosen base tag</span>
    │   └── ee-promote-prod.yml    <span class="cm"># manual + approval: copy tested tags to prod</span>
    ├── <span class="hl">actions/ee_build/</span>
    │   ├── build/pipelines/       <span class="cm"># ci-base-latest, ci-base-compat, ci-dev, prod-promote</span>
    │   ├── build/tasks/           <span class="cm"># resolve-image-tags, build-image, build-derived-ee</span>
    │   ├── setup/                 <span class="cm"># toolchain, registry login</span>
    │   ├── verify/                <span class="cm"># validate-image, target-test</span>
    │   ├── publish/               <span class="cm"># push-image-tags</span>
    │   └── summary/               <span class="cm"># write-run-summary</span>
    └── dependabot.yml             <span class="cm"># weekly GitHub Actions updates</span>
</pre>

## Three Repositories, Three Stages

<div class="stage-box s1">
<h3>Base and dev: built and tested automatically</h3>
<ul>
<li>A push to <code>dev</code> builds both base EEs, validates them, runs the target tests, then builds a derived EE on each.</li>
<li>Images go to the base and dev repositories with immutable version and SHA tags.</li>
<li>A non-production AAP points at the dev images for soak testing.</li>
</ul>
</div>

<div class="stage-box s2">
<h3>Prod: promoted, never rebuilt</h3>
<ul>
<li><code>ee-promote-prod.yml</code> runs by hand and waits for a reviewer on the <code>production</code> environment.</li>
<li>It copies the chosen dev tags into the prod repository under the <strong>same tags</strong>.</li>
<li>With <code>push_image</code> off it is a dry run: it verifies the images and writes the promotion plan without pushing.</li>
</ul>
</div>

## Tagging Convention

| Tag type | Core 2.18 | Core 2.16 compat |
|---|---|---|
| Immutable version | `vYYYYMMDD-NNN` | `core216-vYYYYMMDD-NNN` |
| Immutable SHA | `sha-xxxxxxx` | `core216-sha-xxxxxxx` |
| Mutable | `latest`, `stable`, `tech-preview` | `core216-` + the same |

Production job templates in AAP point at an **immutable** tag or at `stable`, never
at `latest`.
