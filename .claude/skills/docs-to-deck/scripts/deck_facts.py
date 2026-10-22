#!/usr/bin/env python3
"""
deck_facts.py — gather the facts a walkthrough deck needs from a project's
published case-study pages, plus an agenda skeleton shaped by the deck type.

Numbers and claims in a slide go stale silently. Take the page list, the
section grouping and the repo link from here, and the details from the pages
themselves, rather than from memory or an earlier deck.

Usage:
    python3 deck_facts.py --repo-root . --project packer-image-pipeline --deck-type overview

    python3 deck_facts.py --repo-root . --list        # case studies and existing decks
    python3 deck_facts.py --repo-root . --project portfolio-site --deck-type deep-dive \\
        --json > portfolio-site.facts.json

--deck-type is REQUIRED for the agenda skeleton, and that is deliberate: see
SKILL.md STEP 0. A five-minute overview for a recruiter, a deep dive for a
technical interview and a story-led meetup talk are different decks, and the
difference is structural rather than cosmetic.
"""
import argparse
import json
import re
import sys
from pathlib import Path

DEPLOY = "_deploy"
PRESENTATIONS = "_deploy/presentations"

DECK_TYPES = ("overview", "deep-dive", "talk")

AGENDA_SKELETONS = {
    "overview": [
        "The problem, in one slide",
        "What I built",
        "How it works, at a glance",
        "Results: what it gives you",
        "Stack and links",
    ],
    "deep-dive": [
        "The problem and the constraints",
        "Architecture: the components and how they fit",
        "How it works, step by step",
        "Design decisions and the trade-offs behind them",
        "What went wrong, and what I changed",
        "Next steps",
        "Links: repo and case study",
    ],
    "talk": [
        "The itch: why I started",
        "The first version, and where it broke",
        "The idea that fixed it",
        "How it works now",
        "What I learned",
        "Try it yourself: links",
    ],
}

DECK_TYPE_NOTE = {
    "overview": "Audience: recruiters and hiring managers. Short and outcome-first; "
                "five or six content slides, little code.",
    "deep-dive": "Audience: engineers, e.g. a technical interview. Architecture, "
                 "decisions and trade-offs; code and config where they explain something.",
    "talk": "Audience: a meetup or team talk. Story-led: problem, false starts, "
            "the fix, the lessons.",
}

# Page titles worth citing on particular slides.
PAGE_HINTS = (
    ("overview", "the problem and the stack"),
    ("architecture", "components and layout"),
    ("how-it-works", "the step-by-step flow"),
    ("how it works", "the step-by-step flow"),
    ("deploy", "the step-by-step flow"),
    ("lesson", "decisions, lessons and next steps"),
)


def doc_sets(repo_root: Path) -> list:
    d = repo_root / DEPLOY / "docs"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir()
                  if p.is_dir() and any(p.glob("*.html")))


def existing_decks(repo_root: Path) -> list:
    d = repo_root / PRESENTATIONS
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if (p / "index.html").is_file())


def doc_pages(repo_root: Path, project: str) -> list:
    """
    [{slug, title, section}] for a case study. Prefers the committed
    _src/docs.config.json; falls back to reading titles out of the HTML.
    """
    pdir = repo_root / DEPLOY / "docs" / project
    cfg = pdir / "_src" / "docs.config.json"
    if cfg.is_file():
        try:
            nav = json.loads(cfg.read_text(encoding="utf-8")).get("nav", [])
            return [{"slug": n.get("slug", ""), "title": n.get("title", ""),
                     "section": n.get("section", "")} for n in nav]
        except json.JSONDecodeError:
            pass

    pages = []
    for f in sorted(pdir.glob("*.html")):
        if f.name == "index.html":
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'<h1 class="page-title">(.*?)</h1>', text, re.S)
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else f.stem
        pages.append({"slug": f.name, "title": title, "section": ""})
    return pages


def project_meta(repo_root: Path, project: str) -> dict:
    """The case study's display name, subtitle and repo link, from its index page."""
    idx = repo_root / DEPLOY / "docs" / project / "index.html"
    if not idx.is_file():
        return {}
    text = idx.read_text(encoding="utf-8", errors="replace")

    def grab(pattern):
        m = re.search(pattern, text, re.S)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else None

    repo = re.search(r'href="(https://github\.com/[^"]+)"', text)
    return {
        "name": grab(r"<h1>(.*?)</h1>"),
        "subtitle": grab(r'<p class="subtitle">(.*?)</p>'),
        "repo_url": repo.group(1) if repo else None,
    }


def cite_pages(pages: list) -> list:
    out = []
    for p in pages:
        hay = f"{p['slug']} {p['title']}".lower()
        for needle, why in PAGE_HINTS:
            if needle in hay:
                out.append({**p, "use_for": why})
                break
    return out


def build(repo_root: Path, project: str, deck_type: str) -> dict:
    pages = doc_pages(repo_root, project) if project else []
    return {
        "project": project,
        **project_meta(repo_root, project),
        "deck_type": deck_type,
        "deck_type_note": DECK_TYPE_NOTE[deck_type],
        "audience": None,   # fill in from the user's answer
        "docs_href": f"../../docs/{project}/index.html" if project else None,
        "doc_pages": pages,
        "doc_sections": list(dict.fromkeys(p["section"] for p in pages if p["section"])),
        "cite_pages": cite_pages(pages),
        "deck_exists": project in existing_decks(repo_root),
        "agenda_skeleton": AGENDA_SKELETONS[deck_type],
    }


def report(facts: dict):
    print(f"\n  deck type: {facts['deck_type'].upper()}")
    print(f"    {facts['deck_type_note']}")

    print(f"\n  project: {facts.get('name') or facts['project']}")
    if facts.get("subtitle"):
        print(f"    {facts['subtitle']}")
    print(f"    repo: {facts.get('repo_url') or 'none linked from the index page'}")
    if facts["deck_exists"]:
        print(f"    NOTE  a deck already exists at presentations/{facts['project']}/ — "
              f"update it rather than starting over")

    pages = facts["doc_pages"]
    print(f"\n  case-study pages in '{facts['project']}': {len(pages)}")
    for s in facts["doc_sections"] or [""]:
        group = [p for p in pages if p["section"] == s]
        if s:
            print(f"    [{s}]")
        for p in group:
            print(f"      - {p['title']}  ({p['slug']})")
    if not pages:
        print("    none — build the case study with md-to-docs first; "
              "the deck takes its facts from those pages.")

    if facts["cite_pages"]:
        print(f"\n  read these before writing the matching slides")
        for p in facts["cite_pages"]:
            print(f"    - {p['title']}  -> {p['use_for']}")

    print(f"\n  agenda skeleton for a '{facts['deck_type']}' deck")
    for i, s in enumerate(facts["agenda_skeleton"], 1):
        print(f"    {i:2d}. {s}")
    print()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", default=".",
                    help="Path to the mark repo checkout (default: .)")
    ap.add_argument("--project", help="Case study under _deploy/docs/, e.g. packer-image-pipeline")
    ap.add_argument("--deck-type", choices=DECK_TYPES,
                    help="overview | deep-dive | talk (see SKILL.md STEP 0)")
    ap.add_argument("--list", action="store_true",
                    help="List case studies and existing decks, then exit")
    ap.add_argument("--json", action="store_true",
                    help="Emit the facts as JSON instead of a report")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not (repo_root / DEPLOY).is_dir():
        sys.exit(f"error: {repo_root / DEPLOY} not found — is --repo-root correct?")

    if args.list:
        print(f"\n  case studies:   {', '.join(doc_sets(repo_root)) or 'none'}")
        print(f"  existing decks: {', '.join(existing_decks(repo_root)) or 'none'}\n")
        return 0

    if not args.deck_type:
        sys.exit("error: --deck-type is required.\n\n"
                 "  Establish who the deck is for before writing any slides — it\n"
                 "  decides the deck's length, depth and tone. Ask the user, then\n"
                 "  pass one of: overview | deep-dive | talk. See SKILL.md STEP 0.")
    if not args.project:
        sys.exit("error: --project is required (run --list to see case studies).")

    facts = build(repo_root, args.project, args.deck_type)
    if args.json:
        print(json.dumps(facts, indent=2, ensure_ascii=False))
    else:
        report(facts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
