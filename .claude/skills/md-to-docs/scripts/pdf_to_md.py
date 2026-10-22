#!/usr/bin/env python3
"""
pdf_to_md.py — Convert a PDF into Markdown shaped for this skill's pipeline,
so it can then be rendered to a portal-themed page by md_to_page.py /
build_project.py.

    PDF  --(this script)-->  _src/<slug>.md  --(md_to_page.py)-->  <slug>.html

The output obeys the conventions md_to_page.py expects: exactly one leading
`# Title`, an optional one-line subtitle paragraph, then `##` sections (which
are what the on-page TOC is built from).

Usage:
    # one PDF -> one page
    python3 pdf_to_md.py --pdf plan.pdf --out _src/az-failover.md

    # one long PDF -> one page per chapter, plus nav[] entries
    python3 pdf_to_md.py --pdf handbook.pdf --split h1 \
        --out-dir _deploy/docs/my-project/_src \
        --config _deploy/docs/my-project/_src/docs.config.json --update-config \
        --section "Handbook"

PDF text extraction is lossy by nature: bullets lose their markers, headings
lose their level, two-column layouts interleave. This script does the
mechanical cleanup and then REPORTS what a human still has to check — always
read the generated Markdown before building pages from it.

See SKILL.md ("Workflow C") for the full flow. Run --help for all flags.
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

try:
    import pymupdf
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pymupdf"], check=True)
    import pymupdf

try:
    import pymupdf4llm
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pymupdf4llm"], check=True)
    import pymupdf4llm

# A page with less text than this is treated as having no text layer (scanned
# image) and becomes an OCR candidate.
TEXTLESS_CHARS = 40

# Lines that are only a page number, or "Page 4 of 12", or a lone roman numeral.
PAGE_NUM_RE = re.compile(
    r"^\s*(?:page\s+)?(?:\d{1,4}|[ivxlcdm]{1,7})(?:\s*(?:/|of)\s*\d{1,4})?\s*\.?\s*$",
    re.IGNORECASE)

# Presentational tags web-printed PDFs leave behind. Unwrapped (content kept,
# tag dropped) because they carry no meaning in the target theme, and raw HTML
# passes straight through Python-Markdown into the page.
PRESENTATIONAL_TAGS = ("u", "span", "font", "small", "big")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:60] or "page"


def clean_heading_text(text: str) -> str:
    """Strip inline emphasis from heading text.

    pymupdf4llm often emits `# **Section**`, because the heading is bold in the
    PDF. The `**` then ends up literal in the sidebar label, the <title> and the
    nav[] entry, all of which take plain text. Backticks are kept: code in a
    heading is meaningful and does render.
    """
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", text)
    return " ".join(text.strip(" *_#").split())


def parse_pages(spec: str, page_count: int):
    """'1-3,7' -> [0,1,2,6] (1-based inclusive input, 0-based output)."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part.lstrip("-"):
            a, _, b = part.partition("-")
            lo, hi = int(a), int(b)
        else:
            lo = hi = int(part)
        if lo < 1 or hi > page_count or lo > hi:
            sys.exit(f"error: --pages '{part}' is outside 1-{page_count}")
        out.extend(range(lo - 1, hi))
    return sorted(set(out))


def iter_code_aware(lines):
    """Yield (line, in_code) so line-level rewrites can skip fenced code and
    Markdown tables, where a 'cleanup' would corrupt real content."""
    in_fence = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            yield line, True
            continue
        protected = in_fence or stripped.startswith("|")
        yield line, protected


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def ocr_page(doc, pno: int, lang: str, dpi: int) -> str:
    """Rasterise one page and run the tesseract CLI over it."""
    pix = doc[pno].get_pixmap(dpi=dpi)
    proc = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", lang],
        input=pix.tobytes("png"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
    text = proc.stdout.decode("utf-8", "replace")
    # OCR gives flat text: keep paragraph breaks, drop intra-paragraph wraps.
    paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text)]
    return "\n\n".join(p for p in paras if p)


def extract_pages(args, report):
    """Return [(page_number, text)] for the selected pages.

    pymupdf4llm has two back ends and picks one at import time: the newer
    "layout" engine, and the older `pymupdf_rag` one. They take DIFFERENT
    keyword arguments, and the layout path swallows the ones it does not know
    through **kwargs — so passing `margins` to it fails silently rather than
    erroring. Hence the split below, and the report line naming the engine.
    """
    doc = pymupdf.open(args.pdf)
    if doc.needs_pass:
        sys.exit(f"error: {args.pdf} is password-protected — decrypt it first")

    pages = parse_pages(args.pages, doc.page_count) if args.pages else list(range(doc.page_count))
    report["pdf_pages"] = doc.page_count
    report["pages_used"] = len(pages)
    report["pdf_title"] = (doc.metadata or {}).get("title") or ""

    layout = bool(getattr(pymupdf4llm, "_use_layout", False))
    report["engine"] = "layout" if layout else "pymupdf_rag"
    md_kwargs = dict(pages=pages, page_chunks=True)
    ignored = []

    if layout:
        # The layout engine classifies running headers/footers itself, which
        # beats matching repeated text, and it can OCR without help.
        if not args.keep_repeats:
            md_kwargs.update(header=False, footer=False)
        md_kwargs.update(use_ocr=args.ocr != "off", force_ocr=args.ocr == "force",
                         ocr_language=args.ocr_lang, ocr_dpi=args.ocr_dpi)
        if args.margin_top or args.margin_bottom:
            ignored.append("--margin-top/--margin-bottom (layout engine crops nothing; it "
                           "classifies headers and footers instead — see --keep-repeats)")
        if args.table_strategy != "lines_strict":
            ignored.append("--table-strategy (layout engine detects tables on its own)")
    else:
        md_kwargs.update(margins=(0, args.margin_top, 0, args.margin_bottom),
                         table_strategy=args.table_strategy)
    report["ignored_flags"] = ignored

    if args.images:
        image_dir = Path(args.image_dir)
        image_dir.mkdir(parents=True, exist_ok=True)
        md_kwargs.update(write_images=True, image_path=str(image_dir), dpi=args.image_dpi)
        report["image_dir"] = str(image_dir)
    elif not layout:
        md_kwargs.update(ignore_images=True, ignore_graphics=True)

    chunks = pymupdf4llm.to_markdown(doc, **md_kwargs)
    if len(chunks) != len(pages):
        # Page numbers in the report and in OCR come from zipping these two, so
        # a mismatch would silently mislabel every page.
        sys.exit(f"error: pymupdf4llm returned {len(chunks)} chunks for {len(pages)} pages "
                 f"({report['engine']} engine). Retry with --engine "
                 f"{'legacy' if layout else 'layout'}.")

    out, ocr_done, ocr_skipped = [], [], []
    for pno, chunk in zip(pages, chunks):
        text = chunk["text"]
        if args.ocr != "off" and (args.ocr == "force" or len(text.strip()) < TEXTLESS_CHARS):
            try:
                ocr_text = ocr_page(doc, pno, args.ocr_lang, args.ocr_dpi)
            except (FileNotFoundError, RuntimeError) as exc:
                ocr_skipped.append((pno + 1, str(exc) or "tesseract not installed"))
            else:
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
                    ocr_done.append(pno + 1)
        out.append((pno + 1, text))

    report["ocr_pages"] = ocr_done
    report["ocr_failed"] = ocr_skipped
    report["textless_pages"] = [p for p, t in out if len(t.strip()) < TEXTLESS_CHARS]
    doc.close()
    return out


# --------------------------------------------------------------------------
# cleanup
# --------------------------------------------------------------------------

def strip_repeated_lines(pages, threshold: float, report):
    """Drop running headers/footers: short lines that recur near the top or
    bottom of many pages. Only the first and last few lines of each page are
    candidates, so a phrase that legitimately repeats in body text survives."""
    if len(pages) < 3:
        report["repeats_removed"] = []
        return pages

    counts = Counter()
    for _, text in pages:
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        for line in set(lines[:3] + lines[-3:]):
            if 0 < len(line) <= 120 and not line.startswith(("#", "|", "-", "*", "```")):
                counts[line] += 1

    cutoff = max(2, int(len(pages) * threshold))
    repeats = {line for line, n in counts.items() if n >= cutoff}
    report["repeats_removed"] = sorted(repeats)
    if not repeats:
        return pages

    cleaned = []
    for pno, text in pages:
        kept = [l for l in text.split("\n") if l.strip() not in repeats]
        cleaned.append((pno, "\n".join(kept)))
    return cleaned


def strip_page_numbers(pages):
    out = []
    for pno, text in pages:
        lines = text.split("\n")
        # Only the outer edges of the page — a bare "10" mid-page is content
        # (an ordered-list item that lost its marker, usually).
        edges = list(range(min(3, len(lines)))) + list(range(max(0, len(lines) - 3), len(lines)))
        for idx in edges:
            if PAGE_NUM_RE.match(lines[idx]):
                lines[idx] = ""
        out.append((pno, "\n".join(lines)))
    return out


def unwrap_tags(text: str, report) -> str:
    n = 0
    for tag in PRESENTATIONAL_TAGS:
        text, k = re.subn(rf"</?{tag}(?:\s[^>]*)?>", "", text, flags=re.IGNORECASE)
        n += k
    report["tags_unwrapped"] = n
    return text


def dehyphenate(text: str) -> str:
    """'exam-\nple' -> 'example'. Only for a lowercase word split across lines."""
    return re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)


def unwrap_paragraphs(lines):
    """Rejoin lines broken mid-sentence. Off by default: pymupdf4llm already
    emits one line per paragraph, so this only helps PDFs that extract with a
    hard wrap per visual line."""
    out = []
    for line, protected in iter_code_aware(lines):
        stripped = line.strip()
        joinable = (
            out and out[-1].strip() and not protected
            and not stripped.startswith(("#", "-", "*", "+", ">", "|", "```", "~~~"))
            and not re.match(r"^\d+[.)]\s", stripped)
            and not re.match(r"^\s{4,}\S", line)
            and out[-1].rstrip()[-1:] not in ".:;!?"
            and not out[-1].lstrip().startswith(("#", "|"))
        )
        if joinable:
            out[-1] = out[-1].rstrip() + " " + stripped
        else:
            out.append(line)
    return out


def promote_bold_headings(lines, report, enabled: bool):
    """A line that is nothing but short bold text is a heading that lost its
    level during extraction. Opt-in (--bold-headings): the pattern is also a
    legitimate way to emphasise a standalone sentence."""
    candidates, out = 0, []
    for line, protected in iter_code_aware(lines):
        m = re.match(r"^\*\*(.+?)\*\*[:\s]*$", line.strip()) if not protected else None
        if m and len(m.group(1)) <= 80 and not m.group(1).endswith("."):
            candidates += 1
            out.append(f"## {m.group(1).strip()}" if enabled else line)
        else:
            out.append(line)
    report["bold_heading_candidates"] = candidates
    report["bold_headings_promoted"] = candidates if enabled else 0
    return out


def normalise_headings(lines, report, demote_extra_h1=True):
    """Make the heading tree fit the page template.

    1. If the shallowest heading is deeper than H1, promote everything so it
       becomes H1 (PDFs often extract every heading as ### or deeper).
    2. Keep the FIRST H1 as the page title and demote every later H1 to H2,
       leaving H2+ alone — so a PDF whose sections are all H1 ends up with
       TOC-visible `##` sections, which is what the template builds its TOC
       from. A genuinely multi-chapter PDF should use --split h1 instead;
       the report flags that case.

    `demote_extra_h1` is off for --split h1, where each H1 becomes its own
    page and so has to survive as an H1 for the splitter to find.
    """
    levels = []
    for line, protected in iter_code_aware(lines):
        if not protected:
            m = re.match(r"^(#{1,6})\s", line)
            if m:
                levels.append(len(m.group(1)))
    if not levels:
        report["heading_shift"] = 0
        report["h1_demoted"] = 0
        report["heading_levels"] = {}
        return lines

    shift = min(levels) - 1  # >0 means everything was too deep
    seen_h1, demoted, out, counts = False, 0, [], {}
    for line, protected in iter_code_aware(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line) if not protected else None
        if not m:
            out.append(line)
            continue
        level = max(1, len(m.group(1)) - shift)
        if level == 1:
            if seen_h1 and demote_extra_h1:
                level = 2
                demoted += 1
            else:
                seen_h1 = True
        counts[level] = counts.get(level, 0) + 1
        out.append(f"{'#' * level} {clean_heading_text(m.group(2))}")

    report["heading_shift"] = shift
    report["h1_demoted"] = demoted
    report["heading_levels"] = counts
    return out


def drop_headings(lines, names, report):
    """Remove a heading and everything under it, up to the next heading of the
    same or a shallower level. For the in-PDF "Table of Contents" and "Revision
    History" sections, which the sidebar and TOC already replace."""
    if not names:
        report["headings_dropped"] = []
        return lines
    wanted = {n.strip().lower() for n in names}
    out, dropped, cutting, cut_level = [], [], False, 0
    for line, protected in iter_code_aware(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line) if not protected else None
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if cutting and level <= cut_level:
                cutting = False
            if text.lower().rstrip(":").strip() in wanted:
                cutting, cut_level = True, level
                dropped.append(text)
                continue
        if not cutting:
            out.append(line)
    report["headings_dropped"] = dropped
    return out


def collapse_blanks(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def clean(pages, args, report):
    """Page texts -> one cleaned Markdown body."""
    if not args.keep_repeats:
        pages = strip_repeated_lines(pages, args.repeat_threshold, report)
    else:
        report["repeats_removed"] = []
    pages = strip_page_numbers(pages)

    text = "\n\n".join(t for _, t in pages)
    # pymupdf4llm marks page breaks with a horizontal rule; it renders as a
    # <hr> every page, which looks nothing like the hand-authored pages.
    text = re.sub(r"^\s*-{3,}\s*$", "", text, flags=re.MULTILINE)
    if not args.keep_tags:
        text = unwrap_tags(text, report)
    else:
        report["tags_unwrapped"] = 0
    text = dehyphenate(text)

    lines = [l.rstrip() for l in text.split("\n")]
    if args.unwrap:
        lines = unwrap_paragraphs(lines)
    lines = promote_bold_headings(lines, report, args.bold_headings)
    lines = normalise_headings(lines, report, demote_extra_h1=args.split != "h1")
    # After normalisation, so --drop-heading matches the levels you see in the
    # output rather than the PDF's original ones.
    lines = drop_headings(lines, args.drop_heading, report)
    return collapse_blanks("\n".join(lines))


# --------------------------------------------------------------------------
# assembling documents
# --------------------------------------------------------------------------

def take_title(body: str):
    """Pull a leading '# Title' off the body, returning (title, rest)."""
    lines = body.lstrip("\n").split("\n")
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip(), "\n".join(lines[1:]).lstrip("\n")
    return None, body


def compose(title: str, sub: str, body: str) -> str:
    """Emit the shape md_to_page.py parses: H1, optional subtitle, body."""
    head = f"# {title}\n\n"
    if sub:
        head += " ".join(sub.split()) + "\n\n"
    return head + body.lstrip("\n")


def split_sections(body: str, level: int):
    """Split on headings of `level` -> [(heading, section_body)]. Content before
    the first such heading is returned with heading None."""
    marker = "#" * level + " "
    sections, current, head = [], [], None
    for line, protected in iter_code_aware(body.split("\n")):
        if not protected and line.startswith(marker):
            if head is not None or any(l.strip() for l in current):
                sections.append((head, "\n".join(current)))
            head, current = line[len(marker):].strip(), []
        else:
            current.append(line)
    if head is not None or any(l.strip() for l in current):
        sections.append((head, "\n".join(current)))
    return sections


def shift_headings(body: str, up: int) -> str:
    """Promote every heading in a split-out section by `up` levels.

    Splitting on `##` turns that heading into the page's `#`, so its children —
    extracted as `###` — have to become `##` or the page's table of contents,
    which is built from `h2` only, comes out empty and the right sidebar hides
    itself entirely.
    """
    if up <= 0:
        return body
    out = []
    for line, protected in iter_code_aware(body.split("\n")):
        m = re.match(r"^(#{2,6})\s+(.*)$", line) if not protected else None
        if m:
            line = f"{'#' * max(2, len(m.group(1)) - up)} {m.group(2).strip()}"
        out.append(line)
    return "\n".join(out)


def unique_slug(base: str, used: set) -> str:
    slug, n = base, 2
    while slug in used:
        slug, n = f"{base}-{n}", n + 1
    used.add(slug)
    return slug


def write_documents(body: str, args, report):
    """Write one or many .md files. Returns [(path, slug, title)]."""
    first_h1 = take_title(body)[0]
    doc_title = args.title or first_h1 or report.get("pdf_title") or Path(args.pdf).stem

    if args.split == "none":
        _, rest = take_title(body)
        out = Path(args.out) if args.out else Path(args.out_dir) / f"{slugify(doc_title)}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(compose(doc_title, args.sub, rest), encoding="utf-8")
        return [(out, out.stem + ".html", doc_title)]

    if args.split == "h1":
        # Every H1 survived normalisation, so each one is a page — including
        # the first, which must NOT be stripped off as a document title.
        level, sections = 1, split_sections(body, 1)
    else:
        # The document H1 becomes nothing but a title here: strip it, or it
        # leaks into the body of whichever section it precedes.
        level, sections = 2, split_sections(take_title(body)[1], 2)

    if len([s for s in sections if s[0] is not None]) < 2:
        sys.exit(f"error: --split {args.split} found fewer than 2 '{'#' * level}' headings.\n"
                 f"       Heading levels present: {report.get('heading_levels')}\n"
                 f"       Try --split {'h2' if level == 1 else 'h1'}, or drop --split.")

    # A preamble before the first section heading becomes its own page if it is
    # substantial, and otherwise is folded into the first section.
    if sections and sections[0][0] is None:
        preamble = sections.pop(0)[1]
        if len(preamble.strip()) >= args.preamble_min:
            sections.insert(0, (doc_title, preamble))
        elif preamble.strip():
            sections[0] = (sections[0][0], preamble.rstrip() + "\n\n" + sections[0][1].lstrip("\n"))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    used, written = set(), []
    for heading, section in sections:
        slug = unique_slug(slugify(heading), used)
        path = out_dir / f"{slug}.md"
        path.write_text(compose(heading, None, shift_headings(section, level - 1)),
                        encoding="utf-8")
        written.append((path, f"{slug}.html", heading))

    report["split_sections"] = len(written)
    return written


IMAGE_REF_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*/)?([^)/]+\.(?:png|jpe?g|webp))\)")


def split_header_tables(text: str) -> int:
    """Count tables whose header text wrapped into the first body row.

    A PDF column header like "Technology Services" laid out over two lines
    extracts as `|Technolog|` in the header and `|y Services|` in the first body
    row, which renders as a table with a truncated header and a junk first row.
    Worth naming precisely, because it is invisible unless you read the table.
    """
    found, lines = 0, text.split("\n")
    for i, line in enumerate(lines):
        if not re.match(r"^\|[\s\-:|]+\|$", line.strip()):
            continue  # not a header separator row
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if nxt.startswith("|") and nxt.split("|")[1].strip() == "":
            found += 1
    return found


def rewrite_image_paths(docs, args, report):
    """Rename the extracted images and point the Markdown at them.

    Two things need fixing in what pymupdf4llm emits:

    * The ref holds the path the image was written to. The generated HTML lives
      in the project dir while the Markdown lives in `_src/`, so the ref has to
      be relative to the PAGE, not to the Markdown file — hence --image-href.
    * The filename is derived from the PDF's own name, which is usually long and
      space-ridden ("HPE_sd0000..._v8.1.0_-1-.pdf-0020-22.png"). The library
      takes a `filename` prefix but ignores it for an already-open Document, so
      the rename happens here instead.
    """
    if not args.images:
        return
    href = args.image_href.rstrip("/") + "/" if args.image_href else ""
    image_dir = Path(report["image_dir"])
    prefix = args.image_prefix or slugify(Path(args.pdf).stem)

    # Pass 1: collect every referenced image and choose its new name.
    renames, used = {}, set()
    for path, _, _ in docs:
        for m in IMAGE_REF_RE.finditer(path.read_text(encoding="utf-8")):
            name = m.group(3)
            if name in renames:
                continue
            page = re.search(r"-(\d{3,4})-(\d{1,3})\.", name)
            stem = f"{prefix}-p{int(page.group(1)):03d}-{int(page.group(2)):02d}" if page \
                else f"{prefix}-{len(renames) + 1:03d}"
            new = f"{unique_slug(stem, used)}{Path(name).suffix}"
            renames[name] = new

    for old, new in renames.items():
        src = image_dir / old
        if src.is_file() and old != new:
            src.replace(image_dir / new)

    def fix(m):
        alt, name = m.group(1), renames.get(m.group(3), m.group(3))
        if not alt:
            # An empty alt on a content figure is an accessibility defect, and
            # the PDF has no caption to borrow. A placeholder naming the source
            # page at least tells the reviewer what needs describing.
            page = re.search(r"-p(\d+)-", name)
            alt = f"Figure from PDF page {int(page.group(1))}" if page else "Figure"
        return f"![{alt}]({href}{name})"

    total = 0
    for path, _, _ in docs:
        new_text, n = IMAGE_REF_RE.subn(fix, path.read_text(encoding="utf-8"))
        if n:
            path.write_text(new_text, encoding="utf-8")
        total += n
    report["image_refs"] = total
    report["image_files"] = len(renames)


# --------------------------------------------------------------------------
# nav wiring
# --------------------------------------------------------------------------

def wire_config(docs, args, report):
    entries = [{"slug": slug, "title": title,
                **({"section": args.section} if args.section else {})}
               for _, slug, title in docs]
    report["nav_entries"] = entries

    if not args.config:
        return
    config_path = Path(args.config)
    if not config_path.is_file():
        sys.exit(f"error: no config at {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    have = {e["slug"] for e in config.get("nav", [])}
    new = [e for e in entries if e["slug"] not in have]
    report["nav_existing"] = [e["slug"] for e in entries if e["slug"] in have]
    report["nav_new"] = [e["slug"] for e in new]

    if args.update_config and new:
        config.setdefault("nav", []).extend(new)
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        report["config_updated"] = str(config_path)


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def print_report(docs, args, report):
    print(f"\n=== {Path(args.pdf).name} -> {len(docs)} Markdown file"
          f"{'' if len(docs) == 1 else 's'} ===")
    for path, slug, title in docs:
        print(f"  wrote {path}  ({slug}: {title})")

    print(f"\n  source: {report['pages_used']}/{report['pdf_pages']} pages"
          f"  (pymupdf4llm {report['engine']} engine)")
    levels = report.get("heading_levels") or {}
    print("  headings: " + (", ".join(f"h{k}×{v}" for k, v in sorted(levels.items())) or "none"))

    notes = []
    # The on-page TOC is built from h2 only, so a page with none renders with
    # the right-hand sidebar hidden. Checked per output file, after splitting.
    no_toc = [p.name for p, _, _ in docs
              if not re.search(r"(?m)^## \S", p.read_text(encoding="utf-8"))]
    if no_toc:
        notes.append(f"No `##` headings in {len(no_toc)} file(s) ({', '.join(no_toc[:4])}"
                     f"{', …' if len(no_toc) > 4 else ''}) — those pages render with an empty "
                     "on-page TOC and a hidden right sidebar. Promote real section headings "
                     "to `##`, or split at a shallower level.")
    if report.get("h1_demoted"):
        notes.append(f"{report['h1_demoted']} extra `#` heading(s) demoted to `##`. If the PDF is "
                     "really several chapters, rerun with --split h1 for one page each.")
    if report.get("heading_shift"):
        notes.append(f"Every heading was promoted by {report['heading_shift']} level(s) — the "
                     "PDF's shallowest heading was deeper than `#`.")
    if report.get("repeats_removed"):
        notes.append("Removed as running header/footer: "
                     + "; ".join(f'"{l}"' for l in report["repeats_removed"][:5]))
    # A split can land a heading that had no content under it, which publishes
    # as a title and nothing else — and still takes a nav slot on every page.
    thin = [p.name for p, _, _ in docs
            if len(take_title(p.read_text(encoding="utf-8"))[1].strip()) < 200]
    if thin:
        notes.append(f"Almost no body text in {', '.join(thin)} — delete those files and their "
                     "nav[] entries, or fold them into a neighbouring page.")

    split_hdrs = {p.name: n for p, _, _ in docs
                  if (n := split_header_tables(p.read_text(encoding="utf-8")))}
    if split_hdrs:
        notes.append("Table header text wrapped into the first body row in "
                     + ", ".join(f"{name} ({n} table{'' if n == 1 else 's'})"
                                 for name, n in split_hdrs.items())
                     + " — merge that row back into the header by hand.")
    if report.get("headings_dropped"):
        notes.append("Dropped sections: " + "; ".join(f'"{h}"' for h in report["headings_dropped"]))
    for name in args.drop_heading:
        if name.strip().lower() not in {h.lower() for h in report.get("headings_dropped") or []}:
            notes.append(f'--drop-heading "{name}" matched nothing — check the exact heading text.')
    if re.search(r"(?im)^#{1,6}\s+(table of contents|contents)\s*$", "\n".join(
            p.read_text(encoding="utf-8") for p, _, _ in docs)):
        notes.append("The PDF's own table of contents survived — the sidebar and right-hand TOC "
                     'already do that job. Drop it with --drop-heading "Table of Contents".')
    if report.get("textless_pages"):
        notes.append(f"Pages with no text extracted: {report['textless_pages']} — scanned or "
                     "image-only. Use --ocr force, or transcribe them by hand.")
    if report.get("ocr_pages"):
        notes.append(f"OCR'd pages: {report['ocr_pages']} — OCR output is flat text with no "
                     "headings or lists; check it closely.")
    for pno, err in report.get("ocr_failed") or []:
        notes.append(f"OCR failed on page {pno}: {err}")
    if report.get("bold_heading_candidates") and not args.bold_headings:
        notes.append(f"{report['bold_heading_candidates']} bold-only line(s) look like headings "
                     "that lost their level — rerun with --bold-headings to convert them.")
    if report.get("tags_unwrapped"):
        notes.append(f"Stripped {report['tags_unwrapped']} presentational tag(s) "
                     f"({', '.join('<%s>' % t for t in PRESENTATIONAL_TAGS)}).")
    if report.get("image_refs") is not None:
        notes.append(f"{report['image_files']} image(s) in {report.get('image_dir')}, "
                     f"{report['image_refs']} reference(s) pointing at '{args.image_href}'. "
                     "That directory must sit next to the generated .html, NOT in _src/ — "
                     "and the alt text is a placeholder, so write a real description.")
    for flag in report.get("ignored_flags") or []:
        notes.append(f"IGNORED on the {report['engine']} engine: {flag}. "
                     "Rerun with --engine legacy if you need it.")

    if notes:
        print("\n  NOTES")
        for n in notes:
            print(f"    - {n}")

    print("\n  REVIEW BEFORE BUILDING — extraction loses things silently:")
    print("    - bullets and numbered items that lost their marker (now plain paragraphs)")
    print("    - headings that extracted as body text, and body text promoted to headings")
    print("    - tables: check every one rendered as a Markdown table, not as runs of text")
    print("    - two-column or sidebar layouts, where reading order interleaves")
    print("    - code blocks: wrap them in ``` fences, they extract as plain paragraphs")

    if report.get("nav_entries"):
        print("\n  nav[] entries for docs.config.json:")
        for e in report["nav_entries"]:
            print("    " + json.dumps(e, ensure_ascii=False) + ",")
        if report.get("config_updated"):
            print(f"\n  appended {len(report['nav_new'])} new entr"
                  f"{'y' if len(report['nav_new']) == 1 else 'ies'} to {report['config_updated']}")
            if report.get("nav_existing"):
                print(f"  already present, left alone: {report['nav_existing']}")
        elif args.config:
            print(f"\n  {args.config} NOT modified (pass --update-config to append the "
                  f"{len(report.get('nav_new') or [])} new entry/entries)")

    print("\n  Next: render the pages, then validate:")
    print("    python3 build_project.py --project <project>")
    print("    python3 validate_pages.py --project <project>")


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", required=True, help="Source PDF")
    ap.add_argument("--out", help="Output .md path (single-document mode)")
    ap.add_argument("--out-dir", help="Output directory (required for --split, e.g. .../_src)")
    ap.add_argument("--split", choices=["none", "h1", "h2"], default="none",
                    help="Split into one .md per heading of this level (default: none)")
    ap.add_argument("--pages", help="1-based page range to convert, e.g. '1-12,15'")
    ap.add_argument("--title", help="Override the page H1 (default: first heading, else PDF title)")
    ap.add_argument("--sub", help="Subtitle line rendered as .page-sub (single-document mode)")

    ap.add_argument("--margin-top", type=float, default=0,
                    help="Points to crop off the top of every page, to drop a running header")
    ap.add_argument("--margin-bottom", type=float, default=0,
                    help="Points to crop off the bottom of every page, to drop a running footer")
    ap.add_argument("--repeat-threshold", type=float, default=0.4,
                    help="Drop an edge line recurring on this fraction of pages (default: 0.4)")
    ap.add_argument("--keep-repeats", action="store_true",
                    help="Keep repeated header/footer lines")
    ap.add_argument("--keep-tags", action="store_true",
                    help="Keep <u>/<span>/<font> tags instead of unwrapping them")
    ap.add_argument("--unwrap", action="store_true",
                    help="Rejoin lines broken mid-sentence (only needed for hard-wrapped PDFs)")
    ap.add_argument("--bold-headings", action="store_true",
                    help="Convert lines that are only short bold text into `##` headings")
    ap.add_argument("--drop-heading", action="append", default=[], metavar="TITLE",
                    help="Drop this heading and its content (repeatable). Use for a PDF's own "
                         "'Table of Contents' or 'Revision History', which the sidebar replaces")
    ap.add_argument("--table-strategy", default="lines_strict",
                    choices=["lines_strict", "lines", "text", "explicit"],
                    help="Table detection, --engine legacy only: 'lines_strict' needs ruled "
                         "tables, 'text' guesses from alignment (default: lines_strict)")
    ap.add_argument("--engine", choices=["auto", "layout", "legacy"], default="auto",
                    help="pymupdf4llm back end. 'layout' reads structure better and OCRs on its "
                         "own; 'legacy' is the older pymupdf_rag path, and the only one that "
                         "honours --margin-top/--margin-bottom and --table-strategy "
                         "(default: auto, whichever pymupdf4llm chose at import)")
    ap.add_argument("--preamble-min", type=int, default=400,
                    help="In --split mode, keep pre-heading content as its own page only if it "
                         "is at least this many characters (default: 400)")

    ap.add_argument("--images", action="store_true",
                    help="Extract images and reference them (needs --image-dir)")
    ap.add_argument("--image-dir",
                    help="Where to write images. Must be reachable from the generated .html, "
                         "so use <project>/assets — never _src/")
    ap.add_argument("--image-prefix",
                    help="Filename prefix for extracted images (default: slug of the PDF name)")
    ap.add_argument("--image-href", default="./assets",
                    help="Path prefix used in the Markdown image refs, relative to the generated "
                         ".html (default: ./assets)")
    ap.add_argument("--image-dpi", type=int, default=150, help="Rasterisation DPI (default: 150)")

    ap.add_argument("--ocr", choices=["off", "auto", "force"], default="auto",
                    help="OCR pages with no text layer ('auto'), every page ('force'), or never")
    ap.add_argument("--ocr-lang", default="eng", help="tesseract language (default: eng)")
    ap.add_argument("--ocr-dpi", type=int, default=300, help="OCR rasterisation DPI (default: 300)")

    ap.add_argument("--config", help="docs.config.json to check the generated slugs against")
    ap.add_argument("--update-config", action="store_true",
                    help="Append nav[] entries for new slugs to --config")
    ap.add_argument("--section", help="section label for emitted nav[] entries")
    args = ap.parse_args()

    if not Path(args.pdf).is_file():
        sys.exit(f"error: no such file: {args.pdf}")
    if args.split != "none" and not args.out_dir:
        sys.exit("error: --split needs --out-dir (one file per section is written there)")
    if args.split == "none" and not (args.out or args.out_dir):
        sys.exit("error: give --out (or --out-dir to name the file from the PDF title)")
    if args.update_config and not args.config:
        sys.exit("error: --update-config needs --config")
    if args.images and not args.image_dir:
        # Defaulting this to the Markdown's own folder would write images into
        # _src/, where the generated pages cannot reach them.
        sys.exit("error: --images needs --image-dir. The images must land next to the generated "
                 ".html, not beside the Markdown in _src/ — e.g.\n"
                 "         --image-dir _deploy/docs/<project>/assets --image-href ./assets")

    if args.engine != "auto":
        if not hasattr(pymupdf4llm, "use_layout"):
            sys.exit(f"error: this pymupdf4llm ({getattr(pymupdf4llm, 'version', '?')}) has no "
                     f"engine switch — drop --engine")
        try:
            pymupdf4llm.use_layout(args.engine == "layout")
        except ImportError:
            sys.exit("error: --engine layout needs pymupdf.layout, which is not installed")

    report = {}
    pages = extract_pages(args, report)
    body = clean(pages, args, report)
    docs = write_documents(body, args, report)
    rewrite_image_paths(docs, args, report)
    wire_config(docs, args, report)
    print_report(docs, args, report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
