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

1. **Scraping** (GitHub Actions, cada 15 minutos): un runner
   `ubuntu-24.04` arranca Chrome real con `nodriver` sobre un display virtual
   (`Xvfb`) y lee las 54 fichas de ambas tiendas.
2. **Generación**: `scripts/build_public.py` convierte la instantánea en
   `public/index.html` y `public/data.json`.
3. **Publicación**: un commit a `main` dispara el redespliegue automático de Vercel.
4. **Actualización desde la web**: `api/refresh.js` inicia el workflow. El token requerido se guarda solo en las variables de entorno de Vercel, nunca en el repositorio ni en el navegador.

> ¿Por qué Chrome real y no una petición HTTP? Cloudflare bloquea las
> peticiones planas a PCComponentes incluso con `curl` y con UA real. Solo un
> navegador real sin detectable (nodriver + Chrome headed) supera el reto. El
> detalle completo está en `download/zoco-pcc-monitor/SKILL.md`.

## Estructura

```
comparador/
- public/ (sitio estatico y datos publicados)
- api/refresh.js (funcion segura que inicia GitHub Actions)
│  ├─ index.html                ← el sitio (generado)
│  └─ data.json                 ← la instantánea (generada)
├─ download/zoco-pcc-monitor/   ← scraper + app local con backend y Excel
├─ scripts/                     ← generación del sitio y utilidades de investigación
├─ .github/workflows/refresh-precios.yml← actualización automática y manual
├─ vercel.json                  ← outputDirectory: public, sin build
└─ .vercelignore                ← el scraper no viaja a Vercel
```

**Cadena de datos:** `pipeline.py` → `download/zoco-pcc-monitor/data.json` →
`build_public.py` → `public/data.json` → `public/index.html`.

`public/index.html` **no se edita a mano**: se genera. Para cambiar la interfaz
se edita `download/zoco-pcc-monitor/index.html` y se ejecuta
`python3 scripts/build_public.py`.

## Actualizar precios desde la web

La página carga la última instantánea desde `public/data.json`. Al pulsar **Actualizar precios online**, una función de Vercel inicia GitHub Actions, que ejecuta Chrome real con `nodriver`, scrapea los 54 productos y publica una instantánea nueva. GitHub Actions espera hasta terminar; el push de datos dispara el redespliegue de Vercel y la página carga la instantánea nueva automáticamente.

La casilla **Saltar verificación del buscador** viene marcada para hacer la actualización más rápida. Desmárcala para incluir también la búsqueda de productos sin ficha conocida.

### Configuración necesaria una sola vez

El token vive solo en las variables de entorno de Vercel; nunca en el repositorio ni en el navegador:

1. En GitHub, crea un **Fine-grained personal access token** limitado al repositorio `DilesZ/zocopcc` con permiso **Actions: Read and write**. Se necesita lectura para consultar el progreso y escritura para iniciar el workflow.
2. En Vercel, abre el proyecto `zocopcc` → **Settings → Environment Variables** y añade `GITHUB_ACTIONS_TOKEN` con ese token para **Production**.
3. Vuelve a desplegar Production para que la función reciba la variable.

La función `api/refresh.js` valida el origen del sitio, evita duplicar una ejecución activa y aplica una espera de 10 minutos entre solicitudes manuales. No expone el token al cliente.

### Respaldo si GitHub no dispara el cron

GitHub Actions puede retrasar o descartar ejecuciones programadas. Para mantener
la actualización cada 15 minutos, se puede usar [cron-job.org](https://cron-job.org/)
como disparador externo; el scraping y la publicación siguen ejecutándose en
GitHub Actions. La API exige una clave propia para estas llamadas automáticas:

1. Genera una clave aleatoria localmente, por ejemplo en PowerShell:
   `-join ((1..48 | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) }))`.
2. En Vercel → proyecto `zocopcc` → **Settings → Environment Variables**, crea
   `PRICE_CRON_SECRET` para **Production** con esa clave y vuelve a desplegar.
3. En cron-job.org crea una tarea **POST** cada 15 minutos con zona horaria
   `Europe/Madrid` y URL:
   `https://zocopcc.vercel.app/api/refresh?skip_search=1&source=automatic`
4. En sus cabeceras HTTP añade
   `Authorization: Bearer <la misma clave>`.

Una respuesta HTTP **202** significa que la solicitud quedó aceptada por GitHub;
la tarea completa y actualiza la web al terminar. Las llamadas automáticas se
guardan en `last_automatic_update`. Conserva también el `schedule` de GitHub como
respaldo adicional; la concurrencia impide que se ejecuten dos scrapeos a la vez.

### Alternativas

La actualización automática está programada cada 15 minutos. También se puede iniciar desde **GitHub → Actions → Refrescar precios → Run workflow**.

Para hacerlo manualmente desde el ordenador:

```bash
pip install nodriver openpyxl
python download/zoco-pcc-monitor/pipeline.py --skip-search
python scripts/build_public.py
git add public/ && git commit -m "datos: instantánea" && git push
```

## Requisitos

| Para | Necesitas |
|---|---|
| Ver el sitio | nada |
| Scraping local | Python 3.10+, `nodriver`, `openpyxl`, Google Chrome |
| Desplegar y habilitar el botón online | GitHub, Vercel y un token fine-grained guardado como variable de entorno en Vercel |

## Limitaciones conocidas

- El sitio publicado sirve una **instantánea**. El scraping automático o el botón online la actualizan; Vercel publica los datos cuando termina el workflow.
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
