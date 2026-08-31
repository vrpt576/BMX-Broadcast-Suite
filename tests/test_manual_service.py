"""The in-app manual's rendering: a small, purpose-built Markdown-to-HTML
converter scoped to what docs/*.md actually use, and the docs-to-section
mapping that builds the manual's navigation and search index.
"""

from __future__ import annotations

import re

import pytest

from connector.config import APPLICATION_ROOT
from connector.services import manual_service as svc


# ---------------------------------------------------------------------------
# render_markdown -- block and inline constructs actually used in docs/*.md
# ---------------------------------------------------------------------------


def test_renders_headers_at_every_level_used() -> None:
    html = svc.render_markdown("# One\n## Two\n### Three")
    assert "<h1>One</h1>" in html
    assert "<h2>Two</h2>" in html
    assert "<h3>Three</h3>" in html


def test_renders_a_paragraph() -> None:
    html = svc.render_markdown("Just a sentence.")
    assert "<p>Just a sentence.</p>" in html


def test_renders_bold_and_italic_and_inline_code() -> None:
    html = svc.render_markdown("**bold** and *italic* and `code`")
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html
    assert "<code>code</code>" in html


def test_renders_a_fenced_code_block_with_language_class() -> None:
    html = svc.render_markdown("```powershell\nGet-Service\n```")
    assert '<pre><code class="language-powershell">Get-Service</code></pre>' in html


def test_fenced_code_block_content_is_not_interpreted_as_markdown() -> None:
    html = svc.render_markdown("```\n**not bold** [not a link](x)\n```")
    assert "<strong>" not in html
    assert "<a href" not in html
    assert "**not bold**" in html


def test_renders_an_unordered_list() -> None:
    html = svc.render_markdown("- one\n- two\n- three")
    assert html.count("<li>") == 3
    assert html.startswith("<ul>")


def test_renders_an_ordered_list() -> None:
    html = svc.render_markdown("1. first\n2. second")
    assert "<ol>" in html
    assert html.count("<li>") == 2


def test_renders_a_pipe_table() -> None:
    html = svc.render_markdown("| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |")
    assert "<table>" in html
    assert "<th>A</th>" in html
    assert "<th>B</th>" in html
    assert "<td>1</td>" in html
    assert "<td>4</td>" in html


def test_renders_a_blockquote() -> None:
    html = svc.render_markdown("> a quoted line")
    assert "<blockquote>a quoted line</blockquote>" in html


def test_renders_a_horizontal_rule() -> None:
    html = svc.render_markdown("above\n\n---\n\nbelow")
    assert "<hr>" in html


def test_escapes_raw_html_in_source_text() -> None:
    """A doc that happens to contain a literal '<' or '&' must not have it
    interpreted as markup -- this is untrusted-shaped input in the sense
    that a future doc edit could contain it by accident, not because
    docs/*.md is adversarial today."""
    html = svc.render_markdown("Use `<script>` tags & other special chars.")
    assert "&lt;script&gt;" in html or "<script>" not in html


# ---------------------------------------------------------------------------
# Link rewriting -- a relative doc-to-doc Markdown link becomes an in-app
# manual link; anything else degrades to a real, working URL rather than a
# dead relative path (this page is served from an installed app, not a
# repo checkout)
# ---------------------------------------------------------------------------


def test_rewrites_a_relative_md_link_to_a_manual_link_when_the_target_is_included() -> None:
    html = svc.render_markdown("[The Setup Wizard](setup-wizard.md)")
    assert '<a href="/manual/setup-wizard">' in html


def test_preserves_a_fragment_on_a_rewritten_link() -> None:
    html = svc.render_markdown("[Jump](setup-wizard.md#step-2)")
    assert '<a href="/manual/setup-wizard#step-2">' in html


def test_leaves_an_absolute_url_untouched() -> None:
    html = svc.render_markdown("[Microsoft](https://example.com/x)")
    assert '<a href="https://example.com/x">' in html


def test_a_relative_link_to_something_outside_the_manual_becomes_a_github_link_not_a_dead_path() -> (
    None
):
    html = svc.render_markdown("[repo docs](../CLAUDE.md)")
    assert "<a href=\"https://github.com/" in html
    assert "CLAUDE.md" in html


# ---------------------------------------------------------------------------
# get_manual -- the section/topic structure and real docs/*.md content
# ---------------------------------------------------------------------------


def test_get_manual_includes_every_section_requested() -> None:
    manual = svc.get_manual(APPLICATION_ROOT)
    section_names = [name for name, _entries in manual.sections]
    for expected in (
        "Quick start",
        "Installation",
        "Setting up RaceManager access",
        "Sqorz live timing",
        "User guide",
        "System administration",
        "Troubleshooting / FAQ",
        "Best practices for race day",
    ):
        assert expected in section_names


def test_get_manual_loads_real_doc_content_not_a_placeholder() -> None:
    manual = svc.get_manual(APPLICATION_ROOT)
    topic = manual.topics["racemanager-pc-setup"]
    assert "not available in this build" not in topic.html
    assert "db_datareader" in topic.html


def test_get_manual_includes_sqorz_only_mode_with_real_content() -> None:
    manual = svc.get_manual(APPLICATION_ROOT)
    topic = manual.topics["sqorz-only-mode"]
    assert "Jump to Most Recent Activity" in topic.html
    assert "Re-check" in topic.html


def test_get_manual_every_topic_has_non_empty_rendered_html() -> None:
    manual = svc.get_manual(APPLICATION_ROOT)
    for slug, topic in manual.topics.items():
        assert topic.html.strip(), f"{slug} rendered empty"


def test_authored_gap_page_renders() -> None:
    manual = svc.get_manual(APPLICATION_ROOT)
    topic = manual.topics["race-day-best-practices"]
    assert "Diagnostics" in topic.html


# ---------------------------------------------------------------------------
# search -- cheap substring search, title matches ranked first
# ---------------------------------------------------------------------------


def test_search_finds_a_title_match() -> None:
    manual = svc.get_manual(APPLICATION_ROOT)
    hits = svc.search(manual, "Sqorz")
    assert any(h["slug"] == "sqorz-live-timing" for h in hits)


def test_search_ranks_title_matches_before_body_matches() -> None:
    manual = svc.get_manual(APPLICATION_ROOT)
    hits = svc.search(manual, "sqorz")
    title_hit_slugs = {h["slug"] for h in hits if "sqorz" in h["title"].lower()}
    first_slugs = {h["slug"] for h in hits[: len(title_hit_slugs)]}
    assert title_hit_slugs <= first_slugs


def test_search_empty_query_returns_nothing() -> None:
    manual = svc.get_manual(APPLICATION_ROOT)
    assert svc.search(manual, "") == []


def test_search_no_match_returns_empty_list_not_an_error() -> None:
    manual = svc.get_manual(APPLICATION_ROOT)
    assert svc.search(manual, "xyzzy-not-a-real-word-anywhere") == []


# ---------------------------------------------------------------------------
# Regression net: every real doc, not just the hand-picked examples above.
# render_markdown() is deliberately scoped to what today's docs/*.md use,
# not general Markdown -- its failure mode for anything outside that scope
# is silent: a future doc uses syntax it doesn't handle, and a track
# operator sees raw asterisks or a bare [text](url) instead of a link. This
# renders every file actually in docs/ (not just the ones curated into
# SECTIONS -- a doc nobody has wired into the manual yet is exactly the
# kind of "written later, never checked" case this exists to catch) and
# asserts nothing markdown-shaped survives into the output outside a code
# block, where literal '*', '`', '|', and '[x](y)' are legitimately just
# code and not a rendering failure.
# ---------------------------------------------------------------------------


def _strip_code_blocks(html: str) -> str:
    """Strips both fenced code blocks and inline code spans -- literal
    '*', '`', '|', or '[x](y)'-shaped text inside either is legitimately
    just code, not a rendering failure. A fenced block's own <code> is
    covered by stripping the whole <pre>...</pre> first, so this doesn't
    double-strip it as "inline"."""
    without_blocks = re.sub(r"<pre>.*?</pre>", "", html, flags=re.S)
    return re.sub(r"<code>.*?</code>", "", without_blocks, flags=re.S)


def _all_doc_files() -> list:
    docs_root = APPLICATION_ROOT / "docs"
    return sorted(docs_root.glob("*.md"))


@pytest.mark.parametrize("doc_path", _all_doc_files(), ids=lambda p: p.name)
def test_every_doc_in_docs_renders_without_leaking_raw_markdown_syntax(doc_path) -> None:
    source = doc_path.read_text(encoding="utf-8")
    html = svc.render_markdown(source)
    prose = _strip_code_blocks(html)

    assert "*" not in prose, f"{doc_path.name}: a '*' survived rendering outside a code block"
    assert "`" not in prose, f"{doc_path.name}: a '`' survived rendering outside a code block"
    assert not re.search(r"^\s*\|.*\|\s*$", prose, re.M), (
        f"{doc_path.name}: a raw '|...|' table line survived rendering"
    )
    assert not re.search(r"\[[^\]]+\]\([^)]+\)", prose), (
        f"{doc_path.name}: a raw [text](url) link survived rendering"
    )


def test_every_doc_renders_at_least_one_heading() -> None:
    """A doc that renders to zero headings almost certainly failed to
    parse at all (wrong line endings, an encoding issue) rather than
    genuinely having no headings -- every doc in this project's docs/
    starts with a top-level title."""
    for doc_path in _all_doc_files():
        html = svc.render_markdown(doc_path.read_text(encoding="utf-8"))
        assert re.search(r"<h1>", html), f"{doc_path.name}: rendered with no <h1> at all"
