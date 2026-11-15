# Descargas y app portátil

Esta carpeta contiene los artefactos generados y la versión portátil del
monitor, pensada para poder ejecutarse en cualquier PC.

## Contenido

| Ruta | Qué es |
|---|---|
| `zoco-pcc-monitor/` | App local completa: scraper, backend (`server.py`), Excel y la interfaz original |
| `Comparativa_Zococity_vs_PCComponentes.xlsx` | Última comparativa exportada a Excel |

## `zoco-pcc-monitor/` — app portátil

Contiene el scraper y una web con backend, botón «Actualizar precios» en vivo,
barra de progreso, log de la ejecución y descarga de Excel.

```bash
pip install -r zoco-pcc-monitor/requirements.txt
cd zoco-pcc-monitor
python3 server.py        # → http://localhost:8765
```

Requisitos: Python 3.10+ y Google Chrome instalado. En Linux sin pantalla
gráfica: `sudo apt install xvfb`.

En `zoco-pcc-monitor/SKILL.md` está la metodología completa (por qué no
funcionan `curl`, la impersonación TLS, los proxies lectores, Selenium,
Playwright, Puppeteer ni Chrome headless, y por qué `nodriver` + Chrome real sí
funciona contra el reto de Cloudflare de PCComponentes).

## Relación con el sitio publicado

El sitio de <https://zocopcc.vercel.app> **no** usa esta carpeta: se genera en
`public/` a partir de `zoco-pcc-monitor/index.html` y `zoco-pcc-monitor/data.json`
con `scripts/build_public.py`. Esta carpeta es la fuente y la app local; `public/`
es el resultado publicado.

```bash
# desde la raíz del repositorio
python3 download/zoco-pcc-monitor/pipeline.py --skip-search   # refresca los datos
python3 scripts/build_public.py                                # regenera public/
```
