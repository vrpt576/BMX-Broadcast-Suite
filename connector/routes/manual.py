"""The in-app manual (/manual) -- see connector/services/manual_service.py
for the rendering and docs/*.md-to-section mapping. Exists because anyone
who reaches BBS through a link (a track's own install, not a GitHub
clone) never sees the repository's docs/ folder at all; the
documentation has to live inside the product itself. Fully offline: no
CDN, no external fonts, same rule as the overlays -- everything here is
either inline or served from the same origin.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from connector.config import APPLICATION_ROOT
from connector.services import manual_service

router = APIRouter(tags=["manual"])
# Registered separately in connector/main.py with the API prefix applied
# (app.include_router(manual.api_router, prefix=settings.api_prefix)) --
# `router` above holds the un-prefixed page routes (/manual, /manual/{slug}),
# matching how connector/routes/setup.py's own page route is registered
# outside its API-prefixed router.
api_router = APIRouter(tags=["manual"])


def _esc(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _sidebar_html(active_slug: str | None) -> str:
    manual = manual_service.get_manual(APPLICATION_ROOT)
    parts = ['<nav class="manual-nav">']
    for section, entries in manual.sections:
        parts.append(f'<div class="manual-section-title">{_esc(section)}</div><ul>')
        for slug, title in entries:
            cls = ' class="active"' if slug == active_slug else ""
            parts.append(f'<li{cls}><a href="/manual/{slug}">{_esc(title)}</a></li>')
        parts.append("</ul>")
    parts.append("</nav>")
    return "".join(parts)


_STYLE = """
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#f7f7f7;background:#0e141b}
*{box-sizing:border-box}
body{margin:0}
.manual-layout{display:flex;min-height:100vh}
.manual-nav{width:270px;flex:0 0 270px;background:#0d131a;border-right:1px solid #273444;padding:20px 14px;overflow-y:auto;position:sticky;top:0;height:100vh}
.manual-nav a{display:block}
.manual-section-title{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#7f8ea0;margin:18px 0 6px;padding:0 8px}
.manual-section-title:first-child{margin-top:0}
.manual-nav ul{list-style:none;margin:0;padding:0}
.manual-nav li a{color:#cfd8e3;text-decoration:none;padding:7px 8px;border-radius:7px;font-size:14px}
.manual-nav li a:hover{background:#182230}
.manual-nav li.active a{background:#22364a;color:#f5b821;font-weight:700}
.manual-content{flex:1;padding:32px 40px;max-width:820px}
.manual-content h1{font-size:26px;margin-top:0}
.manual-content h2{font-size:19px;margin-top:32px;border-top:1px solid #22303f;padding-top:20px}
.manual-content h3{font-size:16px}
.manual-content p{line-height:1.65;color:#dce4ec}
.manual-content li{line-height:1.6;color:#dce4ec}
.manual-content a{color:#f5b821}
.manual-content code{background:#151e28;padding:2px 6px;border-radius:5px;font-size:13px}
.manual-content pre{background:#0d131a;border:1px solid #273444;border-radius:10px;padding:14px;overflow-x:auto}
.manual-content pre code{background:none;padding:0}
.manual-content table{border-collapse:collapse;margin:14px 0;width:100%}
.manual-content th,.manual-content td{border:1px solid #273444;padding:8px 10px;text-align:left;font-size:14px}
.manual-content th{background:#151e28}
.manual-content blockquote{border-left:3px solid #f5b821;margin:14px 0;padding:2px 16px;color:#aeb9c5}
.manual-topbar{display:flex;gap:12px;align-items:center;padding:14px 16px;border-bottom:1px solid #273444;position:sticky;top:0;background:#0e141b;z-index:2}
.manual-topbar a.home{color:#f7f7f7;font-weight:800;text-decoration:none}
#manual-search{flex:1;max-width:320px;padding:8px 10px;border-radius:8px;border:1px solid #415064;background:#0d131a;color:#fff}
#manual-search-results{position:absolute;top:52px;left:16px;width:320px;background:#151e28;border:1px solid #273444;border-radius:10px;overflow:hidden;display:none;z-index:3}
#manual-search-results a{display:block;padding:9px 12px;color:#dce4ec;text-decoration:none;font-size:13px;border-bottom:1px solid #1c2733}
#manual-search-results a:last-child{border-bottom:none}
#manual-search-results a:hover{background:#1c2733}
#manual-search-results .muted{color:#7f8ea0;font-size:11px}
@media(max-width:800px){.manual-layout{flex-direction:column}.manual-nav{width:100%;height:auto;position:static}.manual-content{padding:20px}}
"""

_SEARCH_SCRIPT = """
<script>
(function(){
  const input = document.getElementById('manual-search');
  const results = document.getElementById('manual-search-results');
  if(!input) return;
  input.addEventListener('input', async () => {
    const q = input.value.trim();
    if(!q){ results.style.display='none'; return }
    const r = await fetch('/api/manual/search?q=' + encodeURIComponent(q));
    const hits = await r.json();
    if(!hits.length){ results.innerHTML = '<div class="muted" style="padding:10px 12px">No matches.</div>'; results.style.display='block'; return }
    results.innerHTML = hits.map(h => '<a href="/manual/' + h.slug + '">' + h.title + '<div class="muted">' + h.section + '</div></a>').join('');
    results.style.display='block';
  });
  document.addEventListener('click', (e) => { if(!e.target.closest('.manual-topbar')) results.style.display='none' });
})();
</script>
"""


def _page(title: str, active_slug: str | None, content_html: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)} — BBS Manual</title>
<style>{_STYLE}</style></head><body>
<div class="manual-topbar" style="position:relative">
  <a class="home" href="/manual">BBS Manual</a>
  <input id="manual-search" placeholder="Search the manual…" autocomplete="off">
  <div id="manual-search-results"></div>
</div>
<div class="manual-layout">
  {_sidebar_html(active_slug)}
  <main class="manual-content">{content_html}</main>
</div>
{_SEARCH_SCRIPT}
</body></html>"""


@router.get("/manual", response_class=HTMLResponse)
def manual_index() -> HTMLResponse:
    manual = manual_service.get_manual(APPLICATION_ROOT)
    body = ["<h1>BBS Manual</h1>", '<p>Everything for running BBS at a track, in one place -- pick a topic from the left, or search above.</p>']
    for section, entries in manual.sections:
        body.append(f"<h2>{_esc(section)}</h2><ul>")
        for slug, title in entries:
            body.append(f'<li><a href="/manual/{slug}">{_esc(title)}</a></li>')
        body.append("</ul>")
    return HTMLResponse(_page("Manual", None, "".join(body)))


@router.get("/manual/{slug}", response_class=HTMLResponse)
def manual_topic(slug: str) -> HTMLResponse:
    manual = manual_service.get_manual(APPLICATION_ROOT)
    topic = manual.topics.get(slug)
    if topic is None:
        return RedirectResponse("/manual")
    return HTMLResponse(_page(topic.title, slug, topic.html))


@api_router.get("/manual/search")
def manual_search(q: str = Query("")) -> list[dict[str, str]]:
    manual = manual_service.get_manual(APPLICATION_ROOT)
    return manual_service.search(manual, q)
