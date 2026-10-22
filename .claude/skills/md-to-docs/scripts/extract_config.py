#!/usr/bin/env python3
"""
extract_config.py — Bootstrap a docs.config.json by reverse-engineering it
from an already-deployed content page in an EXISTING project (e.g.
docs/<project>/overview.html). Hand-built projects don't ship a
docs.config.json (it's a convenience file invented for this skill), so the
first time you touch an existing project you need one built from what's
already live.

Usage:
    python3 extract_config.py --page /path/to/_deploy/docs/portfolio-site/overview.html
    python3 extract_config.py --page ... --out my-project.docs.config.json

Prints the config to stdout, or writes it to --out if given. Review the
result before using it — nav order/section labels are read verbatim from the
sidebar HTML, so anything already inconsistent in the live pages carries over.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path


def extract(html_text: str) -> dict:
    def req(pattern, label, flags=0):
        m = re.search(pattern, html_text, flags)
        if not m:
            sys.exit(f"error: could not find {label} in the page (unexpected template shape)")
        return m.group(1)

    def opt(pattern, label, flags=0):
        m = re.search(pattern, html_text, flags)
        if not m:
            print(f"warning: could not find {label}; leaving it for you to fill in", file=sys.stderr)
            return None
        return m.group(1)

    title_full = req(r"<title>(.*?)</title>", "page title")
    title_full = html.unescape(title_full)
    site_name = title_full.split("—")[-1].strip() if "—" in title_full else title_full.strip()

    css_file = req(r'assets/([\w.\-]+-docs\.css)"', "project css_file link")
    typeset_prefix = req(r'md-content__inner md-typeset ([\w]+)-typeset', "typeset prefix class")
    docidx_label = html.unescape(req(r'hdr-page-nav__docidx"\s+href="\./index\.html">([^<]+)</a>', "docs-index label"))
    footer_raw = opt(r'<div class="md-copyright">([^<]+)</div>', "footer copyright text (page may predate the footer)")
    footer_name = html.unescape(footer_raw) if footer_raw else f"{site_name} — Mark"

    # depth = number of "../" segments in the Projects hub link (../../projects/index.html -> 2)
    hub_href = req(r'hdr-page-nav__hub"\s+href="([^"]+)"', "projects hub link")
    depth = hub_href.count("../")

    # The primary sidebar's <ul class="md-nav__list"> is always the first one
    # in the document (the secondary/TOC one is empty and comes later), so
    # grabbing the first non-greedy match is robust to whitespace differences.
    sidebar_m = re.search(r'<ul class="md-nav__list">(.*?)</ul>', html_text, re.S)
    if not sidebar_m:
        sys.exit("error: could not find the primary sidebar nav list in the page")
    sidebar_html = sidebar_m.group(1)

    nav = []
    section = None
    for m in re.finditer(
        r'<li class="md-nav__item md-nav__section-label">([^<]+)</li>'
        r'|<li class="md-nav__item"><a href="\./([^"]+)" class="md-nav__link[^"]*">([^<]+)</a></li>',
        sidebar_html,
    ):
        if m.group(1) is not None:
            section = html.unescape(m.group(1)).strip()
        else:
            nav.append({"slug": m.group(2), "title": html.unescape(m.group(3)), "section": section})

    return {
        "site_name": site_name,
        "docidx_label": docidx_label,
        "css_file": css_file,
        "footer_name": footer_name,
        "typeset_prefix": typeset_prefix,
        "depth": depth,
        "nav": nav,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", required=True, help="Path to an existing generated content page in the target project")
    ap.add_argument("--out", help="Where to write the resulting docs.config.json (default: print to stdout)")
    args = ap.parse_args()

    html_text = Path(args.page).read_text(encoding="utf-8")
    config = extract(html_text)
    text = json.dumps(config, indent=2) + "\n"

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out} — found {len(config['nav'])} nav entries. Review before use.")
    else:
        print(text)


if __name__ == "__main__":
    main()
