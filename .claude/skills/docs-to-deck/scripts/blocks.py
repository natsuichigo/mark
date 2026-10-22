#!/usr/bin/env python3
"""
blocks.py — renders declared slide content into the house components from
layout-fix.css.

Why this exists: writing slide HTML by hand is where decks break. One
deck shipped with a .box nested inside a .split-panel (overlapping content), a
bare-em font size that did not scale, an ASCII diagram mangled by the shared
pre-wrap, and a .cell-blue that nothing styled. Every one of those is a markup
mistake, not a content mistake — so the markup is generated here and the model
supplies only the words.

There is no headless browser on these machines (see SKILL.md 4a), so a deck
cannot be previewed before it ships. Making the bad markup unrepresentable is
the substitute for looking at it.

The two invariants this module enforces structurally:

  1. A .box is never emitted inside a .split-panel. Ask for one and you get
     <p><strong>lead</strong> text</p>, which is what the reference decks use.
  2. Nothing is sized with a bare em. Components that need a smaller scale get
     a clamp() derived from the shared sheet's own rule, via STYLE_SNIPPETS.

Imported by scaffold_deck.py. Standalone use:

    python3 blocks.py --demo
"""
import argparse
import html
import json
import sys

# Tones the shared sheet actually defines. A tone outside these sets would
# render as an unstyled element — the .cell-blue mistake.
BOX_TONES = {"navy", "blue", "green", "yellow", "red"}
PANEL_TONES = {"navy", "blue", "green", "yellow", "red"}
ROW_TONES = {"red", "yellow", "green"}
CELL_TONES = {"green", "yellow", "orange", "red"}
PILLAR_TONES = {"train", "docs", "framework"}

# Local CSS the renderer emits only for the blocks a deck actually uses. Each
# size is derived from the shared rule it narrows, never invented:
#   .reveal table -> clamp(0.825rem, 1.25vw, 1.075rem)
#   .reveal pre   -> clamp(0.805rem, 1.15vw, 1.025rem)
STYLE_SNIPPETS = {
    "table_compact": """      /* ~85% of the shared table size, same clamp() idiom so it scales with it. */
      .reveal table.compact { font-size: clamp(0.7rem, 1.06vw, 0.92rem); }
      .reveal table.compact td, .reveal table.compact th { padding: 4px 8px; }
      .reveal table.compact code { font-size: 0.94em; padding: 1px 4px; }""",
    "pre_flow": """      /* The shared .reveal pre sets white-space: pre-wrap + word-break: break-word,
         which wraps a wide ASCII diagram mid-line and destroys its alignment. */
      .reveal pre.flow, .reveal pre.flow-sm {
        white-space: pre;
        word-break: normal;
        overflow-x: auto;
      }
      .reveal pre.flow    { font-size: clamp(0.54rem, 0.8vw, 0.74rem); line-height: 1.38; }
      .reveal pre.flow-sm { font-size: clamp(0.46rem, 0.7vw, 0.64rem); line-height: 1.34; }""",
    "agenda_two_col": """      /* More than ~12 agenda cards will not fit the shared single-column flex grid. */
      @media (min-width: 900px) {
        .reveal .agenda-grid { display: grid; grid-template-columns: 1fr 1fr; align-items: start; }
        .reveal .agenda-phase { grid-column: 1 / -1; }
      }""",
    # Values measured on a real deck: two columns alone still left 13+ cards
    # under several phase headers 100-220px over at 1366x768.
    "agenda_compact": """      /* Many cards under several phase headers overflow a 1366x768 projector — each
         header forces a row break. Reclaim it from padding rather than content. */
      @media (min-width: 900px) {
        .reveal .agenda-grid { gap: 0.35em; }
        .reveal .agenda-phase { margin-top: 0.2em; padding: 0.15em 0.2em; }
        .reveal .agenda-card { padding: clamp(6px, 0.8vh, 9px) clamp(8px, 1vw, 11px); }
        .reveal .agenda-card__title { font-size: clamp(0.82rem, 1.05vw, 0.98rem); }
        .reveal .agenda-card__meta { font-size: clamp(0.62rem, 0.75vw, 0.72rem); }
      }
      /* The per-card "Slide N" line is the cheapest thing to drop on a short screen:
         the order number is already on the card and the click target is unaffected. */
      @media (min-width: 900px) and (max-height: 820px) {
        .reveal .agenda-card__meta { display: none; }
        .reveal .agenda-intro { margin-bottom: 0.4em; }
      }""",
    "muted": """      .reveal .muted { color: #7a869a; }""",
    # Screenshots are capped by viewport HEIGHT, not width, because height is what
    # runs out first on a 1366x768 projector. Marker text uses the shared clamp().
    "shot": """      /* Framed screenshots of real pages, with numbered callout markers. */
      .reveal .shot { margin: 0.3em 0; }
      .reveal .shot-frame {
        display: inline-block; max-width: 100%; border-radius: 10px; overflow: hidden;
        background: #fff; box-shadow: 0 10px 30px rgba(var(--brand-primary-rgb), 0.22);
        border: 1px solid #d5deea;
      }
      .reveal .shot-bar {
        display: flex; align-items: center; gap: 6px; padding: 6px 10px;
        background: #eef2f7; border-bottom: 1px solid #d5deea;
      }
      .reveal .shot-bar span { width: 10px; height: 10px; border-radius: 50%; background: #c3ccd8; }
      .reveal .shot-bar span:nth-child(1) { background: #ee5f5b; }
      .reveal .shot-bar span:nth-child(2) { background: #f5c451; }
      .reveal .shot-bar span:nth-child(3) { background: #5cc16b; }
      .reveal .shot-bar em {
        margin-left: 8px; font-style: normal; color: #5b6b82;
        font-size: clamp(0.6rem, 0.8vw, 0.75rem); white-space: nowrap;
        overflow: hidden; text-overflow: ellipsis;
      }
      .reveal .shot-canvas { position: relative; line-height: 0; }
      .reveal .shot img { display: block; width: auto; max-width: 100%; margin: 0; border: 0; }
      .reveal .shot-sm img { max-height: 34vh; }
      .reveal .shot-md img { max-height: 52vh; }
      .reveal .shot-lg img { max-height: 64vh; }
      .reveal .shot figcaption {
        margin-top: 0.35em; color: #5b6b82; font-size: clamp(0.72rem, 0.95vw, 0.9rem);
      }
      .reveal .shot-marker {
        display: inline-flex; align-items: center; justify-content: center;
        width: 1.7em; height: 1.7em; border-radius: 50%; background: var(--brand-accent-2); color: #fff;
        font-weight: 700; font-size: clamp(0.7rem, 0.95vw, 0.9rem); line-height: 1;
        box-shadow: 0 0 0 3px #fff, 0 4px 10px rgba(0, 0, 0, 0.3); flex: none;
      }
      .reveal .shot-canvas .shot-marker { position: absolute; transform: translate(-50%, -50%); }
      .reveal .shot-legend { list-style: none; margin: 0.3em 0; padding: 0; }
      .reveal .shot-legend li {
        display: flex; align-items: flex-start; gap: 0.6em; margin: 0 0 0.55em;
        font-size: clamp(0.85rem, 1.2vw, 1.05rem); line-height: 1.35;
      }
      @media (max-height: 820px) {
        .reveal .shot-md img { max-height: 46vh; }
        .reveal .shot-lg img { max-height: 56vh; }
      }""",
    "stats": """      /* Big-number tiles. */
      .reveal .stat-row {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(7.5em, 1fr));
        gap: 0.6em; margin: 0.4em 0;
      }
      .reveal .stat {
        display: flex; flex-direction: column; gap: 0.2em; padding: 0.7em 0.9em;
        border-radius: 12px; color: #fff; box-shadow: 0 8px 20px rgba(var(--brand-primary-rgb), 0.18);
      }
      .reveal .stat-navy   { background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-light)); }
      .reveal .stat-blue   { background: linear-gradient(135deg, var(--brand-accent-2), var(--brand-accent)); }
      .reveal .stat-green  { background: linear-gradient(135deg, #0f7a3d, #22a45d); }
      .reveal .stat-yellow { background: linear-gradient(135deg, #b7791f, #e0a526); }
      .reveal .stat-red    { background: linear-gradient(135deg, var(--brand-accent), var(--brand-accent-2)); }
      .reveal .stat-value { font-size: clamp(1.6rem, 3.2vw, 2.8rem); font-weight: 800; line-height: 1; }
      .reveal .stat-label { font-size: clamp(0.72rem, 0.98vw, 0.92rem); opacity: 0.92; }""",
}


class BlockError(ValueError):
    """A block that would render as broken or unstyled markup."""


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=False)


def rich(text) -> str:
    """
    Slide prose carries inline markup — <strong>, <code>, <em>, &mdash;. Those
    are authored deliberately, so the text passes through unescaped. Blocks
    come from a plan the model writes, not from user input.
    """
    return str(text if text is not None else "")


def _icon(name) -> str:
    if not name:
        return ""
    prefix = "fab" if str(name).startswith("fa-windows") or str(name).startswith(
        "fa-linux") or str(name).startswith("fa-aws") else "fas"
    return f'<i class="{prefix} {esc(name)}"></i> '


def _tone(value, allowed, kind) -> str:
    if value is None:
        return ""
    if value not in allowed:
        raise BlockError(
            f"{kind} tone {value!r} is not styled by layout-fix.css "
            f"(has: {', '.join(sorted(allowed))})")
    return value


# ── individual blocks ────────────────────────────────────────────────────────

def r_para(b, ind, **_):
    cls = ' class="muted"' if b.get("muted") else ""
    return [f'{ind}<p{cls}>{rich(b["para"])}</p>']


def r_list(b, ind, **_):
    cls = ' class="tight"' if b.get("tight", True) else ""
    out = [f"{ind}<ul{cls}>"]
    out += [f"{ind}  <li>{rich(i)}</li>" for i in b["list"]]
    out.append(f"{ind}</ul>")
    return out


def r_box(b, ind, in_panel=False, **_):
    """
    Inside a .split-panel this degrades to a paragraph on purpose. The panel is
    height:100% with no overflow handling, so a nested .box escapes it and
    lands on the following content — the overlap bug.
    """
    lead, text = b.get("lead"), b.get("text", "")
    if in_panel:
        lead_html = f"<strong>{_icon(b.get('icon'))}{rich(lead)}</strong> " if lead else ""
        return [f"{ind}<p>{lead_html}{rich(text)}</p>"]
    tone = _tone(b["box"], BOX_TONES, "box")
    out = [f'{ind}<div class="box box-{tone}">']
    if lead:
        out.append(f"{ind}  <strong>{_icon(b.get('icon'))}{rich(lead)}</strong>")
    if text:
        out.append(f"{ind}  {rich(text)}")
    out.append(f"{ind}</div>")
    return out


def r_panels(b, ind, **_):
    """.cols split-panels — only h3 + p/ul inside, as the reference decks do."""
    out = [f'{ind}<div class="cols split-panels">']
    for p in b["panels"]:
        tone = _tone(p.get("tone", "blue"), PANEL_TONES, "panel")
        out.append(f'{ind}  <div class="split-panel split-panel-{tone}">')
        if p.get("title"):
            out.append(f'{ind}    <h3>{_icon(p.get("icon"))}{rich(p["title"])}</h3>')
        for inner in p.get("blocks", []):
            out += render_block(inner, f"{ind}    ", in_panel=True)
        out.append(f"{ind}  </div>")
    out.append(f"{ind}</div>")
    return out


def r_cols(b, ind, **_):
    """Plain .cols — a .box IS legal here; only .split-panel cannot hold one."""
    out = [f'{ind}<div class="cols">']
    for column in b["cols"]:
        out.append(f"{ind}  <div>")
        for inner in column:
            out += render_block(inner, f"{ind}    ")
        out.append(f"{ind}  </div>")
    out.append(f"{ind}</div>")
    return out


def r_table(b, ind, **_):
    t = b["table"]
    cls = ' class="compact"' if t.get("compact") else ""
    out = [f"{ind}<table{cls}>", f"{ind}  <thead>", f"{ind}    <tr>"]
    out += [f"{ind}      <th>{rich(h)}</th>" for h in t["headers"]]
    out += [f"{ind}    </tr>", f"{ind}  </thead>", f"{ind}  <tbody>"]
    width = len(t["headers"])
    for row in t["rows"]:
        cells = row.get("cells", row) if isinstance(row, dict) else row
        tone = _tone(row.get("tone"), ROW_TONES, "row") if isinstance(row, dict) else ""
        span = sum(int(c.get("rowspan", 1)) - 1
                   for c in cells if isinstance(c, dict))
        if len(cells) + span != width:
            raise BlockError(
                f"table row has {len(cells)} cells (+{span} rowspan) against "
                f"{width} headers: {cells!r}")
        row_attr = f' class="row-{tone}"' if tone else ""
        out.append(f"{ind}    <tr{row_attr}>")
        for c in cells:
            if isinstance(c, dict):
                ct = _tone(c.get("tone"), CELL_TONES, "cell")
                attrs = f' class="cell-{ct}"' if ct else ""
                if c.get("rowspan"):
                    attrs += f' rowspan="{int(c["rowspan"])}"'
                out.append(f'{ind}      <td{attrs}>{rich(c.get("text", ""))}</td>')
            else:
                out.append(f"{ind}      <td>{rich(c)}</td>")
        out.append(f"{ind}    </tr>")
    out += [f"{ind}  </tbody>", f"{ind}</table>"]
    return out


def r_pre(b, ind, **_):
    """ASCII diagram. Always classed, so the white-space guard reaches it."""
    scale = b.get("scale", "flow")
    if scale not in ("flow", "flow-sm"):
        raise BlockError("pre scale must be 'flow' or 'flow-sm'")
    body = b["pre"].rstrip("\n")
    widest = max((len(l) for l in body.split("\n")), default=0)
    if widest > 118:
        raise BlockError(
            f"ASCII block is {widest} columns wide — it will not fit a slide "
            f"even at flow-sm; shorten it or split the diagram")
    return [f'{ind}<pre class="{scale}"><code>{esc(body)}</code></pre>']


def r_pillars(b, ind, **_):
    """.today-pillars — a 3-up card grid; more than three wrap to further rows."""
    out = [f'{ind}<div class="today-pillars">']
    cycle = ["framework", "docs", "train"]
    for i, p in enumerate(b["pillars"]):
        tone = _tone(p.get("tone", cycle[i % 3]), PILLAR_TONES, "pillar")
        out.append(f'{ind}  <div class="today-pillar today-pillar-{tone}">')
        if p.get("title"):
            out.append(f'{ind}    <h3>{_icon(p.get("icon"))}{rich(p["title"])}</h3>')
        if p.get("text"):
            out.append(f'{ind}    <p>{rich(p["text"])}</p>')
        out.append(f"{ind}  </div>")
    out.append(f"{ind}</div>")
    return out


def r_buttons(b, ind, **_):
    out = [f'{ind}<div style="margin-top: 14px">']
    for btn in b["buttons"]:
        out.append(f'{ind}  <a href="{esc(btn["href"])}" class="btn btn-sm">'
                   f'{_icon(btn.get("icon"))}{esc(btn["label"])}</a>')
    out.append(f"{ind}</div>")
    return out


def r_shot(b, ind, **_):
    """
    A framed screenshot of a real page. Markers are numbered badges placed by
    percentage, so they stay on their target as the image scales; pair them
    with a `legend` block. `href` makes the image open the page it shows.
    """
    alt = b.get("alt")
    if not alt:
        raise BlockError(f"shot {b['shot']!r} needs alt text")
    size = b.get("size", "md")
    if size not in ("sm", "md", "lg"):
        raise BlockError("shot size must be 'sm', 'md' or 'lg'")
    img = f'<img src="{esc(b["shot"])}" alt="{html.escape(alt)}" loading="lazy" />'
    if b.get("href"):
        img = f'<a href="{esc(b["href"])}">{img}</a>'
    out = [f'{ind}<figure class="shot shot-{size}">',
           f'{ind}  <div class="shot-frame">',
           f'{ind}    <div class="shot-bar"><span></span><span></span><span></span>'
           f'<em>{esc(b.get("url", ""))}</em></div>',
           f'{ind}    <div class="shot-canvas">',
           f"{ind}      {img}"]
    for m in b.get("markers", []) or []:
        x, y = float(m["x"]), float(m["y"])
        if not (0 <= x <= 100 and 0 <= y <= 100):
            raise BlockError(f"marker {m.get('n')} is off the image: x={x}, y={y}")
        out.append(f'{ind}      <span class="shot-marker" '
                   f'style="left: {x:g}%; top: {y:g}%">{esc(m["n"])}</span>')
    out += [f"{ind}    </div>", f"{ind}  </div>"]
    if b.get("caption"):
        out.append(f"{ind}  <figcaption>{rich(b['caption'])}</figcaption>")
    out.append(f"{ind}</figure>")
    return out


def r_legend(b, ind, **_):
    """The key to a shot's markers: numbered to match, same badge style."""
    out = [f'{ind}<ol class="shot-legend">']
    for i, item in enumerate(b["legend"], start=1):
        out.append(f'{ind}  <li><span class="shot-marker">{i}</span>'
                   f'<span>{rich(item)}</span></li>')
    out.append(f"{ind}</ol>")
    return out


def r_stats(b, ind, **_):
    """Big-number tiles. Use real counts only — read them, don't estimate."""
    out = [f'{ind}<div class="stat-row">']
    for s in b["stats"]:
        tone = _tone(s.get("tone", "navy"), BOX_TONES, "stat")
        out.append(f'{ind}  <div class="stat stat-{tone}">'
                   f'<span class="stat-value">{esc(s["value"])}</span>'
                   f'<span class="stat-label">{rich(s["label"])}</span></div>')
    out.append(f"{ind}</div>")
    return out


RENDERERS = {
    "para": r_para, "list": r_list, "box": r_box, "panels": r_panels,
    "cols": r_cols, "table": r_table, "pre": r_pre, "pillars": r_pillars,
    "buttons": r_buttons, "shot": r_shot, "legend": r_legend, "stats": r_stats,
}


def render_block(block: dict, indent: str, in_panel: bool = False) -> list:
    if not isinstance(block, dict):
        raise BlockError(f"block must be an object, got {type(block).__name__}")
    keys = [k for k in RENDERERS if k in block]
    if len(keys) != 1:
        raise BlockError(
            f"a block needs exactly one of {sorted(RENDERERS)}; got {sorted(block)}")
    return RENDERERS[keys[0]](block, indent, in_panel=in_panel)


def render_slide_body(blocks: list, indent: str = "          ") -> list:
    out = []
    for b in blocks:
        out += render_block(b, indent)
    return out


def styles_for(plan: dict, agenda_cards: int = 0) -> str:
    """
    Only the local CSS the deck's own blocks need. Emitting the whole snippet
    library would leave dead rules behind for the next person to wonder about.
    """
    blob = json.dumps(plan, separators=(",", ":"))
    needed = {
        "table_compact": '"compact":true' in blob,
        "pre_flow": '"pre":' in blob,
        "muted": '"muted":true' in blob,
        "agenda_two_col": agenda_cards > 12,
        "agenda_compact": agenda_cards > 12,
        "shot": '"shot":' in blob or '"legend":' in blob,
        "stats": '"stats":' in blob,
    }
    ordered = [STYLE_SNIPPETS[key]
               for key in ("agenda_two_col", "agenda_compact", "table_compact",
                           "pre_flow", "muted", "shot", "stats")
               if needed[key]]
    header = ("      /* Per-deck CSS only. NEVER edit ../layout-fix.css — every deck shares it.\n"
              "         Sizes below use the shared clamp(<rem>, <vw>, <rem>) idiom so the deck\n"
              "         scales as one set; see SKILL.md section 4a. */")
    return "\n".join([header] + ordered) if ordered else header


DEMO = [
    {"box": "navy", "icon": "fa-bullseye", "lead": "The one-sentence version:",
     "text": "every image is <strong>built from source</strong> and validated before it exists."},
    {"panels": [
        {"tone": "blue", "title": "Stage 1", "icon": "fa-1",
         "blocks": [{"list": ["Attaches a second empty disk", "Partitions it fully"]},
                    {"box": "yellow", "lead": "Ansible cannot run here.",
                     "text": "The disk is never booted."}]},
        {"tone": "green", "title": "Stage 2", "icon": "fa-2",
         "blocks": [{"para": "Boots the Stage 1 AMI and runs Ansible."}]}]},
    {"table": {"compact": True, "headers": ["Image", "Platform", "Blocks?"],
               "rows": [["RHEL 8.10", "vSphere", {"text": "Yes", "tone": "green"}],
                        {"cells": ["AML23", "AWS", {"text": "Yes", "tone": "green"}],
                         "tone": "yellow"}]}},
    {"pre": "resolve ─┬─► build-aws ────┬─► summary\n         └─► build-vmware ─┘",
     "scale": "flow"},
]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true",
                    help="Render the demo blocks, showing the box-in-panel degradation")
    ap.add_argument("--blocks", help="A JSON file containing a list of blocks")
    args = ap.parse_args()
    if not args.demo and not args.blocks:
        ap.error("pass --demo or --blocks <file>")
    if args.demo:
        data = DEMO
    else:
        with open(args.blocks, encoding="utf-8") as fh:
            data = json.load(fh)
    try:
        print("\n".join(render_slide_body(data)))
    except BlockError as exc:
        sys.exit(f"error: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
