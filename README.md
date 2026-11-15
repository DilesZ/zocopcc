# Zococity vs PCComponentes · comparador de precios

Comparativa de precios entre [Zococity](https://zococity.es) y
[PCComponentes](https://www.pccomponentes.com) para 54 productos de audio y
tecnología: precio, stock, vendedor y código de artículo en ambas tiendas.

**En producción:** <https://zocopcc.vercel.app>

> Esta URL y las referencias de operación de abajo describen la instalación de
> origen. Para una instalación independiente en otra cuenta, empieza por
> [`docs/duplicar-proyecto.md`](docs/duplicar-proyecto.md) y usa `/setup-copy`.

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

1. **Programación**: cron-job.org solicita la actualización cada 15 minutos en
   zona `Europe/Madrid`. El workflow conserva también el cron nativo de GitHub
   como respaldo, aunque GitHub puede retrasar o perder eventos programados.
2. **Scraping**: la API de Vercel inicia GitHub Actions. Un runner
   `ubuntu-24.04` arranca Chrome con `nodriver` sobre un display virtual (`Xvfb`)
   y lee las fichas configuradas.
3. **Generación**: `scripts/build_public.py` convierte la instantánea en
   `public/index.html` y `public/data.json`.
4. **Publicación**: un commit de datos a `main` dispara el redespliegue automático
   de Vercel.
5. **Botón web**: `api/refresh.js` inicia el mismo workflow manualmente. El token
   de GitHub vive solo en las variables de entorno de Vercel.

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
├─ CLAUDE.md                    ← contexto permanente para Claude Code
├─ .claude/skills/price-monitor ← mantener y ampliar el comparador
├─ .claude/skills/setup-copy   ← crear instalación en cuentas nuevas
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

1. En GitHub, crea un **Fine-grained personal access token** limitado a este repositorio con permiso **Actions: Read and write**. Se necesita lectura para consultar el progreso y escritura para iniciar el workflow.
2. En Vercel, abre el proyecto `zocopcc` → **Settings → Environment Variables** y añade `GITHUB_ACTIONS_TOKEN` con ese token para **Production**.
3. Vuelve a desplegar Production para que la función reciba la variable.

La API usa además `GITHUB_OWNER` y `GITHUB_REPO` para localizar el repositorio
que ejecuta el scraping. En el proyecto original se mantienen los valores por
defecto; al crear una copia en otra cuenta, configúralos con el propietario y
nombre del repositorio nuevo en Vercel Production antes de probar el botón.

La función `api/refresh.js` valida el origen de las solicitudes manuales, evita
duplicar ejecuciones y aplica una espera de 10 minutos entre solicitudes
manuales. Para el disparador automático comprueba `PRICE_CRON_SECRET`. Ninguna
clave se expone al navegador.

### Programación automática activa

El disparador externo de [cron-job.org](https://cron-job.org/) está configurado
para solicitar la actualización cada 15 minutos en zona horaria `Europe/Madrid`.
GitHub Actions hace el scraping y publica los datos; su cron nativo permanece
como respaldo. GitHub puede retrasar o descartar ejecuciones programadas, así que
confirma el evento en Actions y la hora publicada en la página.

La tarea ya está configurada; estos pasos sirven solo si hay que recrearla:

1. Genera una clave aleatoria segura localmente, por ejemplo en PowerShell:
   `[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLowerInvariant()`.
2. En Vercel → el proyecto → **Settings → Environment Variables**, crea
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

La actualización automática operativa está configurada en cron-job.org cada 15
minutos con zona horaria `Europe/Madrid`; el workflow también mantiene un
`schedule` de GitHub. Para confirmar una ejecución, revisa el historial de
cron-job.org, luego **GitHub → Actions → Refrescar precios**, y por último el sello
de actualización publicado en la web. También se puede iniciar desde **Run workflow**.

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
| Botón online | `GITHUB_OWNER`, `GITHUB_REPO` y `GITHUB_ACTIONS_TOKEN` en Vercel Production |
| Cron externo | Cuenta de cron-job.org y `PRICE_CRON_SECRET` igual en Vercel Production y en la cabecera del job |

## Limitaciones conocidas

- El sitio publicado sirve una **instantánea**. El scraping automático o el botón online la actualizan; Vercel publica los datos cuando termina el workflow.
- La lectura de PCComponentes depende de que Cloudflare no endurezca el reto
  contra las IP del runner. Si endurece, el scraper conserva los datos
  anteriores en caché y lo marca en la columna «Fuente».
- El scraping tarda ~10 min con `--skip-search` y ~15 min con la verificación
  adicional en el buscador interno de PCComponentes.
- El cron de GitHub no es exacto: las ejecuciones se pueden retrasar unos
  minutos bajo carga.

## Claude Code y ampliación del comparador

El repo incluye instrucciones persistentes en [`CLAUDE.md`](CLAUDE.md), una skill
del proyecto en `.claude/skills/price-monitor/` y pasos para abrir o clonar el
repositorio en [`docs/claude-code.md`](docs/claude-code.md). Invoca
`/price-monitor` al añadir otra tienda o diagnosticar el pipeline. Para instalar
una copia en cuentas nuevas usa `/setup-copy`. No hace falta copiar el scraper
dentro de la carpeta de skills.

Para crear una copia independiente en cuentas nuevas, sigue
[`docs/duplicar-proyecto.md`](docs/duplicar-proyecto.md) con la skill
`/setup-copy`. No reutilices el token de GitHub, la clave del cron ni el enlace
local de Vercel del proyecto original.

## Créditos

`nodriver` + Chrome real para superar Cloudflare; Zococity leído por su API
pública de Shopify; PCComponentes leído del JSON-LD de cada ficha oficial.
