#!/usr/bin/env python3
"""
scaffold_project.py — Create a brand-new case-study project folder under
natsuichigo/mark/_deploy/docs/<project>/, built the same way as the
existing projects: its own <project>-docs.css (cloned from an existing
project's CSS, just re-prefixed) and its own hub index.html (cloned from an
existing project's index.html), plus a starter _src/docs.config.json — the
committed config that md_to_page.py and build_project.py read.

Usage:
    # see what projects exist to clone conventions from
    python3 scaffold_project.py --repo-root /path/to/mark --list

    # create a new case study called "my-new-thing", based on portfolio-site's layout
    python3 scaffold_project.py --repo-root /path/to/mark \\
        --project my-new-thing --like portfolio-site \\
        --site-name "My New Thing" \\
        --docidx-label "My New Thing" \\
        --footer-name "My New Thing — Mark"

This only creates the project's own files. Adding a card for it to
_deploy/projects/index.html is still a manual hand-edit (see SKILL.md)
since that is a hero/card-grid landing page.
"""
import argparse
import json
import re
import sys
from pathlib import Path


CARD_TEMPLATE = """
            <!-- One card per page, in nav[] order. Copy this block, and put a
                 <div class="section-label"><span>Group</span></div> between groups.

            <a class="card" href="./overview.html" aria-label="Overview">
                <div class="icon-badge" aria-hidden="true">
                    <svg viewBox="0 0 24 24" focusable="false"><path d="M6 3h9l5 5v13H6zm8 1.5V9h4.5zM8 11h10v1.8H8zm0 4h10v1.8H8z"/></svg>
                </div>
                <h2>Overview</h2>
                <p>One line on what the page covers.</p>
                <span class="btn">→ View</span>
            </a>
            -->
"""


PROJECT_LINKS_TEMPLATE = """            <!-- Links for this project. Uncomment and fill in:
            <a class="btn" href="https://github.com/natsuichigo/REPO">View repo on GitHub</a>
            <a class="btn alt" href="../../presentations/SLUG/index.html">Walkthrough slides</a>
            -->"""


def retarget_hub(html: str, site_name: str, footer_name: str) -> str:
    """
    The cloned hub still describes the project it came from, and its cards link
    to pages this project does not have. Retitle it and empty the card grid, so
    a new project starts valid instead of with a hub full of broken links.
    """
    esc = site_name.replace("&", "&amp;")
    html = re.sub(r"<title>.*?</title>", f"<title>{esc}</title>", html, count=1, flags=re.S)
    html = re.sub(r"<h1>.*?</h1>", f"<h1>{esc}</h1>", html, count=1, flags=re.S)
    html = re.sub(r'(<p class="subtitle">).*?(</p>)', r"\1Replace with a one-line description of this project\2",
                  html, count=1, flags=re.S)
    html = re.sub(r'(<section class="links"[^>]*>).*?(\n\s*</section>)',
                  lambda m: m.group(1) + "\n" + CARD_TEMPLATE + m.group(2), html, count=1, flags=re.S)
    html = re.sub(r'(<p class="meta">).*?(</p>)', lambda m: m.group(1) + footer_name.replace("&", "&amp;") + m.group(2),
                  html, count=1, flags=re.S)
    # The repo / walkthrough buttons point at the cloned project's repo and deck.
    html = re.sub(r'(<div class="project-links">).*?(\n\s*</div>)',
                  lambda m: m.group(1) + "\n" + PROJECT_LINKS_TEMPLATE + m.group(2), html, count=1, flags=re.S)
    return html


def list_projects(deploy_root: Path):
    docs_dir = deploy_root / "docs"
    if not docs_dir.is_dir():
        return []
    return sorted(
        p.name for p in docs_dir.iterdir()
        if p.is_dir() and (p / "index.html").exists()
    )


def derive_prefix(project: str) -> str:
    parts = [p for p in re.split(r"[-_]", project.lower()) if p]
    if len(parts) == 1:
        return parts[0][:2] or "pg"
    return "".join(p[0] for p in parts)[:3] or "pg"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", required=True, help="Path to the mark repo checkout")
    ap.add_argument("--deploy-dir", default="_deploy", help="Deploy folder to target: _deploy or _test_deploy (default: _deploy)")
    ap.add_argument("--project", help="New project slug, kebab-case, e.g. my-new-thing")
    ap.add_argument("--like", help="Existing project folder to clone CSS/index.html conventions from, e.g. portfolio-site")
    ap.add_argument("--site-name", help="Header/title text, e.g. 'My New Thing'")
    ap.add_argument("--docidx-label", help="Label for this project's index link in the page-nav bar")
    ap.add_argument("--footer-name", help="Footer copyright text")
    ap.add_argument("--brand", help="Button colour: the project's main platform/tool, e.g. ansible, kubernetes, "
                                    "terraform, aws (see project_colors.py --list-tools), or a hex colour")
    ap.add_argument("--prefix", help="CSS typeset prefix, e.g. 'mnt' -> .mnt-typeset (default: derived from --project)")
    ap.add_argument("--config-out", help="Where to write the starter docs.config.json (default: _deploy/docs/<project>/_src/docs.config.json)")
    ap.add_argument("--list", action="store_true", help="List existing projects available to use with --like, then exit")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite an existing index.html / CSS. An EMPTY project folder is "
                         "always accepted without this, since pre-creating the folder is harmless.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root)
    deploy_root = repo_root / args.deploy_dir

    if args.list:
        for name in list_projects(deploy_root):
            print(name)
        return

    missing = [f"--{flag}" for flag, val in [
        ("project", args.project), ("like", args.like), ("site-name", args.site_name),
        ("docidx-label", args.docidx_label), ("footer-name", args.footer_name),
    ] if not val]
    if missing:
        sys.exit(f"error: missing required flags: {', '.join(missing)} (run --list to see existing projects to clone from)")

    like_dir = deploy_root / "docs" / args.like
    like_css = deploy_root / "assets" / f"{args.like}-docs.css"
    if not like_dir.is_dir():
        sys.exit(f"error: --like project '{args.like}' not found at {like_dir}")
    if not like_css.is_file():
        sys.exit(f"error: expected CSS for --like project at {like_css}")

    project = args.project
    prefix = args.prefix or derive_prefix(project)
    if args.brand:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from project_colors import resolve_brand
        try:
            resolve_brand(args.brand)
        except ValueError as e:
            sys.exit(f"error: --brand: {e}")

    new_dir = deploy_root / "docs" / project
    new_css = deploy_root / "assets" / f"{project}-docs.css"
    # An empty folder is accepted: pre-creating the directory is a normal thing to
    # do and clobbers nothing. Only real files require --force.
    existing = [p for p in new_dir.rglob("*") if p.is_file()] if new_dir.exists() else []
    if new_css.is_file():
        existing.append(new_css)
    if existing and not args.force:
        listed = "\n".join(f"    {p}" for p in existing[:8])
        sys.exit(f"error: '{project}' already has files:\n{listed}\n"
                 f"  Pass --force to overwrite index.html and the CSS, or pick a different name.\n"
                 f"  NOTE: --force does not touch generated content pages or _src/.")
    if existing:
        print(f"--force: overwriting {len(existing)} existing file(s) in {project}")

    # Clone the CSS, re-targeting whatever .<prefix>-typeset wrapper class it uses.
    css_text = like_css.read_text(encoding="utf-8")
    prefix_match = re.search(r"\.([a-z0-9]+)-typeset\b", css_text)
    like_prefix = prefix_match.group(1) if prefix_match else args.like[:2]
    css_text = re.sub(rf"\.{re.escape(like_prefix)}-typeset\b", f".{prefix}-typeset", css_text)
    new_dir.mkdir(parents=True, exist_ok=True)
    new_css.write_text(css_text, encoding="utf-8")

    # Clone the hub index.html verbatim; the site-chrome meta tags/paths are
    # identical for any project at the same depth, only labels need to change.
    index_html = (like_dir / "index.html").read_text(encoding="utf-8")
    index_html = index_html.replace(args.like, project)
    index_html = retarget_hub(index_html, args.site_name, args.footer_name)
    new_dir.joinpath("index.html").write_text(index_html, encoding="utf-8")

    config = {
        "site_name": args.site_name,
        "docidx_label": args.docidx_label,
        "css_file": f"{project}-docs.css",
        "footer_name": args.footer_name,
        "typeset_prefix": prefix,
        **({"brand": args.brand} if args.brand else {}),
        "depth": 2,
        "nav": [],
    }
    # Default to the committed location, next to the Markdown sources, so
    # build_project.py finds it without a flag.
    config_out = Path(args.config_out) if args.config_out else new_dir / "_src" / "docs.config.json"
    if config_out.exists() and not args.force:
        sys.exit(f"error: {config_out} already exists — pass --force to overwrite it")
    config_out.parent.mkdir(parents=True, exist_ok=True)
    config_out.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    print(f"created {new_dir}/index.html (cloned from {args.like}, retitled, empty card grid — add a card per page)")
    print(f"created {new_css} (prefix .{like_prefix}-typeset -> .{prefix}-typeset)")
    print(f"wrote {config_out} with an empty nav[] — put the Markdown beside it, add one nav[] entry per page,")
    print(f"  then: python3 build_project.py --project {project}")
    if args.brand:
        import subprocess
        subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "project_colors.py"),
                        "--repo-root", str(repo_root), "--deploy-dir", args.deploy_dir])
    else:
        print("No --brand given: this project's buttons use the default blue. Add \"brand\" to the config later.")
    print("Still manual: add a card for this project to _deploy/projects/index.html (and the home page if featured)")


if __name__ == "__main__":
    main()
