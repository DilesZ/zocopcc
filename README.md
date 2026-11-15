# Zococity vs PCComponentes · comparador de precios

Comparativa de precios entre [Zococity](https://zococity.es) y
[PCComponentes](https://www.pccomponentes.com) para 54 productos de audio y
tecnología: precio, stock, vendedor y código de artículo en ambas tiendas.

**En producción:** <https://zocopcc.vercel.app>

---

## Cómo funciona

```
┌──────────────────────┐        ┌───────────────────┐        ┌──────────────┐
│  GitHub Actions      │        │  GitHub (main)    │        │  Vercel      │
│  runner ubuntu-24.04 │──push─>│  public/data.json │──push─>│  zocopcc     │
│                      │        │  public/index.html│        │  .vercel.app │
│  Chrome real + Xvfb  │        └───────────────────┘        └──────────────┘
│  lee ambas tiendas   │
└──────────────────────┘
```

1. **Scraping** (GitHub Actions, diario a las 08:17 hora peninsular): un runner
   `ubuntu-24.04` arranca Chrome real con `nodriver` sobre un display virtual
   (`Xvfb`) y lee las 54 fichas de ambas tiendas.
2. **Generación**: `scripts/build_public.py` convierte la instantánea en
   `public/index.html` y `public/data.json`.
3. **Publicación**: un commit a `main` dispara el redespliegue automático de
   Vercel. **No hay ningún secreto ni token en el repositorio.**

> ¿Por qué Chrome real y no una petición HTTP? Cloudflare bloquea las
> peticiones planas a PCComponentes incluso con `curl` y con UA real. Solo un
> navegador real sin detectable (nodriver + Chrome headed) supera el reto. El
> detalle completo está en `download/zoco-pcc-monitor/SKILL.md`.

## Estructura

```
comparador/
├─ public/                      ← raíz de despliegue (lo único que sube a Vercel)
│  ├─ index.html                ← el sitio (generado)
│  └─ data.json                 ← la instantánea (generada)
├─ download/zoco-pcc-monitor/   ← scraper + app local con backend y Excel
├─ scripts/                     ← generación del sitio y utilidades de investigación
├─ .github/workflows/refresh.yml← scraping diario
├─ vercel.json                  ← outputDirectory: public, sin build
└─ .vercelignore                ← el scraper no viaja a Vercel
```

**Cadena de datos:** `pipeline.py` → `download/zoco-pcc-monitor/data.json` →
`build_public.py` → `public/data.json` → `public/index.html`.

`public/index.html` **no se edita a mano**: se genera. Para cambiar la interfaz
se edita `download/zoco-pcc-monitor/index.html` y se ejecuta
`python3 scripts/build_public.py`.

## Refrescar los precios

**Automático:** el workflow corre solo cada día. No hay que hacer nada.

**Manual, todo el ciclo:**
```bash
pip install nodriver openpyxl
python download/zoco-pcc-monitor/pipeline.py --skip-search   # ~10 min, 54 productos
python scripts/build_public.py                                # regenera public/
git add public/ && git commit -m "datos: instantánea" && git push
```

**Manual, solo el sitio (sin tocar precios):**
```bash
python scripts/build_public.py
git add public/ && git commit -m "public" && git push
```

**Prueba rápida de 2 productos** (útil para validar que el scraping sigue vivo):
```bash
python download/zoco-pcc-monitor/pipeline.py --limit 2 --skip-search
```

**Desde la web de GitHub:** pestaña *Actions* → *Refrescar precios* →
*Run workflow*, con los parámetros `limit` y `skip_search`.

## App local con backend (opcional)

`download/zoco-pcc-monitor/server.py` es la versión con backend: botón
«Actualizar precios» en vivo, barra de progreso, log y descarga de Excel.

```bash
pip install nodriver openpyxl
cd download/zoco-pcc-monitor && python3 server.py   # → http://localhost:8765
```

Requiere Google Chrome instalado. En Linux sin pantalla: `sudo apt install xvfb`.

## Requisitos

| Para | Necesitas |
|---|---|
| Ver el sitio | nada |
| Scraping local | Python 3.10+, `nodriver`, `openpyxl`, Google Chrome |
| Desplegar | cuenta de Vercel (gratis) y de GitHub |

## Limitaciones conocidas

- El sitio publicado es una **instantánea**: los datos tienen la fecha que
  indica la cabecera («Generado: …»). El scraping diario la refresca.
- La lectura de PCComponentes depende de que Cloudflare no endurezca el reto
  contra las IP del runner. Si endurece, el scraper conserva los datos
  anteriores en caché y lo marca en la columna «Fuente».
- El scraping tarda ~10 min con `--skip-search` y ~15 min con la verificación
  adicional en el buscador interno de PCComponentes.
- El cron de GitHub no es exacto: las ejecuciones se pueden retrasar unos
  minutos bajo carga.

## Créditos

`nodriver` + Chrome real para superar Cloudflare; Zococity leído por su API
pública de Shopify; PCComponentes leído del JSON-LD de cada ficha oficial.
