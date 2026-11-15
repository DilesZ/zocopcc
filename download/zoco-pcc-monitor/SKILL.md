---
name: zoco-pcc-monitor
description: >
  Lee en DIRECTO los precios de PCComponentes (tras Cloudflare) y el catálogo de
  Zococity para compararlos, generar data.json y servir una web con botón de
  actualización y Excel. Usar cuando el usuario pida comparar precios entre ambas
  tiendas, refrescar la comparativa, monitorizar precios de audio/hi-fi, o explicar
  cómo scrapear PCComponentes superando Cloudflare con nodriver.
---

# Zococity vs PCComponentes · lectura de precios EN DIRECTO

## Qué hace

1. **Zococity (zococity.es)**: lee el catálogo Shopify en directo (`/products/<handle>.js`)
   → título, marca, precio, stock, SKU y EAN de cada variante.
2. **PCComponentes (pccomponentes.com)**: abre la ficha oficial de cada producto con un
   navegador real no detectable, supera el reto de Cloudflare y extrae el **JSON-LD**:
   precio con IVA, disponibilidad, **vendedor** (PCC propio o marketplace), **SKU interno
   (cod. artículo)** y EAN. Los productos sin ficha conocida se verifican con el
   **buscador interno** de PCC en directo.
3. **Fusiona** ambas lecturas (con respaldo en caché si una ficha falla) → `data.json`.
4. **Sirve una web** (`server.py`) con botón «Actualizar precios», progreso en vivo,
   filtros y descarga de Excel (`openpyxl`).

Todo está implementado en esta carpeta. No necesitas escribir código nuevo: usa la app.

## Requisitos e instalación

```bash
# 1) Python 3.10+ y pip
pip install nodriver openpyxl

# 2) Google Chrome instalado (cualquiera de estos):
#    - Linux: google-chrome / chromium (apt, dnf…) o binario en ~/.cache/puppeteer/chrome/
#    - macOS: Google Chrome.app
#    - Windows: chrome.exe estándar
#    Si está en una ruta rara: export CHROME_PATH=/ruta/a/chrome

# 3) Solo en Linux SIN entorno gráfico: xvfb
sudo apt install xvfb        # (dnf: sudo dnf install xorg-x11-server-Xvfb)

# 4) Arrancar la web
python3 server.py            # → http://localhost:8765  (puerto: PORT=9000 python3 server.py)
```

Probar fetchers aislados:

```bash
python3 zoco_fetcher.py fiio-ft3 audio-technica-ath-m50x          # catálogo Zoco
python3 pcc_fetcher.py "https://www.pccomponentes.com/audio-technica-ath-m50x-auriculares-de-estudio-cerrados"
python3 pipeline.py --limit 2                                     # proceso completo con 2 productos
python3 excel.py                                                  # regenera el Excel a mano
```

## Por qué NO funcionan las alternativas (probado el 14/11/2026)

| Método | Resultado |
| --- | --- |
| `curl`/`requests` con User-Agent real | 403 + «Just a moment...» (Cloudflare reta incluso `/robots.txt`) |
| Impersonación TLS con `curl_cffi` (huella Chrome real) | 403: CF reta por **reputación de IP** + exige JS |
| Proxies lectores (r.jina.ai, allorigins, codetabs, Google Translate) | Bloqueados o 522 por mala reputación de IP |
| Selenium / Playwright / Puppeteer estándar | Reto en bucle (fingerprint de driver detectado) |
| Chrome headless (`--headless`) | Reto en bucle (integridad de navegador fallida) |
| API móvil/apiv2 de PCC | No existe (`apiv2.pccomponentes.com` sin DNS; `api.` → 404 CF) |
| **`nodriver` (Chrome real, headed, Xvfb en Linux)** | **Funciona: reto auto-resuelto en 4-10 s** |

Zococity también bloquea el HTTP plano (429 rate-limit y `products.json` desactivado):
la única vía estable es también navegador real con XHR síncrono.

## LA TÉCNICA de PCComponentes (reglas duras, a golpe de fallo)

Implementada en `pcc_fetcher.py`. Resumen para reproducirla desde cero:

1. **nodriver** (`pip install nodriver`): Chrome real sin los leaks de CDP de Selenium.
   En Linux sin pantalla: arranca `Xvfb :99 -screen 0 1400x900x24` y usa headless=False
   (`xvfb_display=':99'`). En macOS/Windows: headed directamente.
2. **La PRIMERA navegación debe ser la URL objetivo** (una ficha de producto), nunca la
   portada. La portada dispara un reto más duro y envenena la sesión.
3. **Nunca cierres pestañas** (`tab.close()` mata la sesión y CF endurece para todo lo
   siguiente). Una sola pestaña durante todo el proceso.
4. **Reutiliza la pestaña**: la cookie `cf_clearance` queda ganada y las siguientes
   navegaciones cargan sin reto.
5. **El reto es «non-interactive»**: se resuelve solo esperando. Sondea cada 2 s
   `document.title` hasta que deje de contener «Just a moment» (tolerancia: 120 s).
6. **Ritmo**: 4-6 s entre fichas. Ráfagas rápidas degradan la reputación de la IP y CF
   escala a retos que ya no se auto-resuelven. Si todo empieza a fallar de golpe:
   **cooldown de 10-30 min** y reintentar más despacio (no insistas: empeora).
7. **Extracción**: JSON-LD de la página (`script[type="application/ld+json"]`, búsqueda
   **recursiva** para soportar `@graph` y arrays) de cada `@type: Product`. Una ficha con
   N vendedores = N Product. Elige la oferta así (función `pick_offer`):
   1. `seller` = PcComponentes y `availability` InStock (más barata de esas);
   2. si no, PcComponentes aunque esté agotada;
   3. si no, la más barata InStock (marketplace);
   4. si no, la más barata global.
   Campos: `offers.price` (€ con IVA), `offers.availability`, `offers.seller.name`,
   `sku` (**cod. artículo interno de PCC**), `gtin13` (EAN), `name` (título exacto).
8. **Productos sin ficha conocida**: búscalos en `https://www.pccomponentes.com/buscar/?query=<q>`
   con la misma sesión; espera hidratación (hasta ~18 s) y extrae las tarjetas: links
   `a[href^="https://www.pccomponentes.com/<slug>"]` de un solo segmento + precio del
   `innerText` de la tarjeta. Si la mejor tarjeta no contiene los tokens del modelo
   (≥2), el producto **no está en PCC** («no disponible verificado»).
9. **Ficha blindada** (CF endurece puntualmente sobre URLs muy rastreadas, p. ej.
   «Sennheiser Momentum TW4»): el precio puede obtenerse de las **tarjetas del buscador**
   (misma web, dato en directo) o, como último recurso, del índice de Google Shopping,
   etiquetando la fuente en el output. Nunca lo presentes como ficha en directo.
10. **Gotchas de nodriver**:
    - `tab.evaluate()` **no espera promesas**: `fetch().then()` devuelve `None`. Usa
      `XMLHttpRequest` síncrono o JS puro.
    - Navegar con `tab.get(url)` (pestaña) o `browser.get(url)` (primera); ambas devuelven
      la pestaña.
    - `browser.stop()` al final puede lanzar «Event loop is closed»: ignóralo (try/except).
    - Errores «Cannot navigate to invalid URL»: estabas pasando handles en vez de URLs
      completas (bug clásico de iterar `dict.items()` con los nombres invertidos).

## Zococity (también en `zoco_fetcher.py`)

- Abre `https://zococity.es/` con nodriver (una sola navegación).
- Por cada handle lanza, desde dentro de la página, un **XHR síncrono** a
  `/products/<handle>.js` (JSON oficial de Shopify):
  `variants[0]` → `price` (céntimos), `available`, `sku`, `barcode` (EAN);
  raíz → `title`, `vendor`.
- 0,9 s entre peticiones. Nada de `fetch()` asíncrono (ver gotcha nº 10).

## El proceso completo (`pipeline.py`)

```
1. products.json  → lista fija de productos (handle, categoría, query PCC, url_pcc)
2. zoco_fetcher   → catálogo Zoco en directo            (~1 min para 54)
3. pcc_fetcher    → fichas PCC en directo               (~8 min para ~30, 5 s de gap)
4. pcc_fetcher.verify_search → verificación de ausentes (~5 min, opcional: --skip-search)
5. merge          → reglas pick_offer + respaldo en caché (data_prev.json)
6. data.json      → instantánea que la web lee
```

Respaldo y resiliencia: si una lectura falla (reto CF, ficha retirada), el producto
conserva el dato de la ejecución anterior y la columna «Fuente» lo deja claro. `data.json`
se sustituye atómicamente y la versión previa queda en `data_prev.json`.

## Añadir o cambiar productos

Edita `products.json` (misma estructura que las entradas existentes):
`handle` de Zoco (`zococity.es/products/<handle>`), `cat`, `query` (texto para el buscador
de PCC), `url_pcc` si ya conoces la ficha, `verified_no_pcc: true` si ya se verificó su
ausencia. No hace falta tocar código.

## Web y Excel

- `python3 server.py` → `http://localhost:8765`: botón «🔄 Actualizar precios» (POST
  `/api/refresh`, progreso por `/api/status`, cancelación por `/api/cancel`), filtros y
  «⬇ Descargar Excel» (`/api/excel`, requiere openpyxl).
- Endpoints: `GET /api/data`, `GET /api/status`, `POST /api/refresh?limit=N&skip_search=1`,
  `POST /api/cancel`, `GET /api/excel`.
- El Excel replica la comparativa con reglas de color (verde = Zococity más barato).

## Uso con asistentes de código

Esta carpeta contiene el scraper y su documentación técnica; no copies toda la
aplicación dentro de una carpeta de skills. Para Claude Code, abre el repositorio
desde su raíz: lee `CLAUDE.md` y usa `.claude/skills/price-monitor/`. La guía de
portabilidad está en `docs/claude-code.md`.

## Límites éticos y legales

- Datos públicos de tiendas, leídos a ritmo humano (4-6 s entre fichas), para comparativa
  personal o interna. Sin volumen agresivo, sin evasión para spam, sin revender los datos.
- Respeta robots.txt y las condiciones de uso de cada tienda; uso de las URLs oficiales
  de ficha para atribuir el dato.
- Los precios cambian a lo largo del día: el dato vale para el momento de la lectura y la
  web lo fecha siempre.
