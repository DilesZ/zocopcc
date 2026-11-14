#!/usr/bin/env python3
"""Genera la web pública estática (public/index.html) a partir de la app local
(download/zoco-pcc-monitor/index.html), con sustituciones ancladas y verificadas."""
import json
import pathlib
import sys

BASE = pathlib.Path('/home/z/my-project')
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


# 1) barra de botones: quitar Excel y el checkbox de "saltar buscador"
rep('''    <button id="btnRefresh">🔄 Actualizar precios</button>
    <button id="btnExcel">⬇ Descargar Excel</button>
''', '''    <button id="btnRefresh">🔄 Recargar instantánea</button>
''', 'botones')

rep('''    <label class="chk"><input type="checkbox" id="skipSearch"> Saltar verificación del buscador (más rápido)</label>
''', '', 'checkbox skipSearch')

# 2) quitar botón Parar y bloque de progreso (sin backend no hay proceso)
rep('''    <button id="btnCancel" style="display:none">⏹ Parar</button>
''', '', 'boton cancelar')

prog_start = html.index('  <div class="prog" id="prog">')
prog_end = html.index('</div>', html.index('id="progLog"')) + len('</div>\n') + len('  ')
html = html[:prog_start] + html[prog_end:]
print('ok: bloque progreso')

# 3) banner de entorno → texto de modo consulta pública
b_start = html.index('<div class="warn" id="envBox">')
b_end = html.index('</div>', b_start) + len('</div>')
html = html[:b_start] + '''<div class="warn" id="envBox">
  <b>Modo consulta pública.</b><br>
  Esta página pública muestra la <b>última instantánea</b> del monitor. La actualización
  en directo (lectura de ambas tiendas con navegador real) corre en la app local del
  propietario (<code>python3 server.py</code>); aquí el botón «Recargar instantánea»
  vuelve a leer los datos publicados.
</div>''' + html[b_end:]
print('ok: banner')

# 4) loadData: leer la instantánea relativa y avisar en modo banner si falla
rep('''async function loadData(){
  try{
    DATA = await api('/api/data');
    render();
  }catch(e){
    if((e.message||'').includes('404')) return; // el banner de entorno lo explica
    showErr('No se pudieron cargar los datos: '+e.message);
  }
}''', '''async function loadData(){
  try{
    DATA = await api('./data.json?ts='+Date.now());
    render();
    hideErr();
  }catch(e){
    showEnv();
    showErr('No se pudo leer la instantánea de datos ('+e.message+').');
  }
}''', 'loadData')

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
  if(location.protocol==='file:') showEnv();
}''', 'detectEnv')

# 6) subtítulo con letra de copia pública
rep('''  $('meta').textContent = 'Generado: '+ (DATA.generated_at||'—').replace('T',' ') +
    ' · '+p.length+' productos · Zococity vía Shopify JSON · PCComponentes vía fichas oficiales (nodriver + Cloudflare)';''',
    '''  $('meta').textContent = 'Instantánea pública · Generado: '+ (DATA.generated_at||'—').replace('T',' ') +
    ' · '+p.length+' productos';''', 'meta')

# 7) poll/updateProg/refresh/cancelRun → recarga simple de la instantánea
block_start = html.index('/* ---- progreso ---- */')
block_end = html.index("['q','fCat','fAvail']")
html = html[:block_start] + '''async function refresh(){
  hideErr();
  $('btnRefresh').disabled = true;
  try{
    await loadData();
    $('meta').textContent += ' · recargada a las ' + new Date().toLocaleTimeString('es-ES');
  }finally{
    $('btnRefresh').disabled = false;
  }
}

''' + html[block_end:]
print('ok: bloque progreso JS')

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

# 9) pie
rep('''  $('foot').textContent = 'Precios con IVA sin gastos de envío · lectura en directo significa que el dato se tomó de la web oficial en el momento de la actualización · herramientas: nodriver + Chrome';''',
'''  $('foot').textContent = 'Copia pública de consulta · precios con IVA sin gastos de envío · la actualización en directo (Zococity vía Shopify + PCComponentes con nodriver/Chrome) se ejecuta en la app local del propietario';''', 'footer')

# comprobaciones finales: nada debe llamar a la API del backend
for bad in ('/api/data', '/api/status', '/api/refresh', '/api/excel', '/api/cancel'):
    assert bad not in html, f'referencia residual a {bad}'
print('ok: sin referencias a la API del backend')

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding='utf-8')
snap = json.loads(DATA_SRC.read_text(encoding='utf-8'))
DATA_OUT.write_text(json.dumps(snap, ensure_ascii=False), encoding='utf-8')
print(f'escrito: {OUT} ({OUT.stat().st_size} b) · {DATA_OUT} ({len(snap["products"])} productos)')
