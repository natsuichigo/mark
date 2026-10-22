#!/usr/bin/env python3
"""
scaffold_deck.py — write the shell of a deck from a plan, with the agenda
wired correctly.

What it generates: the title slide, the agenda slide with every card pointing
at the right slide index, titled placeholder sections for the content, the
deck-nav bar with the right slide count, the local-return-bar, and the
reveal.js init + navigation script copied verbatim from an existing deck.

What it does NOT generate: the content. Writing the slides is the job; this
removes the part that breaks silently. Every agenda card carries
data-slide-target/-start/-end that must match its slide's real horizontal
index, and the nav label hard-codes the total — so inserting one slide by hand
puts every later card off by one, and nothing complains until someone clicks.

Usage:
    python3 scaffold_deck.py --repo-root . --plan packer-image-pipeline.deck.plan.json
    python3 scaffold_deck.py --repo-root . --plan p.json --like portfolio-site --force

The plan must carry a deck_type — see SKILL.md STEP 0. It is not cosmetic: it
decides the deck's length and depth, so the scaffolder refuses a plan that has
not answered it.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blocks import BlockError, render_slide_body, styles_for  # noqa: E402

PRESENTATIONS = "_deploy/presentations"
DECK_TYPES = ("overview", "deep-dive", "talk")
SITE_OWNER = "Mark — DevOps &amp; Platform Engineer"

# Written into the deck as an HTML comment, so the next edit knows which kind
# of deck this is without re-asking.
DECK_TYPE_BANNER = {
    "overview": "OVERVIEW deck — for recruiters and hiring managers: short, "
                "outcome-first, little code.",
    "deep-dive": "DEEP-DIVE deck — for engineers / technical interviews: "
                 "architecture, decisions, trade-offs.",
    "talk": "TALK deck — for a meetup or team talk: story-led, problem to lessons.",
}


def esc(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def load_plan(path: Path) -> dict:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"error: {path}: no such file")
    except json.JSONDecodeError as e:
        sys.exit(f"error: {path}: invalid JSON — {e}")

    problems = []
    for key in ("slug", "title", "deck_type", "phases"):
        if not plan.get(key):
            problems.append(f"missing required key '{key}'")
    kind = plan.get("deck_type")
    if kind and kind not in DECK_TYPES:
        problems.append(f"deck_type must be one of {', '.join(DECK_TYPES)} — "
                        f"got '{kind}'. Establish who the deck is for before "
                        f"building it (SKILL.md STEP 0)")
    if not any(ph.get("slides") for ph in plan.get("phases", []) or []):
        problems.append("no phases[].slides — there is nothing to scaffold")
    if problems:
        sys.exit(f"error: {path}:\n  - " + "\n  - ".join(problems))
    return plan


def reveal_scaffolding(like: Path) -> tuple:
    """
    (head_links, nav_bar, script) lifted verbatim from an existing deck. Copied
    rather than reimplemented so a scaffolded deck behaves exactly like the
    hand-written ones — the agenda navigation in particular is subtle.
    """
    html = like.read_text(encoding="utf-8")
    links = re.findall(r'(?m)^\s*<link rel="stylesheet"[^>]*>\s*$', html)
    nav = re.search(r'(?s)(\s*<div class="deck-nav".*?</div>\s*\n)', html)
    script = re.search(r'(?s)(\s*<script src="https://cdn\.jsdelivr\.net/npm/'
                       r'reveal\.js[^"]*"></script>\s*<script>.*?</script>)', html)
    if not nav or not script:
        sys.exit(f"error: could not find the deck-nav bar and reveal init in "
                 f"{like} — pass --like <a deck that has them>")
    return "\n".join(l.rstrip() for l in links), nav.group(1), script.group(1)


def build(plan: dict, like: Path) -> str:
    links, nav, script = reveal_scaffolding(like)

    # slide 0 = title, slide 1 = agenda, content starts at 2
    flat = []
    for phase in plan["phases"]:
        for slide in phase.get("slides", []):
            flat.append((phase.get("title"), slide))
    total = 2 + len(flat)

    # ── agenda ────────────────────────────────────────────────────────────
    agenda, seen_phase, order = [], None, 0
    for idx, (phase_title, slide) in enumerate(flat, start=2):
        if phase_title and phase_title != seen_phase:
            agenda.append(f'            <div class="agenda-phase">'
                          f'{esc(phase_title)}</div>')
            seen_phase = phase_title
        order += 1
        icon = slide.get("icon", "fa-circle-info")
        agenda.append(
            f'            <button type="button" class="agenda-card" '
            f'data-slide-target="{idx}" data-slide-start="{idx}" '
            f'data-slide-end="{idx}">\n'
            f'              <span class="agenda-card__order">{order:02d}</span>\n'
            f'              <span class="agenda-card__icon">'
            f'<i class="fas {esc(icon)}"></i></span>\n'
            f'              <span class="agenda-card__body">\n'
            f'                <span class="agenda-card__title">'
            f'{esc(slide["title"])}</span>\n'
            f'                <span class="agenda-card__meta">'
            f'Slide {idx + 1}</span>\n'
            f'              </span>\n'
            f'              <span class="agenda-card__arrow">'
            f'<i class="fas fa-arrow-right"></i></span>\n'
            f'            </button>')

    # ── content slides ────────────────────────────────────────────────────
    # A slide with "blocks" is rendered into real house-component markup by
    # blocks.py. One without still gets a placeholder, so a plan can be filled
    # in slide by slide. Rendering beats hand-writing because the component
    # rules that break a deck (SKILL.md 4a) are enforced in the renderer.
    content = []
    for phase_title, slide in flat:
        icon = slide.get("icon", "fa-circle-info")
        head = (f'        <section data-background-color="#f1f5f9">\n'
                f'          <h2><i class="fas {esc(icon)}"></i> '
                f'{esc(slide["title"])}</h2>')
        if slide.get("blocks"):
            try:
                body = "\n".join(render_slide_body(slide["blocks"]))
            except BlockError as exc:
                sys.exit(f"error: slide {slide['title']!r}: {exc}")
            content.append(f"{head}\n{body}\n        </section>")
        else:
            note = f"  Phase: {phase_title}\n" if phase_title else ""
            content.append(
                f'{head}\n'
                f'          <!-- TODO write this slide.\n'
                f'{note}'
                f'  Take the facts from deck_facts.py, not from an earlier deck.\n'
                f'  Preferred: add a "blocks" list to this slide in the plan and\n'
                f'  re-run the scaffolder — blocks.py renders the house components\n'
                f'  and refuses the combinations that break a deck.\n'
                f'  By hand: .box box-navy|blue|green|yellow|red, .cols split-panels\n'
                f'  + .split-panel split-panel-*, .pill pill-*, ul.tight, <table>.\n'
                f'  Read SKILL.md section 4a first — there is no browser here. -->\n'
                f'        </section>')

    pills = "".join(
        f'\n            <span class="pill pill-{c}">{esc(p)}</span>'
        for p, c in zip(plan.get("pills", []),
                        ["navy", "blue", "green", "yellow", "red"] * 4))

    docs_href = plan.get("docs_href")
    docs_btn = (f'\n          <a href="{esc(docs_href)}" class="btn">'
                f'<i class="fas fa-book"></i> '
                f'{esc(plan.get("docs_label", "Read the Case Study"))}</a>'
                if docs_href else "")

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{esc(plan['title'])} — Mark</title>
{links}
    <style>
{styles_for(plan, agenda_cards=len(flat))}
    </style>
  </head>
  <!-- {DECK_TYPE_BANNER[plan['deck_type']]}
       audience: {esc(plan.get('audience') or 'not recorded')} -->
  <body>
    <div class="local-return-bar">
      <a href="../../walkthroughs/index.html">&larr; Back to Walkthroughs</a>
    </div>
    <div class="reveal">
      <div class="slides">

        <section class="title-slide" data-background-gradient="linear-gradient(135deg, #1e293b, #4f46e5 60%, #0ea5e9)">
          <div class="logo-row">
            <img class="brand-logo brand-logo-site" src="../../assets/logo.svg" alt="Mark" />
          </div>
          <h1>{esc(plan['title'])}</h1>
          <p class="subtitle">{esc(plan.get('subtitle', ''))}</p>
          <p>{pills}
          </p>
          <p class="team">{SITE_OWNER}</p>{docs_btn}
        </section>

        <section class="agenda-slide" data-background-color="#f1f5f9">
          <h2><i class="fas fa-list-check"></i> Agenda</h2>
          <p class="agenda-intro">
            {esc(plan.get('agenda_intro', 'Select any section to jump straight to it.'))}
          </p>
          <div class="agenda-grid" aria-label="Agenda quick navigation">
{chr(10).join(agenda)}
          </div>
        </section>

{chr(10).join(content)}

      </div>
    </div>
{nav.replace('Slide 1 of 15', f'Slide 1 of {total}')
    if 'Slide 1 of 15' in nav
    else re.sub(r'Slide 1 of \\d+', f'Slide 1 of {total}', nav)}
{script}
  </body>
</html>
"""


def _site_meta():
    """md-to-docs' site_meta module (favicon + link-preview tags), or None."""
    scripts = Path(__file__).resolve().parents[2] / "md-to-docs" / "scripts"
    if not (scripts / "site_meta.py").is_file():
        return None
    sys.path.insert(0, str(scripts))
    import site_meta
    return site_meta


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", default=".",
                    help="Path to the mark repo checkout (default: .)")
    ap.add_argument("--plan", required=True, help="Deck plan JSON")
    ap.add_argument("--like", default="portfolio-site",
                    help="Existing deck to copy the reveal shell from "
                         "(default: portfolio-site, the reference deck)")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite an existing deck at that slug")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    pdir = repo_root / PRESENTATIONS
    if not pdir.is_dir():
        sys.exit(f"error: {pdir} not found — is --repo-root correct?")

    like = pdir / args.like / "index.html"
    if not like.is_file():
        sys.exit(f"error: --like deck not found at {like}")

    plan = load_plan(Path(args.plan))
    out = pdir / plan["slug"] / "index.html"
    if out.exists() and not args.force:
        sys.exit(f"error: {out} already exists — pass --force to overwrite "
                 f"(this discards any slides written there)")

    out.parent.mkdir(parents=True, exist_ok=True)
    deck_html = build(plan, like)
    meta = _site_meta()
    if meta:  # favicon + link-preview tags, same as every other page
        deck_html = meta.apply(out.relative_to(pdir.parent).as_posix(), deck_html)
    out.write_text(deck_html, encoding="utf-8")

    slides = 2 + sum(len(p.get("slides", [])) for p in plan["phases"])
    print(f"\n  wrote {out.relative_to(repo_root)}")
    print(f"    {slides} slides (title + agenda + {slides - 2} content)")
    print(f"    deck type: {plan['deck_type']} — "
          f"{DECK_TYPE_BANNER[plan['deck_type']]}")
    print(f"\n  Next:")
    print(f"    1. Write the content slides — the placeholders say what to use.")
    print(f"    2. Add a card to _deploy/walkthroughs/index.html, and uncomment the")
    print(f"       'Walkthrough slides' button on the case study's index page.")
    print(f"    3. python3 validate_deck.py --repo-root {args.repo_root} "
          f"--deck {plan['slug']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
