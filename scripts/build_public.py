#!/usr/bin/env python3
"""Genera la web pública estática (public/index.html) a partir de la app local
(download/zoco-pcc-monitor/index.html), con sustituciones ancladas y verificadas."""
import json
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parents[1]
SRC = BASE / 'download/zoco-pcc-monitor/index.html'
OUT = BASE / 'public/index.html'
DATA_SRC = BASE / 'download/zoco-pcc-monitor/data.json'
DATA_OUT = BASE / 'public/data.json'

html = SRC.read_text(encoding='utf-8')


def rep(old, new, what):
    global html
    n = html.count(old)
    assert n == 1, f'ANCLA {what!r}: {n} apariciones (se esperaba 1)'
    html = html.replace(old, new)
    print(f'ok: {what}')


# Los sellos de tiempo del scraper usan Europe/Madrid y los anteriores sin zona
# se interpretan como UTC (así los genera el runner de GitHub Actions).
rep("const PCC_BASE='https://www.pccomponentes.com/', ZOCO_BASE='https://zococity.es/products/';",
'''function formatMadridDate(value){
  const raw=String(value||'');
  if(!raw) return '—';
  const iso=/(Z|[+-]\\d{2}:?\\d{2})$/i.test(raw)?raw:raw+'Z';
  const date=new Date(iso);
  if(Number.isNaN(date.getTime())) return raw.replace('T',' ');
  const parts=new Intl.DateTimeFormat('es-ES',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(date);
  const fields={};
  for(const part of parts) fields[part.type]=part.value;
  return `${fields.year}-${fields.month}-${fields.day} ${fields.hour}:${fields.minute}:${fields.second}`;
}
const PCC_BASE='https://www.pccomponentes.com/', ZOCO_BASE='https://zococity.es/products/';''', 'hora peninsular con cambio estacional')


# 1) botón que dispara el workflow remoto
rep('''        <button id="btnRefresh">↻ Actualizar precios</button>
        <button id="btnExcel">Descargar Excel</button>
''', '''        <button id="btnRefresh">🚀 Actualizar precios online</button>
''', 'botones online')

rep('''<input type="checkbox" id="skipSearch">''', '''<input type="checkbox" id="skipSearch" checked>''', 'opcion de busqueda remota')

# 2) quitar solo el control local de cancelación
rep('''    <button id="btnCancel" style="display:none">⏹ Parar</button>
''', '', 'boton cancelar')



# 3) explicar la actualización online
b_start = html.index('<div class="warn" id="envBox">')
b_end = html.index('</div>', b_start) + len('</div>')
html = html[:b_start] + '''<div class="warn" id="envBox">
  <b>Actualización online.</b><br>
  El botón ejecuta el scraping en un navegador real de GitHub Actions. Lee los 54 productos,
  publica una nueva instantánea y la web se actualiza al terminar el redespliegue de Vercel.
  La actualización puede tardar varios minutos.
</div>''' + html[b_end:]
print('ok: banner online')

# 4) loadData: leer la instantánea relativa y avisar en modo banner si falla
rep('''async function loadData(){
  try{
    DATA = await api('/api/data');
    render();
  }catch(e){
    if((e.message||'').includes('404')) return; // el banner de entorno lo explica
    showErr('No se pudieron cargar los datos: '+e.message);
  }
}''', '''async function loadData(quiet=false){
  try{
    DATA = await api('./data.json?ts='+Date.now(), {cache:'no-store'});
    render(); hideErr(); return true;
  }catch(e){
    if(!quiet) showErr('No se pudo cargar la instantánea: '+e.message);
    return false;
  }
}''', 'loadData estático')

# 5) detectEnv estático
rep('''async function detectEnv(){
  if(location.protocol==='file:'){ showEnv(); return; }
  try{
    const r=await fetch('/api/status');
    if(!r.ok){ showEnv(); return; }
    const j=await r.json().catch(()=>null);
    if(!j || j.running===undefined) showEnv();
  }catch(e){ showEnv(); }
}''', '''function detectEnv(){
  showEnv();
}''', 'detectEnv')

# 6) subtítulo con letra de copia pública
rep('''  $('meta').textContent = 'Generado: '+ (DATA.generated_at||'—').replace('T',' ') +
    ' · '+p.length+' productos · Zococity vía Shopify JSON · PCComponentes vía fichas oficiales (nodriver + Cloudflare)';''',
    '''  $('meta').textContent = 'Instantánea pública · Generado: '+ formatMadridDate(DATA.generated_at) +
    ' · '+p.length+' productos';''', 'meta')

# 7) iniciar y supervisar el scraping remoto
block_start = html.index('/* ---- progreso ---- */')
block_end = html.index("['q','fCat','fAvail']")
html = html[:block_start] + '''function wait(ms){ return new Promise(resolve=>setTimeout(resolve, ms)); }
function remoteProgress(message, percent){
  $('prog').classList.add('on');
  $('progPhase').textContent = message;
  $('progCount').textContent = 'GitHub Actions';
  $('progFill').style.width = percent+'%';
}
async function waitForPublishedSnapshot(runId, previous, timeoutMs){
  const until = Date.now()+timeoutMs;
  while(Date.now()<until){
    await wait(10000);
    await loadData(true);
    if(DATA && DATA.meta && String(DATA.meta.workflow_run_id||'')===String(runId)) return true;
    if(!runId && DATA && DATA.generated_at && DATA.generated_at!==previous) return true;
    remoteProgress('Scraping terminado; esperando a que Vercel publique los datos...', 90);
  }
  return false;
}
async function followRun(runId, requestedAt, previousSnapshot){
  const until = Date.now()+55*60*1000;
  let id = runId;
  while(Date.now()<until){
    const query = id ? 'run_id='+encodeURIComponent(id) : 'since='+encodeURIComponent(requestedAt);
    const state = await api('/api/refresh?'+query, {cache:'no-store'});
    if(state.run_id) id = state.run_id;
    if(state.status==='completed'){
      if(state.conclusion!=='success') throw new Error('El scraping terminó con estado '+(state.conclusion||'desconocido')+'. Revisa '+(state.html_url||'GitHub Actions'));
      remoteProgress('Scraping listo; esperando el redespliegue de Vercel...', 88);
      if(await waitForPublishedSnapshot(state.run_id||id, previousSnapshot, 12*60*1000)) return;
      throw new Error('GitHub terminó bien, pero Vercel aún no ha publicado la instantánea nueva. Revisa '+(state.html_url||'GitHub Actions'));
    }
    remoteProgress(state.status==='queued'?'Scraping en cola en GitHub Actions?':'Scrapeando Zococity y PCComponentes online...', state.status==='queued'?8:35);
    await wait(8000);
  }
  throw new Error('El scraping sigue en marcha. Puedes consultar el progreso en GitHub Actions.');
}
async function refresh(){
  hideErr();
  if(!DATA) await loadData(true);
  if(!DATA) { showErr('No se pudo leer la instantánea publicada.'); return; }
  const previous = DATA && DATA.generated_at;
  $('btnRefresh').disabled = true;
  $('btnRefresh').classList.add('running');
  remoteProgress('Solicitando scraping online...', 5);
  try{
    const skip = $('skipSearch').checked ? '1':'0';
    const startedAt = new Date().toISOString();
    const run = await api('/api/refresh?skip_search='+skip, {method:'POST'});
    remoteProgress(run.already_running?'Ya hay un scraping en marcha...':'Iniciando GitHub Actions...', 8);
    await followRun(run.run_id, run.requested_at||startedAt, previous);
    remoteProgress('Precios actualizados', 100);
  }catch(e){
    showErr('No se pudo completar la actualización: '+(e.message||e));
  }finally{
    $('btnRefresh').disabled = false;
    $('btnRefresh').classList.remove('running');
  }
}

''' + html[block_end:]
print('ok: scraping remoto y seguimiento de publicación')

# 8) listeners y arranque (tras el paso 7, los tres listeners anteriores ya no existen)
rep('''['q','fCat','fAvail'].forEach(id=>$(id).addEventListener('input', renderTable));
$('fCat').addEventListener('change', renderTable); $('fAvail').addEventListener('change', renderTable);

loadData();
detectEnv();''',
'''$('btnRefresh').addEventListener('click', refresh);
['q','fCat','fAvail'].forEach(id=>$(id).addEventListener('input', renderTable));
$('fCat').addEventListener('change', renderTable); $('fAvail').addEventListener('change', renderTable);

loadData();
detectEnv();''', 'listeners')

# 9) quitar el poll() muerto: la app local sí lo tiene, pero aquí no hay backend
#    que lo atienda (la app local lo define en el bloque de progreso). Se sustituye
#    por un refresco silencioso que relee la instantánea publicada cada 5 min.
rep('poll(); setInterval(()=>{ poll(); }, 5000);',
    '''// refresco silencioso cada 5 min: carga la instantánea publicada
setInterval(()=>{ loadData(); }, 300000);''', 'poll muerto -> refresco silencioso')

# 10) metadatos para buscadores y redes (la metadata de Next desaparece con el export)
rep('<meta name="viewport" content="width=device-width, initial-scale=1.0">',
    '''<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="Comparativa de precios entre Zococity y PCComponentes: 54 productos de audio y tecnología con precio, stock y vendedor en ambas tiendas.">
<meta name="theme-color" content="#f4f5f2">
<meta property="og:type" content="website">
<meta property="og:locale" content="es_ES">
<meta property="og:title" content="Zococity vs PCComponentes · Precios en directo">
<meta property="og:description" content="Comparativa de precios entre Zococity y PCComponentes con precio, stock y vendedor en ambas tiendas.">
<meta name="twitter:card" content="summary">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%231e5b4b'/%3E%3Ctext x='16' y='23' font-size='18' font-family='Georgia' font-weight='bold' text-anchor='middle' fill='%23ffffff'%3EZ%3C/text%3E%3C/svg%3E">''',
    'metadatos (description, Open Graph, favicon)')

# 9) pie
old_footer = next(line for line in html.splitlines() if "$('foot').textContent = " in line)
new_footer = "  $('foot').textContent = 'Instantánea pública · precios con IVA sin gastos de envío · el botón Actualizar precios online lanza el scraping en GitHub Actions';"
rep(old_footer, new_footer, 'footer')

# comprobaciones finales: nada debe llamar a la API del backend
for bad in ('/api/data', '/api/status', '/api/excel', '/api/cancel'):
    assert bad not in html, f'referencia residual a {bad}'
print('ok: sin referencias a APIs locales')

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding='utf-8')
if '--html-only' in sys.argv:
    print(f'escrito: {OUT} ({OUT.stat().st_size} b); instantánea conservada')
else:
    snap = json.loads(DATA_SRC.read_text(encoding='utf-8'))
    DATA_OUT.write_text(json.dumps(snap, ensure_ascii=False), encoding='utf-8')
    print(f'escrito: {OUT} ({OUT.stat().st_size} b) · {DATA_OUT} ({len(snap["products"])} productos)')
