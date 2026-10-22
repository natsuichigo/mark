#!/usr/bin/env python3
"""
Regenerate every page in a documentation set from its committed Markdown sources.

WHY THIS EXISTS. The sidebar and the prev/next links are baked into each page as
static HTML, not loaded from a shared include. So adding, removing, renaming or
reordering a page requires regenerating EVERY page in the set — convert only the
new one and the others keep a sidebar that no longer mentions it, with nothing to
warn you. That rule used to be a hand-written shell loop, which is exactly the
kind of thing people forget.

Reads _deploy/docs/<project>/_src/docs.config.json, and for each nav[] entry
converts _src/<slug>.md -> <slug>.html via md_to_page.py.

Usage:
    python3 build_project.py --project portfolio-site
    python3 build_project.py --project portfolio-site --check
    python3 build_project.py --project portfolio-site --repo-root /path/to/repo

Exit codes:
    0 = every nav entry was built (or, with --check, every source is present)
    1 = a nav entry has no Markdown source, or a conversion failed
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", default=".", help="Path to the mark repo checkout (default: .)")
    ap.add_argument("--deploy-dir", default="_deploy", help="Deploy folder to target (default: _deploy)")
    ap.add_argument("--project", required=True, help="Doc set under <deploy>/docs/, e.g. portfolio-site")
    ap.add_argument("--src-dir", default="_src",
                    help="Markdown source folder, relative to the project dir (default: _src)")
    ap.add_argument("--check", action="store_true",
                    help="Report source coverage and exit without writing anything")
    args = ap.parse_args()

    project_dir = Path(args.repo_root) / args.deploy_dir / "docs" / args.project
    if not project_dir.is_dir():
        sys.exit(f"error: project not found at {project_dir} — is --repo-root correct?")

    src_dir = project_dir / args.src_dir
    config_path = src_dir / "docs.config.json"
    if not config_path.is_file():
        sys.exit(
            f"error: no config at {config_path}\n"
            f"       This set has no committed sources, so there is nothing to build from.\n"
            f"       Bootstrap a config from a deployed page with:\n"
            f"         python3 {SCRIPT_DIR.name}/extract_config.py "
            f"--page {project_dir}/<a-page>.html --out {config_path}\n"
            f"       then add the Markdown sources alongside it.")

    nav = json.loads(config_path.read_text(encoding="utf-8"))["nav"]

    # Pair every nav entry with its expected source before touching anything, so a
    # missing file is reported up front rather than halfway through a rebuild.
    planned, missing = [], []
    for entry in nav:
        slug = entry["slug"]
        md = src_dir / (Path(slug).stem + ".md")
        (planned if md.is_file() else missing).append((slug, md))

    orphans = sorted(
        p.name for p in src_dir.glob("*.md")
        if (p.stem + ".html") not in {e["slug"] for e in nav})

    print(f"=== {args.project}: {len(nav)} nav entr{'y' if len(nav) == 1 else 'ies'}, "
          f"{len(planned)} with sources ===")

    if missing:
        print("\n  NO MARKDOWN SOURCE:")
        for slug, md in missing:
            print(f"    {slug:38} expected {md.relative_to(project_dir)}")
        print("\n  Those pages can only be edited by hand-patching their HTML.")

    if orphans:
        print("\n  ORPHAN SOURCES (not in nav[], so never built):")
        for name in orphans:
            print(f"    {name}")
        print("\n  Either add a nav[] entry for these or delete them.")

    if args.check:
        print(f"\n  coverage: {len(planned)}/{len(nav)}")
        if missing:
            print("  CHECK FAILED")
            return 1
        print("  CHECK PASSED")
        return 0

    if missing:
        print("\n  Refusing to build a partial set — a half-regenerated set is exactly")
        print("  the inconsistent-sidebar state this script exists to prevent.")
        print("  Add the missing sources, or remove those nav[] entries.")
        return 1

    print()
    failed = []
    for slug, md in planned:
        out = project_dir / slug
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "md_to_page.py"),
             "--config", str(config_path), "--md", str(md), "--out", str(out)],
            capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  wrote  {slug}")
        else:
            failed.append(slug)
            print(f"  FAILED {slug}")
            for line in (result.stderr or result.stdout).strip().splitlines():
                print(f"         {line}")

    print(f"\n  {len(planned) - len(failed)}/{len(planned)} pages written")
    if failed:
        print("  BUILD FAILED")
        return 1

    # Button colours come from the config's "brand" key; keep the generated
    # CSS in step with it so a brand change needs no separate command.
    print("\n  Project button colours:")
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "project_colors.py"),
         "--repo-root", args.repo_root, "--deploy-dir", args.deploy_dir],
        capture_output=True, text=True)
    print((result.stdout or result.stderr).rstrip())
    if result.returncode != 0:
        print("  BUILD FAILED (project colours)")
        return 1
    print("\n  Next: validate the result with")
    print(f"    python3 {SCRIPT_DIR.name}/validate_pages.py --project {args.project}")
    print("  And remember the hub page is hand-authored — if you added or removed a")
    print(f"  page, update the card grid in docs/{args.project}/index.html too.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
