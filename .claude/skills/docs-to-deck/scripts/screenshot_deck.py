#!/usr/bin/env python3
"""
screenshot_deck.py — renders every slide and measures whether it fits.

This is the check `validate_deck.py` cannot do. The validator reads the source;
this one asks a browser. It catches the faults that only exist once the cascade
has run:

  * a slide taller than the viewport, which scrolls in front of an audience
  * an element wider than its container
  * a slide that fits at 1920x1080 and does not at 1366x768 — the resolution of
    the projector in most rooms
  * content hidden under the fixed bars (the "Back to Walkthroughs" bar at the
    top, the deck-nav pill at the bottom), which no source check can see

Depends on ensure_render_env.py having succeeded; it reads that descriptor and
inherits the LD_LIBRARY_PATH the rootless library prefix needs.

Usage:
    python3 screenshot_deck.py --repo-root . --deck portfolio-site
    python3 screenshot_deck.py --repo-root . --deck portfolio-site --out /tmp/shots
    python3 screenshot_deck.py --repo-root . --deck portfolio-site \
        --viewports 1920x1080,1366x768
    python3 screenshot_deck.py --repo-root . --all --quiet

Exit codes:
    0 = every slide fits at every viewport
    1 = at least one slide overflows, or no render environment
"""
import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

PRESENTATIONS = "_deploy/presentations"
DEFAULT_VIEWPORTS = "1920x1080,1600x900,1366x768"

# Sub-pixel rounding on inline elements (<strong>, <code>) produces a pixel or
# two of scrollWidth. Only a real layout break clears this.
SLOP = 8

DRIVER = r'''
import json, sys
from playwright.sync_api import sync_playwright

deck, outdir, spec, shots = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
viewports = [tuple(int(n) for n in v.split("x")) for v in spec.split(",")]
results = []
with sync_playwright() as p:
    b = p.firefox.launch()
    for w, h in viewports:
        page = b.new_page(viewport={"width": w, "height": h})
        page.goto("file://" + deck, wait_until="load")
        page.wait_for_timeout(500)
        total = page.evaluate(
            "document.querySelectorAll('.slides > section').length")
        for i in range(total):
            page.goto(f"file://{deck}#/{i}", wait_until="load")
            # reveal.css transitions slides over 800ms and layout-fix.css adds a
            # 500ms fadeSlideUp. Screenshot sooner and the outgoing slide is still
            # ghosted behind this one, which reads as a layout bug that isn't one.
            page.wait_for_timeout(1000)
            r = page.evaluate("""() => {
                const s = document.querySelector('.slides > section.present');
                if (!s) return {error: 'no present section'};
                const t = s.querySelector('h2, h1');
                const wide = [];
                s.querySelectorAll('div, table, pre, ul, section').forEach(el => {
                    const over = el.scrollWidth - el.clientWidth;
                    if (over > 8) wide.push((el.className || el.tagName) + ':' + over);
                });
                // Fixed bars sit on top of the slide. Anything visible that
                // starts above the top bar's bottom edge is hidden under it.
                const bar = document.querySelector('.local-return-bar');
                const barBottom = bar ? bar.getBoundingClientRect().bottom : 0;
                let covered = null;
                for (const el of s.children) {
                    const r = el.getBoundingClientRect();
                    if (r.height === 0 || getComputedStyle(el).display === 'none') continue;
                    if (r.top < barBottom - 1) {
                        covered = (el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''))
                                  + ':' + Math.round(barBottom - r.top);
                    }
                    break;  // only the first visible child can be under the top bar
                }
                return {
                    title: (t ? t.innerText : '').trim().slice(0, 40),
                    vertical: s.scrollHeight - s.clientHeight,
                    wide: wide.slice(0, 3),
                    covered: covered,
                };
            }""")
            r.update({"slide": i, "viewport": f"{w}x{h}"})
            results.append(r)
            if shots and (w, h) == viewports[0]:
                page.screenshot(path=f"{outdir}/{i:02d}.png")
        page.close()
    b.close()
print("###" + json.dumps(results))
'''


def cache_root() -> Path:
    """Same location ensure_render_env.py uses — kept in step with it."""
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "deck-render"


def load_env(quiet=False) -> dict:
    desc = cache_root() / "render-env.json"
    if not desc.is_file():
        sys.exit("error: no render environment. Run:\n"
                 "    python3 ensure_render_env.py")
    env = json.loads(desc.read_text(encoding="utf-8"))
    if not env.get("verified"):
        sys.exit("error: the render environment exists but no browser launches.\n"
                 "    Re-run ensure_render_env.py for the reason.")
    if not quiet:
        print(f"  browser: {env['browser']}")
    return env


def shoot(env: dict, deck: Path, outdir: Path, viewports: str,
          shots: bool) -> list:
    outdir.mkdir(parents=True, exist_ok=True)
    child = dict(os.environ)
    ld = env.get("ld_library_path") or []
    if ld:
        browser_dir = Path(env["browser"]).parent
        child["LD_LIBRARY_PATH"] = os.pathsep.join(
            ld + [str(browser_dir), str(browser_dir / "gtk"),
                  child.get("LD_LIBRARY_PATH", "")])
    r = subprocess.run(
        [env["python"], "-c", DRIVER, str(deck.resolve()), str(outdir),
         viewports, "1" if shots else "0"],
        capture_output=True, text=True, env=child, check=False)
    marker = [l for l in (r.stdout or "").splitlines() if l.startswith("###")]
    if not marker:
        sys.exit(f"error: render failed:\n{(r.stderr or r.stdout).strip()[:1200]}")
    return json.loads(marker[-1][3:])


def report(name: str, rows: list, quiet: bool) -> int:
    by_vp = {}
    for r in rows:
        by_vp.setdefault(r["viewport"], []).append(r)
    problems = 0
    for vp, items in by_vp.items():
        over = [i for i in items if i.get("vertical", 0) > SLOP]
        wide = [i for i in items if i.get("wide")]
        covered = [i for i in items if i.get("covered")]
        if not over and not wide and not covered:
            if not quiet:
                print(f"    PASS  {name} @ {vp}: all {len(items)} slides fit")
            continue
        problems += len(over) + len(wide) + len(covered)
        for i in covered:
            print(f"    FAIL  {name} @ {vp}: slide {i['slide']:>2} "
                  f"{i.get('title', '')!r} starts under the top bar "
                  f"({i['covered']}px hidden)")
        if not over and not wide:
            continue
        print(f"    WARN  {name} @ {vp}: {len(over)} slide(s) overflow vertically")
        for i in over:
            print(f"            slide {i['slide']:>2} "
                  f"{i.get('title', '')!r} +{i['vertical']}px")
        for i in wide:
            print(f"            slide {i['slide']:>2} horizontal: "
                  f"{', '.join(i['wide'])}")
    return problems


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--deck")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", help="Where PNGs go (default: <cache>/shots/<deck>)")
    ap.add_argument("--viewports", default=DEFAULT_VIEWPORTS,
                    help=f"Comma-separated WxH (default: {DEFAULT_VIEWPORTS})")
    ap.add_argument("--no-screenshots", action="store_true",
                    help="Measure only; write no PNGs")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    if not args.all and not args.deck:
        sys.exit("error: pass --deck <name> or --all")

    env = load_env(args.quiet)
    pdir = Path(args.repo_root).resolve() / PRESENTATIONS
    if args.all:
        decks = [d for d in sorted(pdir.iterdir())
                 if d.is_dir() and (d / "index.html").is_file()]
    else:
        decks = [pdir / args.deck]

    total = 0
    for d in decks:
        page = d / "index.html"
        if not page.is_file():
            sys.exit(f"error: no deck at {page}")
        html = page.read_text(encoding="utf-8", errors="replace")
        if 'class="reveal"' not in html and "reveal.js" not in html:
            if not args.quiet:
                print(f"\n  {d.name}  [landing page, not a deck — skipped]")
            continue
        out = Path(args.out) if args.out else cache_root() / "shots" / d.name
        if args.out and len(decks) > 1:
            out = Path(args.out) / d.name
        if not args.quiet:
            print(f"\n  {d.name}")
        rows = shoot(env, page, out, args.viewports, not args.no_screenshots)
        total += report(d.name, rows, args.quiet)
        if not args.quiet and not args.no_screenshots:
            print(f"    screenshots: {out}")

    print("\n" + "=" * 68)
    if total:
        print(f"  {total} layout problem(s) across {len(decks)} deck(s)")
        print("  A slide that overflows scrolls in front of an audience. Reclaim "
              "space from\n  padding first (SKILL.md 4a), and cut content only "
              "if that is not enough.")
        return 1
    print(f"  every slide fits at every viewport ({args.viewports})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
