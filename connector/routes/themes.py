"""Overlay theme discovery API."""

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse

from connector.config import APPLICATION_ROOT, get_settings
from connector.services.theme_service import ThemeNotFoundError, ThemeService, ThemeValidationError

router = APIRouter(prefix="/themes", tags=["themes"])


def get_theme_service() -> ThemeService:
    settings = get_settings()
    return ThemeService(
        settings.theme_dir,
        bundled_root=APPLICATION_ROOT / "themes",
    )


@router.get("")
def list_themes() -> list[dict[str, Any]]:
    return get_theme_service().list()


@router.get("/{slug}")
def get_theme(slug: str) -> dict[str, Any]:
    try:
        return get_theme_service().get(slug)
    except ThemeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Theme not found.") from exc


@router.put("/{slug}")
def save_theme(slug: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"saved": True, "theme": get_theme_service().save(slug, payload)}
    except ThemeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{slug}/reset")
def reset_theme(slug: str) -> dict[str, Any]:
    try:
        return {"saved": True, "theme": get_theme_service().reset(slug)}
    except ThemeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Theme not found.") from exc
    except ThemeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def themes_page() -> HTMLResponse:
    return HTMLResponse(THEMES_HTML)


THEMES_HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BBS Themes</title><style>
:root{font-family:Segoe UI,Arial,sans-serif;background:#0e141b;color:#fff}*{box-sizing:border-box}body{margin:0;padding:28px}.wrap{max-width:1050px;margin:auto}.card{background:#151e28;border:1px solid #293746;border-radius:12px;padding:18px;margin:14px 0}label{display:block;font-size:13px;color:#c4ced9;margin:10px 0 0}input,select{width:100%;margin-top:5px;padding:10px;border-radius:8px;border:1px solid #415064;background:#0d131a;color:#fff}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.actions{display:flex;gap:10px;flex-wrap:wrap}button{margin-top:18px;padding:11px 16px;border:0;border-radius:8px;background:#f3b61f;color:#101820;font-weight:900;cursor:pointer}button.secondary{background:#344454;color:#fff}.muted{color:#aeb9c5}.ok{color:#7ee2aa}.error{color:#ff8b8b}@media(max-width:760px){.grid{grid-template-columns:1fr}}
</style></head><body><main class="wrap"><h1>BBS Theme Manager</h1><p class="muted">Select the active broadcast look, then safely edit the supported colors and typography. Changes apply when overlays next refresh.</p><section class="card"><label>Theme<select id="theme"></select></label><div class="actions"><button id="use">Use this theme</button><button id="reset" class="secondary">Restore default settings</button></div></section><section class="card"><label>Theme name<input id="name" maxlength="80"></label><h2>Colors</h2><div id="colors" class="grid"></div><h2>Typography</h2><div id="typography" class="grid"></div><div class="actions"><button id="save">Save theme</button></div><p id="status" class="muted" role="status"></p></section></main><script>
const token=()=>sessionStorage.getItem('bbs.admin.token')||'';const headers=(extra={})=>{const h=new Headers(extra);if(token())h.set('X-BBS-Admin-Token',token());return h};let current='';
const label=k=>k.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());function status(text,kind='muted'){const el=document.querySelector('#status');el.textContent=text;el.className=kind}
function fields(id,values){const box=document.querySelector('#'+id);box.replaceChildren();for(const [key,value] of Object.entries(values||{})){const labelEl=document.createElement('label');labelEl.textContent=label(key);const input=document.createElement('input');input.dataset.section=id;input.dataset.key=key;input.value=value;labelEl.append(input);box.append(labelEl)}}
async function load(slug){status('Loading…');const r=await fetch('/api/themes/'+encodeURIComponent(slug),{headers:headers(),cache:'no-store'}),d=await r.json();if(!r.ok){status(d.detail||'Theme unavailable','error');return}current=d.slug;document.querySelector('#name').value=d.name;fields('colors',d.colors);fields('typography',d.typography);status('Theme loaded.','ok')}
async function list(){const r=await fetch('/api/themes',{headers:headers(),cache:'no-store'}),themes=await r.json(),select=document.querySelector('#theme');select.replaceChildren();for(const theme of themes){const option=document.createElement('option');option.value=theme.slug;option.textContent=theme.name+' ('+theme.slug+')';select.append(option)}const config=await fetch('/api/configuration',{headers:headers(),cache:'no-store'});const setting=config.ok?await config.json():{};select.value=setting.default_theme||'default';await load(select.value)}
function payload(){const value={name:document.querySelector('#name').value,colors:{},typography:{}};for(const input of document.querySelectorAll('input[data-section]'))value[input.dataset.section][input.dataset.key]=input.value;return value}
async function save(){if(current==='default'){status('Create or select a custom theme before saving. The bundled default is protected.','error');return}const r=await fetch('/api/themes/'+encodeURIComponent(current),{method:'PUT',headers:headers({'Content-Type':'application/json'}),body:JSON.stringify(payload())}),d=await r.json();if(!r.ok){status(d.detail||'Save failed','error');return}status('Theme saved. Overlays will update on their next refresh.','ok')}
async function reset(){if(current==='default'){await load('default');status('Showing the bundled default settings.','ok');return}if(!confirm('Restore every supported setting in this theme to BBS defaults?'))return;const r=await fetch('/api/themes/'+encodeURIComponent(current)+'/reset',{method:'POST',headers:headers()}),d=await r.json();if(!r.ok){status(d.detail||'Restore failed','error');return}await load(current);status('Theme settings restored to defaults.','ok')}
async function use(){const r=await fetch('/api/configuration',{headers:headers(),cache:'no-store'}),base=await r.json();if(!r.ok){status(base.detail||'Configuration unavailable','error');return}base.default_theme=current;const save=await fetch('/api/configuration',{method:'PUT',headers:headers({'Content-Type':'application/json'}),body:JSON.stringify(base)}),d=await save.json();status(save.ok?'Active theme updated.':d.detail||'Could not select theme.',save.ok?'ok':'error')}
document.querySelector('#theme').addEventListener('change',e=>load(e.target.value));document.querySelector('#save').addEventListener('click',save);document.querySelector('#reset').addEventListener('click',reset);document.querySelector('#use').addEventListener('click',use);list().catch(()=>status('Theme manager unavailable.','error'));
</script></body></html>'''
