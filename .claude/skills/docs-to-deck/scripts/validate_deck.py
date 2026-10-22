#!/usr/bin/env python3
"""
validate_deck.py — the review step for a presentation, because nothing in CI
looks at one.

A broken deck fails in front of an audience. Every check here maps to something
that actually goes wrong: an agenda card that jumps to the wrong slide, a nav
label left saying "of 15" after a slide was cut, a link that 404s on the
projector, a stray brace that leaves the agenda inert.

Usage:
    python3 validate_deck.py --repo-root . --deck portfolio-site
    python3 validate_deck.py --repo-root . --all
    python3 validate_deck.py --repo-root . --all --quiet

Exit codes:
    0 = no failures (warnings are allowed)
    1 = one or more failures

Severities follow the companion skills: things that break the deck in the room
are FAILURES; things worth knowing are WARNINGS.
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

PRESENTATIONS = "_deploy/presentations"
HUB = "_deploy/walkthroughs/index.html"
SHARED_CSS = "layout-fix.css"

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
    "path", "stop", "text", "use", "rect", "circle", "line", "polyline",
    "polygon", "ellipse",
}


class Report:
    """Same shape as the companion skills' reports, so they read alike."""

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
    """Unclosed and mis-nested elements — a deck is one long HTML document."""

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
            self.errors.append(f"</{tag}> closed out of order "
                               f"(open: {self.stack[-1]})")
            while self.stack and self.stack.pop() != tag:
                pass
        else:
            self.errors.append(f"</{tag}> with no matching open tag")


def top_level_sections(html: str) -> list:
    """
    Indices of the deck's horizontal slides: the direct <section> children of
    <div class="slides">. Nested <section>s are vertical stacks and do not
    count towards the horizontal index the agenda targets.
    """
    m = re.search(r'<div class="slides">', html)
    if not m:
        return []
    depth = 0
    out = []
    for token in re.finditer(r"<(/?)section\b", html[m.end():]):
        if token.group(1):
            depth -= 1
        else:
            if depth == 0:
                out.append(token.start())
            depth += 1
    return out


def is_reveal_deck(html: str) -> bool:
    """
    A reveal.js deck, as opposed to a site-chrome landing page. Both live under
    _deploy/presentations/<slug>/index.html, so the distinction has to be made
    from the content: a folder can hold a landing page with no deck.
    """
    return 'class="reveal"' in html or "reveal.js" in html


class LayoutAudit(HTMLParser):
    """
    The layout faults that survive every structural check and only show up on a
    projector: content escaping its container, and classes that were never
    styled. Both are decidable from the source, so there is no excuse for
    finding them in the room.
    """

    # .split-panel is height:100% with no overflow handling, and the reference
    # decks put nothing but h3 + p/ul inside one. A .box nested in a panel
    # brings its own margins and a hover transform, and spills out of it.
    NO_NEST = {"box": "split-panel"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.open_classes = []
        self.nesting = []
        self.classes = set()
        self.class_sets = []
        self._pre = None
        self.wide_pre = []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "")
        names = cls.split()
        self.classes.update(names)
        if names:
            self.class_sets.append(names)
        if tag not in VOID_TAGS:
            self.open_classes.append(names)
            for inner, outer in self.NO_NEST.items():
                if inner in names and any(
                        outer in anc for anc in self.open_classes[:-1]):
                    self.nesting.append((self.getpos()[0], inner, outer))
        if tag == "pre":
            self._pre = (self.getpos()[0], names, [])

    def handle_data(self, data):
        if self._pre is not None:
            self._pre[2].append(data)

    def handle_endtag(self, tag):
        if tag == "pre" and self._pre is not None:
            line, names, chunks = self._pre
            text = "".join(chunks)
            widest = max((len(l) for l in text.split("\n")), default=0)
            if widest > 70:
                self.wide_pre.append((line, names, widest))
            self._pre = None
        if tag in VOID_TAGS:
            return
        if self.open_classes:
            self.open_classes.pop()


def local_style(html: str) -> str:
    """The deck's own <style> block — per-deck CSS belongs there, not in the shared sheet."""
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))


def defined_classes(css: str) -> set:
    return set(re.findall(r"\.([A-Za-z][\w-]*)", css))


# Semantic hooks the reference decks carry with no rule behind them — markers
# for the eye, not styling. Not worth reporting.
CLASS_ALLOW = {"agenda-slide", "reveal", "slides", "no-js"}

# Elements where a bare em is correct: they normalise against a parent that is
# itself clamped, which is how the shared sheet uses em (.box h3 { 1em }).
# Matched against the selector's rightmost element name, never as a substring —
# ".reveal table.compact" must not be excused because "compact" contains "p".
EM_OK_ELEMENTS = {"code", "h1", "h2", "h3", "h4", "h5", "h6", "p", "li",
                  "strong", "em", "span", "small", "td", "th", "a"}


def em_is_deliberate(selector: str) -> bool:
    """
    True when a bare em on this selector is a child-relative normalisation
    rather than a new absolute scale. Only the rightmost compound matters —
    that is the element actually being sized.
    """
    tokens = selector.replace(">", " ").replace(",", " ").split()
    if not tokens:
        return False
    last = tokens[-1]
    if "::after" in last or "::before" in last:
        return True
    # A class or id on the rightmost compound means a component is being given a
    # new scale of its own (table.compact), not normalised against its parent.
    if "." in last or "#" in last:
        return False
    element = re.match(r"^([a-zA-Z][\w-]*)", last)
    return bool(element) and element.group(1) in EM_OK_ELEMENTS


def validate_layout(name: str, html: str, shared_css: str, rep: Report):
    """
    Checks derived from breaking a real deck. Each one names the shared rule it
    protects, because the fix is always "use the house component", never "add
    more local CSS".
    """
    local = local_style(html)

    audit = LayoutAudit()
    audit.feed(html)

    # ── containers that cannot hold what was put in them ──────────────────
    rep.check(not audit.nesting,
              f"{name}: no .box nested inside a .split-panel",
              "; ".join(f"line {ln}: .{i} inside .{o} — .split-panel is "
                        f"height:100% with no overflow handling, so the box "
                        f"escapes it; use <p><strong>…</strong></p> instead"
                        for ln, i, o in audit.nesting[:3]))

    # ── type that does not scale with the rest of the deck ────────────────
    offenders = []
    for rule in re.findall(r"([^{}]+)\{([^{}]*)\}", local):
        selector, body = rule[0].strip(), rule[1]
        for value in re.findall(r"font-size:\s*([^;]+)", body):
            if "clamp" in value:
                continue
            if value.strip().endswith("em") and em_is_deliberate(selector):
                continue          # child-relative on purpose
            offenders.append(f"{selector.splitlines()[-1].strip()} -> {value.strip()}")
    rep.check(not offenders,
              f"{name}: local font sizes use the shared clamp() idiom",
              f"{'; '.join(offenders[:3])} — layout-fix.css sizes every element "
              f"as clamp(<rem>, <vw>, <rem>) so the deck scales as one set; a "
              f"bare em/rem/px has no vw term and stays put while the rest "
              f"scales", hard=False)

    # ── ASCII diagrams that the shared pre rule will mangle ───────────────
    # .reveal pre sets white-space: pre-wrap + word-break: break-word, which
    # wraps a wide diagram mid-line and destroys its column alignment.
    overridden = "white-space: pre;" in local or "white-space:pre;" in local
    unguarded = [(ln, w) for ln, names, w in audit.wide_pre if not names]
    if audit.wide_pre and not overridden:
        rep.warn(f"{name}: {len(audit.wide_pre)} <pre> block(s) wider than 70 "
                 f"columns with no 'white-space: pre' override — the shared "
                 f"pre-wrap will wrap them mid-line and break the alignment "
                 f"(widest: {max(w for _, _, w in audit.wide_pre)} cols)")
    else:
        rep.ok(f"{name}: wide <pre> blocks are guarded against pre-wrap")
    if unguarded and overridden:
        rep.warn(f"{name}: wide <pre> on line(s) "
                 f"{', '.join(str(ln) for ln, _ in unguarded[:3])} carry no "
                 f"class, so the local white-space override may not reach them")

    # ── classes nothing styles ────────────────────────────────────────────
    # Only an element where *nothing* is styled is interesting. A variant
    # marker beside a styled base class is normal and deliberate — e.g.
    # <path class="flow s1"> with no .s1 rule because s1 is the un-delayed
    # default. Reporting those buries the real case: a class invented alone,
    # like a .cell-blue on a <td> when the sheet only has cell-green/red/…
    known = defined_classes(shared_css) | defined_classes(local) | CLASS_ALLOW
    ignorable = ("fa-", "fa", "md-")
    orphans = set()
    for names in audit.class_sets:
        candidates = [c for c in names if not c.startswith(ignorable)]
        if candidates and not any(c in known for c in candidates):
            orphans.update(candidates)
    unstyled = sorted(orphans)
    rep.check(not unstyled,
              f"{name}: every styled element has a rule behind it",
              f"nothing styles: {', '.join(unstyled[:6])} — either a typo or a "
              f"class invented without a rule (the shared sheet has "
              f"cell-green/yellow/orange/red, for instance, but no cell-blue)",
              hard=False)


def validate_landing_page(name: str, html: str, deck_dir: Path, rep: Report):
    """A per-project landing page under presentations/: check it goes somewhere."""
    rep.section(f"{name}  [landing page, not a deck]")
    links = [r for r in re.findall(r'href="([^"#:]+)"', html)
             if not r.startswith(("http", "//"))]
    onward = [r for r in links
              if "walkthroughs" not in r and not r.endswith(".css")]
    rep.check(bool(onward),
              f"{name}: links to at least one deck",
              "links only back to the hub — Walkthroughs advertises "
              "this project but there is nothing behind it", hard=False)
    missing = [r for r in set(links)
               if not (deck_dir / unquote(r.split("#")[0])).resolve().exists()]
    rep.check(not missing, f"{name}: every relative href resolves",
              f"missing: {', '.join(sorted(missing))}")


def validate_deck(deck_dir: Path, hub_html: str, rep: Report, shared_css: str = ""):
    name = deck_dir.name
    page = deck_dir / "index.html"
    html = page.read_text(encoding="utf-8", errors="replace")

    if not is_reveal_deck(html):
        validate_landing_page(name, html, deck_dir, rep)
        return

    rep.section(f"{name}")

    # ── slide count vs the nav label ──────────────────────────────────────
    slides = top_level_sections(html)
    rep.check(bool(slides), f"{name}: has slides",
              "a reveal.js page with no <section> inside .slides")
    if not slides:
        return

    label = re.search(r'id="deckNavMeta"[^>]*>\s*Slide\s+\d+\s+of\s+(\d+)', html)
    if not label:
        rep.warn(f"{name}: no deckNavMeta label — the nav bar shows no position")
    else:
        stated = int(label.group(1))
        rep.check(stated == len(slides),
                  f"{name}: nav label matches the slide count ({len(slides)})",
                  f"label says {stated}, the deck has {len(slides)}", hard=False)

    # ── agenda wiring ─────────────────────────────────────────────────────
    targets = [(int(t), int(s), int(e)) for t, s, e in re.findall(
        r'data-slide-target="(\d+)"\s+data-slide-start="(\d+)"\s+data-slide-end="(\d+)"',
        html)]
    bare = len(re.findall(r'data-slide-target="', html))
    if bare:
        rep.check(len(targets) == bare,
                  f"{name}: every agenda card has target/start/end",
                  f"{bare} cards but only {len(targets)} fully wired", hard=False)
        out_of_range = [t for t, _, _ in targets if t < 0 or t >= len(slides)]
        rep.check(not out_of_range,
                  f"{name}: all {len(targets)} agenda targets are in range",
                  f"targets past the last slide ({len(slides) - 1}): {out_of_range}")
        bad_span = [(t, s, e) for t, s, e in targets if not s <= t <= e]
        rep.check(not bad_span, f"{name}: agenda highlight spans contain their target",
                  f"{bad_span}", hard=False)
    else:
        rep.warn(f"{name}: no agenda cards — fine for a short deck, "
                 f"but the agenda slide cannot navigate")

    # ── the inline scripts have to parse ──────────────────────────────────
    blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    if not shutil.which("node"):
        rep.warn(f"{name}: node not on PATH — skipped the JavaScript syntax check")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            for i, block in enumerate(blocks):
                if not block.strip():
                    continue
                p = Path(tmp) / f"b{i}.js"
                p.write_text(block, encoding="utf-8")
                r = subprocess.run(["node", "--check", str(p)],
                                   capture_output=True, text=True, check=False)
                first = next(iter((r.stderr or "").strip().splitlines()),
                             "syntax error")
                rep.check(r.returncode == 0,
                          f"{name}: inline script {i + 1}/{len(blocks)} parses", first)

    # ── well-formedness ───────────────────────────────────────────────────
    tb = TagBalance()
    tb.feed(html)
    unclosed = [t for t in tb.stack if t not in ("html", "body")]
    rep.check(not tb.errors and not unclosed, f"{name}: tags balanced",
              "; ".join(tb.errors[:3] + [f"unclosed <{t}>" for t in unclosed[:3]]))

    # ── the shared brand layer ────────────────────────────────────────────
    rep.check(f"../{SHARED_CSS}" in html, f"{name}: links ../{SHARED_CSS}",
              "without it the deck renders unstyled", hard=False)
    section_rule = re.search(r"\.reveal \.slides > section\s*\{([^}]*)\}", shared_css or "")
    rep.check(not shared_css or bool(section_rule and re.search(
                  r"padding:\s*calc\(\s*var\(--deck-bar-h\)", section_rule.group(1))),
              f"{name}: slides are padded below the fixed top bar",
              f"{SHARED_CSS} does not add --deck-bar-h to the section padding, so "
              f"the fixed Back to Walkthroughs bar covers every slide's heading. "
              f"(Padding on .reveal does not help: the slides are absolutely "
              f"positioned at top: 0.)")
    rep.check("walkthroughs/index.html" in html,
              f"{name}: has a return link to Walkthroughs",
              "no .local-return-bar link — the audience cannot get back",
              hard=False)

    # ── every relative link has to resolve ────────────────────────────────
    missing = []
    for ref in sorted(set(re.findall(r'(?:href|src)="([^"#:]+)"', html))):
        if ref.startswith(("http", "//", "#", "mailto:", "data:")):
            continue
        target = (deck_dir / unquote(ref.split("#")[0])).resolve()
        if not target.exists():
            missing.append(ref)
    rep.check(not missing, f"{name}: every relative href/src resolves",
              f"missing: {', '.join(missing)}")

    # ── registered in the hub ─────────────────────────────────────────────
    rep.check(f"presentations/{name}/index.html" in hub_html,
              f"{name}: registered in {HUB}",
              "the deck exists but nothing links to it", hard=False)

    # ── layout rules the structural checks cannot see ─────────────────────
    validate_layout(name, html, shared_css, rep)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", default=".",
                    help="Path to the mark repo checkout (default: .)")
    ap.add_argument("--deck", help="One deck folder under _deploy/presentations/")
    ap.add_argument("--all", action="store_true", help="Validate every deck")
    ap.add_argument("--quiet", action="store_true",
                    help="Print only WARN and FAIL lines, plus the summary")
    args = ap.parse_args()

    if not args.all and not args.deck:
        sys.exit("error: pass --deck <name> or --all")

    repo_root = Path(args.repo_root).resolve()
    pdir = repo_root / PRESENTATIONS
    if not pdir.is_dir():
        sys.exit(f"error: {pdir} not found — is --repo-root correct?")

    hub = repo_root / HUB
    hub_html = hub.read_text(encoding="utf-8") if hub.is_file() else ""

    css = pdir / SHARED_CSS
    shared_css = css.read_text(encoding="utf-8") if css.is_file() else ""

    if args.all:
        decks = [d for d in sorted(pdir.iterdir())
                 if d.is_dir() and (d / "index.html").is_file()]
    else:
        decks = [pdir / args.deck]
        if not (decks[0] / "index.html").is_file():
            sys.exit(f"error: no deck at {decks[0] / 'index.html'}")

    rep = Report(quiet=args.quiet)
    if not hub_html:
        rep.warn(f"{HUB} not found — cannot check deck registration")
    if not shared_css:
        rep.warn(f"{PRESENTATIONS}/{SHARED_CSS} not found — cannot check "
                 f"classes against the shared brand layer")
    for deck in decks:
        validate_deck(deck, hub_html, rep, shared_css)

    print("\n" + "=" * 68)
    print(f"  decks: {len(decks)}   passed: {rep.passed}   "
          f"warnings: {len(rep.warnings)}   failures: {len(rep.failures)}")
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
