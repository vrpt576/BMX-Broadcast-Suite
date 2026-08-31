"""Renders the in-app manual (/manual) from the project's own docs/*.md
files -- see docs/README.md's own index for the source list this mirrors.

Deliberately not a general-purpose Markdown library: BBS's docs use a
small, consistent subset (headers, paragraphs, bold/italic, inline code,
fenced code blocks, links, unordered/ordered lists, pipe tables,
horizontal rules, blockquotes) and pulling in a real dependency would add
a new entry to the offline, hash-locked wheel pipeline for something this
project's own docs corpus doesn't need. See docs/manual-authoring.md for
what this renderer does and does not support, and the module docstring
for TOPICS below for how docs/*.md map to manual sections.

Rendered once at BBS startup (get_manual() is lru_cache'd) and reused for
every request -- there is no per-request Markdown parsing cost, and no
network fetch: every topic's source .md file ships inside the MSI
payload (see scripts/build-windows-installer.ps1, which now copies
`docs` alongside connector/database/themes/etc.) and is read from disk
once, relative to APPLICATION_ROOT so this works identically from an
installed MSI and a source checkout.
"""

from __future__ import annotations

import html as html_module
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# (slug, title) for every topic this manual includes, in reading order
# within its section. slug matches the source file's stem exactly
# (docs/{slug}.md) so cross-doc Markdown links (e.g. "(setup-wizard.md)")
# can be rewritten to "/manual/{slug}" mechanically -- see _rewrite_links.
#
# Deliberately excludes docs/architecture.md, docs/gold-cup-full-program-
# fixture.md, and docs/racemanager-round-model.md: contributor/internal
# design docs, not operator-facing. docs/README.md isn't included either
# -- its job (an index into the docs) is what this manual's own landing
# page now does in-app.
SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Quick start", [
        ("first-run", "First Run Guide"),
    ]),
    ("Installation", [
        ("installation-windows", "Windows Installation"),
        ("installation-linux", "Linux Installation"),
        ("wizard-installer-windows", "Windows MSI Installer"),
        ("windows-installer-security", "Windows Installer Security"),
        ("upgrading", "Upgrading Between Versions"),
    ]),
    ("Setting up RaceManager access", [
        ("setup-wizard", "The Setup Wizard"),
        ("racemanager-pc-setup", "Prepare the RaceManager PC"),
    ]),
    ("Sqorz live timing", [
        ("sqorz-live-timing", "Sqorz Live Timing"),
        ("sqorz-on-site-runbook", "Sqorz On-Site Runbook"),
    ]),
    ("User guide", [
        ("browser-sources", "Browser Source Reference"),
        ("obs-setup", "OBS Setup Guide"),
        ("keyboard-shortcuts", "Race Director Keyboard Shortcuts"),
        ("themes", "Theme Customization"),
        ("results-roll", "Results Roll"),
        ("race-program-export", "Race-Program Structure Export"),
        ("race-slots", "Race Slots and Combined Motos"),
        ("phase-classification", "Program Segments and Scoring Classification"),
    ]),
    ("System administration", [
        ("configuration", "Track Configuration Guide"),
        ("service-windows", "Windows Service and Tray"),
        ("service-linux", "Linux Background Service and Tray Icon"),
        ("backup-and-restore", "Backup and Restore"),
    ]),
    ("Troubleshooting / FAQ", [
        ("troubleshooting", "Troubleshooting"),
        ("faq", "Frequently Asked Questions"),
    ]),
    ("Best practices for race day", [
        ("race-day-best-practices", "Race Day Best Practices"),
    ]),
]

# Slugs whose content is authored directly here rather than mirrored from
# docs/*.md -- a real gap in the existing docs, not a duplicate of one.
# Kept short and out of the build's tracked-docs check on purpose: this
# is manual-only content, not a source-of-truth doc a contributor would
# expect to find and edit as docs/race-day-best-practices.md.
_AUTHORED_PAGES: dict[str, str] = {
    "race-day-best-practices": """# Race Day Best Practices

A short, practical checklist -- not a replacement for the rest of the manual.

## Before racing starts

- Open [Diagnostics](/diagnostics) and resolve every red check.
- Confirm the correct event is selected, not last week's leftover event.
- Open every overlay you plan to use (`/overlay/current`, `/overlay/lineup`,
  `/overlay/results`, `/overlay/break`) in OBS and confirm each one is showing
  real data, not the bundled demo data.
- If your track uses Sqorz, leave [Sqorz status](/sqorz-status) open on a
  second monitor throughout the event -- it's meant to be watched, not
  checked once.
- Compare at least one class's Director view against the official
  RaceManager report before going live, so a labeling surprise is caught
  before it's on air, not during a broadcast.

## During racing

- Keep [Diagnostics](/diagnostics) and `/logs` open somewhere you'll notice
  them. A RaceManager connection drop shows there first, not as a silent
  blank overlay.
- Use the Director's Next/Previous controls rather than manually re-selecting
  a moto after every race -- they're built to move correctly through
  qualifiers, finals, and any track-specific ordering quirks, which manual
  re-selection can get wrong.
- If a graphic looks wrong, check the Director's own current selection
  first (moto, round, class) before assuming BBS is broken -- most "wrong
  graphic" reports turn out to be a moto that was moved on in RaceManager
  without a matching move in the Director.

## If something goes wrong mid-event

- Don't restart the BBS service as a first response -- it drops the current
  WebSocket connections to every open overlay, and OBS Browser Sources
  reconnect but lose their last-known-good state until the next update.
  Check [Diagnostics](/diagnostics) and [Troubleshooting](/manual/troubleshooting)
  first.
- If RaceManager itself becomes unreachable, BBS's overlays hold their
  last-known-good lineup rather than going blank -- you likely have more
  time than it feels like to fix the underlying connection.
- Screenshot or save the log (`/logs`) before restarting anything, if you'll
  want to report the issue afterward -- state that only exists in memory is
  gone the moment the service restarts.

## After racing

- If you hit anything confusing or wrong, note it (with a screenshot and the
  moto/class involved) while it's fresh -- see
  [Troubleshooting / FAQ](/manual/troubleshooting) for what to capture.
""",
}


def _slug_titles() -> dict[str, str]:
    return {slug: title for _section, topics in SECTIONS for slug, title in topics}


_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MD_LINK_TARGET = re.compile(r"^(?:\.\./|\./)*(?:docs/)?([a-zA-Z0-9_-]+)\.md(#.*)?$")


def _rewrite_link_target(target: str) -> str:
    """A relative Markdown link to another doc becomes an in-app manual
    link if that doc is part of the manual; a relative link to something
    outside the manual (../CLAUDE.md, an image, etc.) becomes a link to
    that file on GitHub instead of a dead relative path -- this page is
    served from an installed app, not from a checked-out repo, so a bare
    relative path resolves to nothing. An already-absolute URL (http/https)
    passes through untouched."""
    if target.startswith(("http://", "https://", "mailto:")):
        return target
    match = _MD_LINK_TARGET.match(target)
    if match:
        slug, fragment = match.group(1), match.group(2) or ""
        if slug in _slug_titles():
            return f"/manual/{slug}{fragment}"
    return f"https://github.com/vrpt576/BMX-Broadcast-Suite/blob/main/docs/{target}"


def _render_inline(text: str) -> str:
    text = html_module.escape(text, quote=False)

    def link_sub(m: re.Match) -> str:
        label, target = m.group(1), m.group(2)
        return f'<a href="{_rewrite_link_target(target)}">{label}</a>'

    text = _LINK.sub(link_sub, text)
    text = _INLINE_CODE.sub(r"<code>\1</code>", text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    return text


def _render_table(lines: list[str]) -> str:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    header, _separator, *body = rows
    out = ["<table>", "<thead><tr>"]
    out += [f"<th>{_render_inline(cell)}</th>" for cell in header]
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{_render_inline(cell)}</td>" for cell in row) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def render_markdown(source: str) -> str:
    """Converts one doc's Markdown source to an HTML fragment (no
    <html>/<body> wrapper -- callers embed this in the manual's shared
    page shell). Block-level: headers, fenced code, pipe tables,
    unordered/ordered lists, blockquotes, horizontal rules, paragraphs.
    Inline: bold, italic, inline code, links (rewritten -- see
    _rewrite_link_target)."""
    lines = source.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        if line.startswith("```"):
            fence_lang = line[3:].strip()
            body: list[str] = []
            i += 1
            while i < n and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            cls = f' class="language-{fence_lang}"' if fence_lang else ""
            code = html_module.escape("\n".join(body), quote=False)
            out.append(f"<pre><code{cls}>{code}</code></pre>")
            continue

        header_match = re.match(r"^(#{1,4})\s+(.*)$", line)
        if header_match:
            level = len(header_match.group(1))
            out.append(f"<h{level}>{_render_inline(header_match.group(2))}</h{level}>")
            i += 1
            continue

        if re.match(r"^-{3,}\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        if line.strip().startswith("|"):
            table_lines = []
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            if len(table_lines) >= 2:
                out.append(_render_table(table_lines))
                continue
            i -= len(table_lines)  # not really a table; fall through
            table_lines = []

        if re.match(r"^>\s?", line):
            quote_lines = []
            while i < n and re.match(r"^>\s?", lines[i]):
                quote_lines.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{_render_inline(' '.join(quote_lines))}</blockquote>")
            continue

        list_match = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if list_match:
            ordered = list_match.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items = []
            while i < n:
                m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if not m:
                    break
                item_text = m.group(3)
                i += 1
                # Fold any indented continuation lines into the same item.
                while i < n and lines[i].strip() and lines[i].startswith("  "):
                    item_text += " " + lines[i].strip()
                    i += 1
                items.append(f"<li>{_render_inline(item_text)}</li>")
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue

        if not line.strip():
            i += 1
            continue

        paragraph_lines = [line]
        i += 1
        while i < n and lines[i].strip() and not re.match(
            r"^(#{1,4}\s|```|-{3,}\s*$|\||>|\s*([-*]|\d+\.)\s)", lines[i]
        ):
            paragraph_lines.append(lines[i])
            i += 1
        out.append(f"<p>{_render_inline(' '.join(paragraph_lines))}</p>")

    return "\n".join(out)


@dataclass(frozen=True)
class ManualTopic:
    slug: str
    title: str
    section: str
    html: str
    search_text: str


@dataclass(frozen=True)
class Manual:
    sections: list[tuple[str, list[tuple[str, str]]]]
    topics: dict[str, ManualTopic]
    search_index: list[dict[str, str]]


def _plain_text(html_fragment: str) -> str:
    return re.sub(r"<[^>]+>", " ", html_fragment)


def _load_docs_root(application_root: Path) -> Path:
    installed = application_root / "docs"
    if installed.is_dir():
        return installed
    return application_root / "docs"


@lru_cache
def get_manual(application_root: Path) -> Manual:
    docs_root = _load_docs_root(application_root)
    topics: dict[str, ManualTopic] = {}
    for section, entries in SECTIONS:
        for slug, title in entries:
            if slug in _AUTHORED_PAGES:
                source = _AUTHORED_PAGES[slug]
            else:
                source_path = docs_root / f"{slug}.md"
                source = source_path.read_text(encoding="utf-8") if source_path.exists() else (
                    f"# {title}\n\nThis topic is not available in this build."
                )
            rendered = render_markdown(source)
            topics[slug] = ManualTopic(
                slug=slug, title=title, section=section, html=rendered,
                search_text=_plain_text(rendered).lower(),
            )
    search_index = [
        {"slug": t.slug, "title": t.title, "section": t.section}
        for t in topics.values()
    ]
    return Manual(sections=SECTIONS, topics=topics, search_index=search_index)


def search(manual: Manual, query: str, *, limit: int = 8) -> list[dict[str, str]]:
    """Cheap substring search over each topic's already-rendered plain
    text -- no index structure beyond what get_manual() already built,
    no ranking beyond "title match beats body match". Good enough for a
    few dozen short pages; not meant to scale past that."""
    needle = query.strip().lower()
    if not needle:
        return []
    title_hits: list[dict[str, str]] = []
    body_hits: list[dict[str, str]] = []
    for topic in manual.topics.values():
        entry = {"slug": topic.slug, "title": topic.title, "section": topic.section}
        if needle in topic.title.lower():
            title_hits.append(entry)
        elif needle in topic.search_text:
            body_hits.append(entry)
    return (title_hits + body_hits)[:limit]
