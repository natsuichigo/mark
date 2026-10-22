#!/usr/bin/env python3
"""
md_to_page.py — Convert a Markdown source file into a portfolio-themed
MkDocs-Material-style case-study page, matching the exact template
used under natsuichigo/mark/_deploy/docs/<project>/*.html
(see e.g. docs/portfolio-site/overview.html).

Usage:
    python3 md_to_page.py --config docs.config.json --md Overview.md --out ../_deploy/docs/portfolio-site/overview.html

See SKILL.md in the parent skill folder for the full workflow and the
docs.config.json schema. Run --help for all flags.
"""
import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import markdown as _markdown
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "markdown"], check=True)
    import markdown as _markdown

MD_EXTENSIONS = ["extra", "sane_lists", "tables", "fenced_code", "toc"]


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9\- ]", "", text.lower()).strip()
    s = re.sub(r"[\s]+", "-", s)
    return s or "section"


def split_title_and_body(md_text: str):
    """Strip a leading '# Title' and the following lone paragraph (subtitle)."""
    lines = md_text.lstrip("\n").split("\n")
    title = None
    sub = None
    idx = 0
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        idx = 1
        # skip blank lines
        while idx < len(lines) and lines[idx].strip() == "":
            idx += 1
        # a single non-heading paragraph directly after the title is the subtitle
        if idx < len(lines) and lines[idx].strip() and not lines[idx].startswith("#"):
            para_lines = []
            while idx < len(lines) and lines[idx].strip() != "":
                para_lines.append(lines[idx])
                idx += 1
            sub = " ".join(para_lines).strip()
    body = "\n".join(lines[idx:])
    return title, sub, body


def render_subtitle(text: str) -> str:
    """
    The subtitle is a single plain line, so it is NOT run through the Markdown
    renderer — that would let raw HTML through into the page header. It is
    escaped, then inline code spans are converted, because those are the one
    piece of Markdown a subtitle realistically needs (variable and file names).

    Before this existed, backticks in a subtitle rendered as literal backticks.
    That shipped to the live site twice. Any other Markdown in a subtitle still
    renders literally, by design.
    """
    escaped = html.escape(text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def render_markdown(body: str) -> str:
    md = _markdown.Markdown(extensions=MD_EXTENSIONS, extension_configs={"toc": {"toc_depth": 0}})
    return md.convert(body)


def build_sidebar(nav, active_slug: str) -> str:
    parts = []
    last_section = object()
    for entry in nav:
        section = entry.get("section")
        if section != last_section and section:
            parts.append(f'<li class="md-nav__item md-nav__section-label">{html.escape(section)}</li>')
            last_section = section
        active = " md-nav__link--active" if entry["slug"] == active_slug else ""
        parts.append(
            f'<li class="md-nav__item"><a href="./{entry["slug"]}" '
            f'class="md-nav__link{active}">{html.escape(entry["title"])}</a></li>'
        )
    return "\n              ".join(parts)


def find_prev_next(nav, active_slug: str):
    idx = next((i for i, e in enumerate(nav) if e["slug"] == active_slug), None)
    if idx is None:
        return None, None
    prev_e = nav[idx - 1] if idx > 0 else None
    next_e = nav[idx + 1] if idx < len(nav) - 1 else None
    return prev_e, next_e


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="no-js">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{page_title} — {site_name}</title>
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Roboto:300,400,400i,700,700i%7CRoboto+Mono:400,400i,700,700i&display=fallback">
    <style>:root{{--md-text-font:"Roboto";--md-code-font:"Roboto Mono"}}</style>
{prev_link}{next_link}    <link rel="stylesheet" href="{docs_root_up}assets/stylesheets/main.484c7ddc.min.css">
    <link rel="stylesheet" href="{docs_root_up}theme.local.css">
    <link rel="stylesheet" href="{deploy_root_up}assets/{css_file}">
</head>
<body dir="ltr">

<input class="md-toggle" data-md-toggle="drawer" type="checkbox" id="__drawer" autocomplete="off">
<label class="md-overlay" for="__drawer"></label>

<header class="md-header md-header--shadow" data-md-component="header">
  <nav class="md-header__inner md-grid" aria-label="Header">
    <a href="./index.html" title="{site_name}" class="md-header__button md-logo" aria-label="{site_name}"></a>
    <label class="md-header__button md-icon" for="__drawer" aria-label="Open navigation">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z"/></svg>
    </label>
    <div class="md-header__title" data-md-component="header-title">
      <div class="md-header__ellipsis">
        <div class="md-header__topic"><span class="md-ellipsis">{site_name}</span></div>
        <div class="md-header__topic" data-md-component="header-topic"><span class="md-ellipsis">{page_title}</span></div>
      </div>
    </div>
  </nav>
  <div class="hdr-page-nav" id="hdr-page-nav" aria-label="Page navigation"></div>
  <script>(function(){{function slugToTitle(h){{var n=h.split("/").pop().replace(/\\.html$/,"").replace(/-/g," ");return n.charAt(0).toUpperCase()+n.slice(1);}}function buildNav(){{var row=document.getElementById("hdr-page-nav");if(!row)return;var pE=document.querySelector("link[rel=prev]"),nE=document.querySelector("link[rel=next]"),pO=document.getElementById("pnav-prev"),nO=document.getElementById("pnav-next");var pH=pO?pO.dataset.href:(pE?pE.getAttribute("href"):null),pL=pO?pO.dataset.label:(pE?"&#9664; "+slugToTitle(pE.getAttribute("href")):null),nH=nO?nO.dataset.href:(nE?nE.getAttribute("href"):null),nL=nO?nO.dataset.label:(nE?slugToTitle(nE.getAttribute("href"))+" &#9654;":null);row.innerHTML=(pH?'<a class="hdr-page-nav__link hdr-page-nav__prev" href="'+pH+'">'+pL+'</a>':'<span class="hdr-page-nav__spacer"></span>')+'<div class="hdr-page-nav__centre"><a class="hdr-page-nav__link hdr-page-nav__hub" href="{hub_href}">Projects</a><a class="hdr-page-nav__link hdr-page-nav__docidx" href="./index.html">{docidx_label}</a><a class="hdr-page-nav__link hdr-page-nav__portal" href="{portal_href}">Home</a></div>'+(nH?'<a class="hdr-page-nav__link hdr-page-nav__next" href="'+nH+'">'+nL+'</a>':'<span class="hdr-page-nav__spacer"></span>');}}if(document.readyState==="loading"){{document.addEventListener("DOMContentLoaded",buildNav);}}else{{buildNav();}}}})()</script>
</header>

<div class="md-container">
  <main class="md-main">
    <div class="md-main__inner md-grid">

      <div class="md-sidebar md-sidebar--primary" data-md-component="sidebar" data-md-type="navigation">
        <div class="md-sidebar__scrollwrap"><div class="md-sidebar__inner">
          <nav class="md-nav md-nav--primary" aria-label="Navigation" data-md-level="0">
            <label class="md-nav__title" for="__drawer">
              <a href="./index.html" class="md-nav__button md-logo" aria-label="{site_name}"></a>
              {site_name}
            </label>
            <ul class="md-nav__list">
              {sidebar_html}
            </ul>
          </nav>
        </div></div>
      </div>

      <div class="md-sidebar md-sidebar--secondary" data-md-component="sidebar" data-md-type="toc">
        <div class="md-sidebar__scrollwrap"><div class="md-sidebar__inner">
          <nav class="md-nav md-nav--secondary" aria-label="Table of contents">
            <label class="md-nav__title">On this page</label>
            <ul class="md-nav__list" id="pd-toc"></ul>
          </nav>
        </div></div>
      </div>

      <div class="md-content" data-md-component="content">
        <article class="md-content__inner md-typeset {typeset_prefix}-typeset">

        <h1 class="page-title">{page_title}</h1>
{page_sub}
{body_html}

        </article>
      </div>

    </div>
  </main>

  <footer class="md-footer">
  <div class="md-footer-meta md-typeset">
    <div class="md-footer-meta__inner md-grid">
      <div class="md-copyright">{footer_name}</div>
    </div>
  </div>
</footer>

</div>

<script>
(function(){{
  function buildToc(){{
    var toc=document.getElementById("pd-toc");
    if(!toc)return;
    var headings=document.querySelectorAll(".md-typeset h2");
    if(!headings.length){{
      var sec=toc.closest(".md-sidebar--secondary");
      if(sec)sec.style.display="none";
      return;
    }}
    var html="";
    for(var i=0;i<headings.length;i++){{
      var h=headings[i];
      if(!h.id)h.id="section-"+i;
      html+='<li class="md-nav__item"><a class="md-nav__link" href="#'+h.id+'">'+h.textContent+'</a></li>';
    }}
    toc.innerHTML=html;
  }}
  function initScrollSpy(){{
    var links=document.querySelectorAll("#pd-toc .md-nav__link");
    if(!links.length)return;
    function onScroll(){{
      var hs=document.querySelectorAll(".md-typeset h2"),active=null;
      var st=window.pageYOffset||document.documentElement.scrollTop||0;
      for(var i=hs.length-1;i>=0;i--){{if(hs[i].getBoundingClientRect().top+st-140<=st){{active=hs[i].id;break;}}}}
      for(var j=0;j<links.length;j++){{links[j].className=active&&links[j].getAttribute("href")==="#"+active?"md-nav__link md-nav__link--active":"md-nav__link";}}
    }}
    window.addEventListener("scroll",onScroll,{{passive:true}});
  }}
  if(document.readyState==="loading"){{document.addEventListener("DOMContentLoaded",function(){{buildToc();initScrollSpy();}});}}
  else{{buildToc();initScrollSpy();}}
}})();
</script>

<button class="back-to-top" id="back-to-top" aria-label="Back to top" title="Back to top">&#8679;</button>
<script>(function(){{var b=document.getElementById("back-to-top");window.addEventListener("scroll",function(){{b.classList.toggle("visible",window.scrollY>400);}},{{passive:true}});b.addEventListener("click",function(){{window.scrollTo({{top:0,behavior:"smooth"}});}});}})();</script>
{pnav_data}
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, help="Path to docs.config.json for the target project")
    ap.add_argument("--md", required=True, help="Path to the source Markdown file")
    ap.add_argument("--out", required=True, help="Path to write the generated .html file")
    ap.add_argument("--slug", help="Override the output slug used to match the nav entry (default: <md filename>.html)")
    args = ap.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    nav = config["nav"]
    depth = int(config.get("depth", 2))  # docs/<project>/file.html -> depth 2

    md_path = Path(args.md)
    slug = args.slug or (md_path.stem + ".html")

    entry = next((e for e in nav if e["slug"] == slug), None)
    if entry is None:
        sys.exit(f"error: slug '{slug}' not found in nav of {args.config}. Add it to docs.config.json first.")

    md_text = md_path.read_text(encoding="utf-8")
    fm_title, fm_sub, body_md = split_title_and_body(md_text)
    page_title = entry.get("title") or fm_title or md_path.stem
    page_sub_text = entry.get("sub") or fm_sub
    page_sub_html = f'        <p class="page-sub">{render_subtitle(page_sub_text)}</p>' if page_sub_text else ""

    body_html = render_markdown(body_md)

    prev_e, next_e = find_prev_next(nav, slug)
    prev_link = f'    <link rel="prev" href="{prev_e["slug"]}">\n' if prev_e else ""
    next_link = f'    <link rel="next" href="{next_e["slug"]}">\n' if next_e else ""

    pnav_bits = []
    if prev_e:
        pnav_bits.append(
            f'    <data id="pnav-prev" data-href="./{prev_e["slug"]}" '
            f'data-label="&#9664; {html.escape(prev_e["title"])}" hidden></data>'
        )
    if next_e:
        pnav_bits.append(
            f'    <data id="pnav-next" data-href="./{next_e["slug"]}" '
            f'data-label="{html.escape(next_e["title"])} &#9654;" hidden></data>'
        )
    pnav_data = "\n".join(pnav_bits)

    # Two different roots sit above docs/<project>/*.html:
    #   docs/           -> main.484c7ddc.min.css + theme.local.css   (depth-1 "../")
    #   _deploy/assets/ -> the project-specific extra CSS            (depth   "../")
    docs_root_up = "../" * (depth - 1)
    deploy_root_up = "../" * depth
    hub_href = "../" * depth + "projects/index.html"
    portal_href = "../" * depth + "index.html"

    html_out = PAGE_TEMPLATE.format(
        page_title=html.escape(page_title),
        site_name=html.escape(config["site_name"]),
        prev_link=prev_link,
        next_link=next_link,
        docs_root_up=docs_root_up,
        deploy_root_up=deploy_root_up,
        css_file=config["css_file"],
        hub_href=hub_href,
        docidx_label=html.escape(config["docidx_label"]),
        portal_href=portal_href,
        sidebar_html=build_sidebar(nav, slug),
        page_sub=page_sub_html,
        body_html=body_html,
        footer_name=html.escape(config["footer_name"]),
        pnav_data=pnav_data,
        typeset_prefix=config.get("typeset_prefix", "pk"),
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_out, encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
