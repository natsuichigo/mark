#!/usr/bin/env python3
"""
Validate a generated case-study set under _deploy/docs/<project>/.

Nothing in CI checks these pages — the deploy workflow uploads _deploy/ verbatim —
so this is the review step. Every check here corresponds to a defect that has
actually shipped to the live site: unrendered Markdown tables, literal backtick
code spans, placeholder tags silently eaten by the browser, and sidebars that
disagreed with each other after a page was added without regenerating the rest.

Usage:
    python3 validate_pages.py --project portfolio-site
    python3 validate_pages.py --all
    python3 validate_pages.py --project portfolio-site --repo-root /path/to/repo

Exit codes:
    0 = no failures (warnings are allowed)
    1 = one or more failures

Two severities, decided by whether the set is managed by this skill:

  STRICT  — _src/docs.config.json exists. The set is ours, so structural checks
            (sidebar agreement, one active link, an unbroken prev/next chain in
            nav[] order) are FAILURES.
  ADVISORY— no config. The set predates this skill or was built by something
            else, so the same structural checks become WARNINGS — real, but not
            a defect this toolchain introduced.

Checks that are defects no matter who built the page — broken links, unresolvable
assets, unrendered Markdown, eaten placeholder tags, unbalanced tags — are
FAILURES in both modes.
"""
import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

# Tags that never need closing. The SVG subset matters because the hub pages and
# several content components embed inline icons.
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
    "path", "stop", "text", "use", "rect", "circle", "line", "polyline",
    "polygon", "ellipse",
}

# Anything outside this set, appearing as <word> in prose, is almost certainly a
# placeholder the author forgot to escape — the browser drops it and the text
# vanishes from the page with no error.
KNOWN_TAGS = {
    # Structure and text
    "html", "head", "body", "title", "main", "header", "footer", "nav", "section",
    "article", "aside", "div", "span", "p", "br", "hr", "h1", "h2", "h3", "h4",
    "h5", "h6", "blockquote", "figure", "figcaption", "address", "hgroup",
    # Inline
    "a", "b", "i", "em", "strong", "code", "pre", "kbd", "samp", "var", "mark",
    "small", "sub", "sup", "abbr", "cite", "q", "del", "ins", "time", "data",
    # Lists and tables
    "ul", "ol", "li", "dl", "dt", "dd", "table", "thead", "tbody", "tfoot", "tr",
    "td", "th", "caption", "colgroup", "col",
    # Media and embeds
    "img", "picture", "source", "svg", "video", "audio", "canvas", "iframe",
    # Forms and interactive
    "form", "fieldset", "legend", "label", "input", "button", "select", "option",
    "optgroup", "textarea", "details", "summary", "output", "progress", "meter",
    # Head and scripting
    "link", "meta", "style", "script", "noscript", "template", "slot", "base",
    # SVG children (lowercased by the parser)
    "defs", "g", "path", "rect", "circle", "ellipse", "line", "polyline",
    "polygon", "text", "tspan", "use", "marker", "mask", "pattern", "clippath",
    "lineargradient", "radialgradient", "stop", "filter", "symbol", "desc",
    "foreignobject", "textpath", "animate",
}


class Report:
    """Collects pass/warn/fail lines and prints them grouped by section."""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self.passed = 0
        self.warnings = []
        self.failures = []

    def section(self, name: str):
        if not self.quiet:
            print(f"\n  {name}")

    def ok(self, msg: str):
        self.passed += 1
        if not self.quiet:
            print(f"    PASS  {msg}")

    def warn(self, msg: str):
        self.warnings.append(msg)
        print(f"    WARN  {msg}")

    def fail(self, msg: str):
        self.failures.append(msg)
        print(f"    FAIL  {msg}")

    def check(self, condition: bool, msg: str, detail: str = "", hard: bool = True):
        if condition:
            self.ok(msg)
        elif hard:
            self.fail(f"{msg}{' — ' + detail if detail else ''}")
        else:
            self.warn(f"{msg}{' — ' + detail if detail else ''}")


class TagBalance(HTMLParser):
    """Minimal well-formedness check: unclosed and mis-nested elements."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            i = len(self.stack) - 1 - self.stack[::-1].index(tag)
            self.errors.append(f"</{tag}> closes over unclosed {self.stack[i + 1:]}")
            del self.stack[i:]
        else:
            self.errors.append(f"stray </{tag}>")


def article_of(page_html: str) -> str:
    """The authored region of a content page, or '' for a hub page."""
    m = re.search(r"<article.*?</article>", page_html, re.S)
    return m.group(0) if m else ""


def strip_verbatim(fragment: str) -> str:
    """Drop <pre> and <code> so their intentional literals don't trip checks."""
    fragment = re.sub(r"<pre>.*?</pre>", "", fragment, flags=re.S)
    return re.sub(r"<code>.*?</code>", "", fragment, flags=re.S)


def sidebar_of(page_html: str) -> str:
    m = re.search(r"md-sidebar--primary.*?</nav>", page_html, re.S)
    return m.group(0) if m else ""


def nav_links_of(sidebar: str):
    """Slugs in the sidebar's nav list, excluding the logo link above it."""
    return re.findall(r'<li class="md-nav__item"><a href="\./([^"]+)"', sidebar)


def load_config(project_dir: Path):
    for candidate in (project_dir / "_src" / "docs.config.json",
                      project_dir / "docs.config.json"):
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8")), candidate
    return None, None


def validate_project(project_dir: Path, deploy_root: Path, rep: Report) -> None:
    project = project_dir.name
    pages = {p.name: p.read_text(encoding="utf-8") for p in sorted(project_dir.glob("*.html"))}
    content = {n: s for n, s in pages.items() if sidebar_of(s)}
    hubs = sorted(set(pages) - set(content))

    config, config_path = load_config(project_dir)
    strict = config is not None
    mode = ("STRICT — checked against _src/docs.config.json" if strict else
            "ADVISORY — no config, so structural findings are warnings")
    print(f"\n=== {project}: {len(content)} content page(s), {len(hubs)} hub page(s)\n    {mode} ===")

    if not content:
        rep.fail(f"{project}: no content pages found (only hub pages?)")
        return

    # ── Inventory ────────────────────────────────────────────────────────────
    rep.section("Inventory")
    if config:
        nav = [e["slug"] for e in config["nav"]]
        missing = [s for s in nav if s not in pages]
        extra = sorted(set(content) - set(nav))
        rep.check(not missing, f"every nav slug exists on disk ({len(nav)} entries)", str(missing))
        rep.check(not extra, "no content page is missing from nav[]", str(extra))
    else:
        # Derive the expected nav from the first page and require the rest to match.
        nav = nav_links_of(sidebar_of(next(iter(content.values()))))
        rep.check(set(nav) == set(content),
                  f"sidebar slugs match the pages on disk ({len(nav)})",
                  f"sidebar-only={sorted(set(nav) - set(content))}, "
                  f"disk-only={sorted(set(content) - set(nav))}", hard=strict)

    # ── Page skeleton ────────────────────────────────────────────────────────
    rep.section("Page skeleton")
    for name, src in sorted(content.items()):
        problems = []
        if src.count("<article") != 1:
            problems.append(f'{src.count("<article")} <article>')
        if "<h1 class=\"page-title\">" not in src:
            problems.append("no page-title")
        if "pd-toc" not in src:
            problems.append("no TOC container")
        rep.check(not problems, f"{name}: skeleton intact", ", ".join(problems), hard=strict)
        # Hand-built pages sometimes have no footer — report, don't fail.
        if src.count("</footer>") != 1:
            rep.warn(f"{name}: {src.count('</footer>')} </footer> "
                     f"(generated pages have exactly one — hand-built pages may differ)")

    # ── Sidebar consistency ──────────────────────────────────────────────────
    rep.section("Sidebar")
    seen = {}
    for name, src in sorted(content.items()):
        seen.setdefault(frozenset(nav_links_of(sidebar_of(src))), []).append(name)
    rep.check(len(seen) == 1, f"all {len(content)} pages carry one identical sidebar",
              f"{len(seen)} variants: " + "; ".join(f"{len(k)} links -> {v[:4]}" for k, v in seen.items()),
              hard=strict)
    if len(seen) == 1:
        rep.check(set(next(iter(seen))) == set(nav), "sidebar matches the expected page set",
                  f"diff={set(next(iter(seen))) ^ set(nav)}", hard=strict)
    for name, src in sorted(content.items()):
        n_active = len(re.findall(r"md-nav__link--active", sidebar_of(src)))
        rep.check(n_active == 1, f"{name}: exactly one active sidebar link", f"found {n_active}",
                  hard=strict)

    # ── Prev/next chain ──────────────────────────────────────────────────────
    rep.section("Prev/next chain")
    heads = [n for n, s in content.items() if 'rel="prev"' not in s]
    tails = [n for n, s in content.items() if 'rel="next"' not in s]
    rep.check(len(heads) == 1, "exactly one page has no prev (the first)",
              f"{len(heads)} heads: {sorted(heads)[:6]}", hard=strict)
    rep.check(len(tails) == 1, "exactly one page has no next (the last)",
              f"{len(tails)} tails: {sorted(tails)[:6]}", hard=strict)
    if len(heads) == 1:
        walked, cur = [], heads[0]
        while cur and cur in content and cur not in walked:
            walked.append(cur)
            m = re.search(r'<link rel="next" href="([^"]+)"', content[cur])
            cur = m.group(1) if m else None
        rep.check(len(walked) == len(content),
                  f"next chain visits all {len(content)} pages",
                  f"visited {len(walked)} of {len(content)}", hard=strict)
        if config:
            rep.check(walked == nav, "next chain follows nav[] order", f"got {walked}", hard=strict)

    # ── Links and assets resolve ─────────────────────────────────────────────
    rep.section("Links and assets")
    for name, src in sorted(pages.items()):
        scope = article_of(src) or src
        bad = sorted(set(re.findall(r'href="\./([^"#]+\.html)', scope)) - set(pages))
        rep.check(not bad, f"{name}: same-set links resolve", str(bad))

        refs = re.findall(r'(?:href|src)="((?:\.\./|\./)[^"#]+\.(?:css|js|svg|png|jpg))"', src)
        # unquote: refs are URL-encoded, and at least one real filename contains a space.
        broken = [r for r in refs if not (project_dir / unquote(r)).resolve().exists()]
        rep.check(not broken, f"{name}: relative assets resolve ({len(refs)} refs)", str(broken))

    # ── Rendering hygiene ────────────────────────────────────────────────────
    rep.section("Rendering hygiene")
    for name, src in sorted(pages.items()):
        art = article_of(src)
        if not art:
            continue
        clean = strip_verbatim(art)

        leftover = re.findall(r"`[^`\n]+`", clean)
        rep.check(not leftover, f"{name}: no unrendered code spans", str(leftover[:3]))

        tables = re.findall(r"^\|.*\|$", clean, re.M)
        rep.check(not tables, f"{name}: no unrendered Markdown tables", str(tables[:2]))

        eaten = sorted({t for t in re.findall(r"<([a-z][a-z0-9_|.-]*)>", strip_verbatim(
            re.sub(r"<pre.*?</pre>", "", art, flags=re.S))) if t not in KNOWN_TAGS})
        rep.check(not eaten, f"{name}: no unescaped placeholder tags", str(eaten))

        sub = re.search(r'page-sub">([^<]*)', src)
        if sub:
            rep.check("`" not in sub.group(1), f"{name}: subtitle has no literal backticks",
                      sub.group(1)[:60])

    # ── Well-formedness ──────────────────────────────────────────────────────
    rep.section("Well-formedness")
    for name, src in sorted(pages.items()):
        parser = TagBalance()
        parser.feed(src)
        detail = "; ".join(parser.errors[:2]) or f"unclosed at EOF: {parser.stack[:5]}"
        rep.check(not parser.errors and not parser.stack, f"{name}: tags balanced", detail)

    # ── Favicon and link previews ────────────────────────────────────────────
    rep.section("Favicon and link previews")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import site_meta
    stale = [n for n, s in sorted(pages.items())
             if site_meta.apply(f"docs/{project}/{n}", s) != s]
    rep.check(not stale, f"all {len(pages)} pages have current favicon / link-preview tags",
              f"{stale} — run site_meta.py (build_project.py does this)")

    # ── Hub page links ───────────────────────────────────────────────────────
    # Hub pages are hand-edited, so check every live (uncommented) relative link
    # on them, including ones leaving the set (decks, Projects, Home).
    rep.section("Hub page links")
    for name in hubs:
        live = re.sub(r"<!--.*?-->", "", pages[name], flags=re.S)
        hrefs = sorted(set(re.findall(r'href="((?:\.\./|\./)[^"#?]+)"', live)))
        broken = [h for h in hrefs if not (project_dir / unquote(h)).resolve().exists()]
        rep.check(not broken, f"{name}: {len(hrefs)} relative links resolve", str(broken))

    # ── Project colour ───────────────────────────────────────────────────────
    # The button colour comes from the config's "brand" key via the generated
    # assets/project-colors.css, and reaches the hub page through
    # <body data-project="<project>">. Any break in that chain silently falls
    # back to the default blue, so check each link of it.
    rep.section("Project colour")
    brand = (config or {}).get("brand")
    if not brand:
        rep.warn(f"{project}: no \"brand\" in docs.config.json — buttons use the default blue")
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import project_colors
        try:
            project_colors.resolve_brand(brand)
            known = True
        except ValueError as e:
            known = False
            rep.fail(f"{project}: {e}")
        if known:
            css_path = deploy_root / project_colors.OUT_REL
            css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
            rep.check(project_colors.project_block(project, brand) in css,
                      f"project-colors.css has the current colour for '{brand}'",
                      "missing or stale — run project_colors.py (build_project.py does this)")
            hub_css = deploy_root / "assets" / "hub.css"
            rep.check(hub_css.is_file() and "project-colors.css" in hub_css.read_text(encoding="utf-8"),
                      "hub.css imports project-colors.css", "add @import url(\"project-colors.css\")")
        if "index.html" in pages:
            rep.check(f'data-project="{project}"' in pages["index.html"],
                      f'index.html <body> has data-project="{project}"',
                      "the hub page's buttons will stay the default blue")

    # ── Source coverage ──────────────────────────────────────────────────────
    # Not a failure: most legacy sets predate the _src/ convention. But an
    # uncovered page is one that can only be edited by hand-patching HTML, so
    # the gap should be visible rather than discovered.
    rep.section("Markdown source coverage")
    src_dir = project_dir / "_src"
    if not src_dir.is_dir():
        rep.warn(f"{project}: no _src/ folder — every page here can only be hand-edited. "
                 f"See docs/portfolio-site/_src/ for the convention")
    else:
        uncovered = [s for s in sorted(content) if not (src_dir / (Path(s).stem + ".md")).is_file()]
        rep.check(not uncovered, f"all {len(content)} pages have a Markdown source in _src/",
                  str(uncovered), hard=False)
        rep.check((src_dir / "docs.config.json").is_file(),
                  "_src/docs.config.json is committed", "", hard=False)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", default=".", help="Path to the mark repo checkout (default: .)")
    ap.add_argument("--deploy-dir", default="_deploy", help="Deploy folder to target (default: _deploy)")
    ap.add_argument("--project", help="Doc set under <deploy>/docs/ to validate, e.g. portfolio-site")
    ap.add_argument("--all", action="store_true", help="Validate every doc set that has content pages")
    ap.add_argument("--quiet", action="store_true", help="Print only WARN and FAIL lines, plus the summary")
    args = ap.parse_args()

    deploy_root = Path(args.repo_root) / args.deploy_dir
    docs_root = deploy_root / "docs"
    if not docs_root.is_dir():
        sys.exit(f"error: {docs_root} not found — is --repo-root correct?")

    if args.all:
        targets = [d for d in sorted(docs_root.iterdir())
                   if d.is_dir() and any(sidebar_of(p.read_text(encoding='utf-8'))
                                         for p in d.glob("*.html"))]
    elif args.project:
        targets = [docs_root / args.project]
        if not targets[0].is_dir():
            sys.exit(f"error: project '{args.project}' not found at {targets[0]}")
    else:
        sys.exit("error: pass --project <name> or --all")

    rep = Report(quiet=args.quiet)
    for project_dir in targets:
        validate_project(project_dir, deploy_root, rep)

    print("\n" + "=" * 68)
    print(f"  passed: {rep.passed}   warnings: {len(rep.warnings)}   failures: {len(rep.failures)}")
    if rep.failures:
        print("\n  FAILURES:")
        for f in rep.failures:
            print(f"    - {f}")
        print("\n  VALIDATION FAILED")
        return 1
    if rep.warnings:
        print("\n  Warnings do not fail validation, but are worth reading.")
    print("\n  VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
