"""Validated broadcast-break controls and shared OBS overlay."""

from fastapi import APIRouter, Depends

from connector.dependencies import get_current_moto_service, get_results_roll_service
from connector.models import ActiveGraphic, BreakPreset, CurrentMoto
from connector.services.current_moto_service import CurrentMotoService
from connector.services.results_roll_service import ResultsRollService

router = APIRouter(prefix="/breaks", tags=["broadcast breaks"])

BREAK_GRAPHICS = {
    BreakPreset.ROUND_1: ActiveGraphic.ROUND_1_BREAK,
    BreakPreset.MAIN: ActiveGraphic.MAIN_BREAK,
}


@router.get("/presets", response_model=list[BreakPreset])
def break_presets() -> list[BreakPreset]:
    return list(BREAK_GRAPHICS)


@router.post("/show/{preset}", response_model=CurrentMoto)
def show_break(
    preset: BreakPreset,
    current: CurrentMotoService = Depends(get_current_moto_service),
    results_roll: ResultsRollService = Depends(get_results_roll_service),
) -> CurrentMoto:
    """Pause Results Roll before making one validated break preset active."""
    results_roll.pause_if_active()
    return current.set_graphic(BREAK_GRAPHICS[preset])


def break_overlay() -> str:
    return BREAK_HTML


BREAK_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BBS Broadcast Break</title><style>
:root{--primary:#f3b61f;--primary-text:#101820;--panel:#101820;--panel-alt:#1b2733;--panel-text:#fff;--shadow:rgba(0,0,0,.55);--font-family:Arial,Helvetica,sans-serif;--text-transform:uppercase;font-family:var(--font-family)}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}.frame{position:absolute;inset:5%;display:grid;place-items:center;border:10px solid var(--primary);background:linear-gradient(135deg,var(--panel),var(--panel-alt));color:var(--panel-text);filter:drop-shadow(0 10px 24px var(--shadow))}.accent{position:absolute;left:0;right:0;top:18%;height:12px;background:var(--primary)}.accent.bottom{top:auto;bottom:18%}.label{max-width:90%;text-align:center;font-size:clamp(70px,10vw,180px);line-height:.95;font-weight:950;letter-spacing:.025em;text-transform:var(--text-transform);text-shadow:0 6px 12px var(--shadow)}
</style></head><body><main id="frame" class="frame"><div class="accent"></div><div id="label" class="label">ROUND 1 BREAK</div><div class="accent bottom"></div></main><script>
const params=new URLSearchParams(location.search),preview=['1','true','yes'].includes((params.get('preview')||'').toLowerCase()),previewPreset=(params.get('preset')||'round_1').toLowerCase();let themeName=(params.get('theme')||'').toLowerCase();
const labels={round_1_break:'ROUND 1 BREAK',main_break:'MAIN BREAK'},previewGraphics={round_1:'round_1_break',main:'main_break'};
async function applyTheme(){try{if(!themeName){const cfg=await fetch('/api/configuration/public',{cache:'no-store'});if(cfg.ok)themeName=((await cfg.json()).default_theme||'default').toLowerCase()}if(!themeName)themeName='default';const response=await fetch(`/api/themes/${encodeURIComponent(themeName)}`,{cache:'no-store'});if(!response.ok)return;const theme=await response.json(),root=document.documentElement.style,c=theme.colors||{},t=theme.typography||{},map={primary:'--primary',primary_text:'--primary-text',panel:'--panel',panel_alt:'--panel-alt',panel_text:'--panel-text',shadow:'--shadow'};for(const[key,variable]of Object.entries(map))if(c[key])root.setProperty(variable,c[key]);if(t.font_family)root.setProperty('--font-family',t.font_family);if(t.text_transform)root.setProperty('--text-transform',t.text_transform)}catch(_){}}
function render(state){const active=preview?(previewGraphics[previewPreset]||'round_1_break'):state.active_graphic;document.body.style.visibility=labels[active]?'visible':'hidden';document.querySelector('#label').textContent=labels[active]||''}
async function load(){try{const response=await fetch('/api/current',{cache:'no-store'});if(!response.ok)throw new Error();render(await response.json())}catch(_){if(!preview)document.body.style.visibility='hidden'}}
applyTheme();load();setInterval(load,1000);
</script></body></html>'''
