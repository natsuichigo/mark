# Architecture
The repo layout, the two kinds of page, and which files are generated rather than written by hand.

## The Repository

<pre class="dir-tree">
mark/
├── <span class="hl">_deploy/</span>                       <span class="cm"># EVERYTHING PUBLISHED. This folder is the site.</span>
├── <span class="hl">.claude/skills/</span>                <span class="cm"># The authoring tools, committed with the site</span>
│   ├── md-to-docs/                <span class="cm"># Markdown / PDF → case-study pages</span>
│   └── docs-to-deck/              <span class="cm"># Case-study pages → a reveal.js walkthrough deck</span>
├── <span class="hl">.github/</span>
│   ├── workflows/deploy-pages.yml <span class="cm"># The only workflow: upload _deploy/ to Pages</span>
│   └── CODEOWNERS
└── README.md
</pre>

## Inside `_deploy/`

<pre class="dir-tree">
_deploy/
├── <span class="hl">.nojekyll</span>                      <span class="cm"># Required and empty. Without it Pages ignores _-prefixed folders</span>
├── index.html                     <span class="cm"># Home</span>
├── projects/index.html            <span class="cm"># Card grid: one card per case study</span>
├── walkthroughs/index.html        <span class="cm"># Card grid: one card per deck</span>
├── about/index.html               <span class="cm"># Skills, certifications, contact</span>
├── <span class="hl">assets/</span>
│   ├── theme.css                  <span class="cm"># THE BRAND: every colour on the site comes from here</span>
│   ├── hub.css                    <span class="cm"># Layout for the hand-written hub pages</span>
│   ├── site-chrome.css / .js      <span class="cm"># The shared Home · Projects · Walkthroughs · About nav</span>
│   └── &lt;project&gt;-docs.css         <span class="cm"># Content styles for one case study</span>
├── <span class="hl">docs/</span>
│   ├── theme.local.css            <span class="cm"># Maps theme.css onto MkDocs-Material variables</span>
│   ├── assets/stylesheets/        <span class="cm"># MkDocs-Material core CSS (third-party, MIT)</span>
│   └── &lt;project&gt;/                 <span class="cm"># One folder per case study</span>
│       ├── index.html             <span class="cm"># The case study's landing page (hand-written)</span>
│       ├── *.html                 <span class="cm"># Generated content pages</span>
│       └── _src/                  <span class="cm"># Markdown sources + docs.config.json</span>
└── <span class="hl">presentations/</span>
    ├── layout-fix.css             <span class="cm"># The shared deck layer</span>
    └── &lt;slug&gt;/index.html          <span class="cm"># One reveal.js deck per walkthrough</span>
</pre>

## Two Kinds of Page

<div class="stage-box s1">
<h3>Hub pages: written by hand</h3>
<ul>
<li>Home, Projects, Walkthroughs, About, and each case study's <code>index.html</code>.</li>
<li>Styled by the shared <code>hub.css</code>; the nav bar is injected by <code>site-chrome.js</code> from a few <code>&lt;meta&gt;</code> tags.</li>
<li>Content is a <strong>card grid</strong>: one card per destination.</li>
</ul>
</div>

<div class="stage-box s2">
<h3>Content pages: generated from Markdown</h3>
<ul>
<li>Every <code>docs/&lt;project&gt;/*.html</code> except <code>index.html</code>.</li>
<li>MkDocs-Material layout: header, left sidebar, table of contents, previous/next links, footer.</li>
<li>Written in Markdown and converted by <code>md_to_page.py</code>. Never edited by hand, because the next build overwrites them.</li>
</ul>
</div>

## Generated vs Written by Hand

<div class="check-group"><div class="check-group-title">Written by hand</div><div class="check-list"><span class="check">_deploy/index.html</span><span class="check">projects/, walkthroughs/, about/</span><span class="check">docs/&lt;project&gt;/index.html</span><span class="check">assets/*.css, site-chrome.js</span></div></div>

<div class="check-group"><div class="check-group-title">Generated: edit the source, not the output</div><div class="check-list"><span class="check">docs/&lt;project&gt;/*.html (from _src/*.md)</span><span class="check">presentations/&lt;slug&gt;/index.html (from a deck plan)</span></div></div>

<div class="check-group"><div class="check-group-title">Do not touch</div><div class="check-list"><span class="check">_deploy/.nojekyll</span><span class="check">docs/assets/stylesheets/main.*.min.css</span></div></div>

## One Brand File

Every page, case study and deck reads its colours from `assets/theme.css`, as CSS
custom properties such as `--brand-primary` and `--brand-gradient`. Changing the
palette there restyles the whole site; no other file hard-codes a brand colour.

<div class="callout warn">
<p><strong><code>_src/</code> is published too.</strong> It sits inside <code>_deploy/</code>, so the Markdown sources are readable on the live site. That is fine for prose written to be published, but nothing private belongs there.</p>
</div>
