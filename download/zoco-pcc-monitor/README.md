# Zococity vs PCComponentes · monitor de precios en directo

Web local con botón **«🔄 Actualizar precios»** que ejecuta en segundo plano la lectura
en directo de ambas tiendas y actualiza la tabla al terminar.

## Inicio rápido

```bash
pip install nodriver openpyxl
# Linux sin entorno gráfico: sudo apt install xvfb
python3 server.py
# → abre http://localhost:8765
```

Requisito: Google Chrome instalado (o `export CHROME_PATH=/ruta/a/chrome`).

Al arrancar, `server.py` abre solo `http://localhost:8765` en tu navegador
(desactívalo con `AUTO_OPEN=0` si no quieres).

## Problemas frecuentes

**«No se pudo iniciar (HTTP 404)» al pulsar Actualizar.**
La página se está abriendo **sin el backend**. Este 404 no lo da `server.py` (que siempre
responde a la API): lo da el entorno desde el que abriste la página. Causas típicas:
doble clic en `index.html` (file://), «Open with Live Server» de VS Code,
`python3 -m http.server`, XAMPP/Apache, o una web publicada en un hosting.
**Solución única:** cierra esa pestaña, ejecuta `python3 server.py` en la carpeta y usa
`http://localhost:8765`. La propia web detecta esta situación y muestra un banner azul.

**«El puerto 8765 ya está en uso.** Arranca en otro puerto:
`PORT=9000 python3 server.py` (Linux/macOS) o `set PORT=9000 && python server.py` (Windows),
y abre `http://localhost:9000`.

**«Chrome no encontrado».** Instala Google Chrome o exporta `CHROME_PATH=/ruta/a/chrome`.

**¿Puedo publicarla en internet?** La tabla sí es estática, pero el botón **no**: ejecuta
el proceso en la máquina donde corre `server.py`. En tu propia red local ya funciona en
otras máquinas con `http://TU-IP:8765` (el servidor escucha en todas las interfaces).
En un hosting de internet necesitarías el backend Python ahí, y Cloudflare es aún más
agresivo con IPs de datacenter — no recomendado.

**Linux sin entorno gráfico.** Instala xvfb (`sudo apt install xvfb`); el fetcher lo
arranca solo.

**Excel falla (501).** Falta openpyxl: `pip install openpyxl`.


## Qué hace el botón Actualizar

1. Lee el catálogo de **Zococity** en directo (Shopify `/products/<handle>.js` vía
   navegador automatizado — la web bloquea las descargas planas con 429).
2. Abre la **ficha oficial de cada producto en PCComponentes** en directo y supera el
   reto de Cloudflare (nodriver = Chrome real no detectable). De cada ficha lee precio,
   stock, vendedor, SKU interno (cod. artículo) y EAN.
3. Verifica con el buscador interno de PCC los productos sin ficha conocida.
4. Fusiona todo en `data.json` (la versión anterior se guarda en `data_prev.json`) y la
   web se refresca sola.

Tiempo: ~15 min completo (54 productos). El checkbox «Saltar verificación del buscador»
lo deja en ~10 min. Para probar en 1 minuto usa la API:
`curl -X POST "http://localhost:8765/api/refresh?limit=2&skip_search=1"`.

## Archivos

| Fichero | Papel |
| --- | --- |
| `SKILL.md` | Skill portátil (metodología completa) para Claude Code / OpenCode |
| `server.py` | Web + API local (solo librería estándar) |
| `index.html` | Interfaz (auto-contenida) |
| `pipeline.py` | Orquestador: Zoco → PCC → fusión → data.json |
| `zoco_fetcher.py` | Catálogo Zococity en directo (nodriver + XHR síncrono) |
| `pcc_fetcher.py` | Fichas PCComponentes en directo (nodriver + JSON-LD) + buscador |
| `excel.py` | Genera el Excel comparativo |
| `products.json` | Config de los 54 productos (editable a mano) |
| `data.json` | Última instantánea (la que muestra la web) |
| `data_prev.json` | Instantánea anterior (respaldo) |

## Endpoints

- `GET /api/data` · `GET /api/status` (progreso + log)
- `POST /api/refresh?limit=N&skip_search=1` · `POST /api/cancel`
- `GET /api/excel` (descarga)

## Notas

- Los precios se leen en el momento de la actualización y cambian a lo largo del día.
- «No disponible en PCComponentes» = ausencia verificada en su buscador interno.
- `SKILL.md` contiene TODAS las reglas para que el flujo funcione en otro PC
  (rutas de skill incluidas) y explica por qué no funcionan los métodos clásicos
  (curl, TLS impersonation, Selenium, headless…).
