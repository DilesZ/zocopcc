# Instrucciones del proyecto

Este repositorio publica una comparativa estática de precios cuyo catálogo base
es Zococity. La automatización compara sus precios con PCComponentes, Carrefour y Fnac, sin mezclar los datos ni perder la identidad del vendedor.

## Antes de cambiar código

- Empieza por esta guía y el `README.md`. Para cambios de scraping, sigue también
  `.claude/skills/price-monitor/SKILL.md` y `download/zoco-pcc-monitor/SKILL.md`.
- Localiza la fuente de verdad en `download/zoco-pcc-monitor/products.json`, los
  fetchers, `pipeline.py`, el constructor público y el workflow afectado.
- Respeta las modificaciones locales que ya existan. No leas, copies, muestres
  ni añadas `.env.local`, tokens, contraseñas o valores de secretos al repositorio.

## Arquitectura y archivos generados

- `download/zoco-pcc-monitor/products.json`: catálogo canónico de productos,
  identificado hoy por el `handle` de Zococity.
- `download/zoco-pcc-monitor/zoco_fetcher.py`, `pcc_fetcher.py`, `carrefour_fetcher.py`, `fnac_fetcher.py` y `retailer_common.py`: lectura directa de fichas configuradas y normalización de cada tienda. Carrefour y Fnac usan URLs de producto guardadas en `products.json` y validan coincidencia exacta por EAN/GTIN en JSON-LD.
- `download/zoco-pcc-monitor/pipeline.py`: orquesta lecturas, mantiene la
  instantánea anterior cuando una fuente falla y escribe metadatos de ejecución.
- `download/zoco-pcc-monitor/index.html`: interfaz fuente. `scripts/build_public.py`
  genera `public/index.html` y copia la instantánea pública a `public/data.json`.
  No edites esos dos archivos públicos a mano.
- `.github/workflows/refresh-precios.yml`: scraping y publicación en GitHub
  Actions. Un push de los datos a `main` provoca el redespliegue de Vercel.
- `api/refresh.js`: solicita ejecuciones manuales y automáticas sin exponer el
  token de GitHub al navegador.
- Una copia del repo debe establecer `GITHUB_OWNER` y `GITHUB_REPO` en Vercel
  Production. La API acepta peticiones del mismo origen por host, por lo que el
  nombre de dominio nuevo no requiere cambios en el código.

## Invariantes de datos

- Los precios se expresan en euros como números; conserva por separado precio,
  disponibilidad, vendedor, SKU, EAN, URL y procedencia de cada tienda.
- Distingue `true`, `false` y `null` para disponibilidad o presencia cuando
  corresponda. Un fallo de lectura no demuestra que un producto esté agotado ni
  que la tienda no lo venda.
- Al fallar una tienda, conserva su último dato conocido e indica que no se leyó
  en directo. No sustituyas datos de una tienda por los de otra.
- El identificador de producto debe señalar la misma variante (modelo, tamaño,
  color, impedancia u otra característica relevante). Usa EAN/SKU cuando existan;
  no enlaces productos solo por parecido del título.
- Mantén la compatibilidad de `public/data.json` y de la interfaz. Si incorporar
  una tienda exige cambiar el esquema, planifica una migración compatible y
  actualiza la generación y la visualización juntas.

## Automatización y seguridad

- La actualización externa vigente usa tres jobs coordinados de cron-job.org para mantener una cadencia de 45 minutos, en
  `Europe/Madrid`, con POST a `/api/refresh?skip_search=1&source=automatic` y
  `Authorization: Bearer …`. El secreto compartido se llama
  `PRICE_CRON_SECRET` y vive en Vercel Production y en la cabecera de cron-job.org.
- El workflow de GitHub conserva tres reglas `schedule` que mantienen la misma
  cadencia de 45 minutos. No asumas que se ejecutaron: comprueba Actions y la hora
  de la instantánea. La concurrencia del
  workflow evita scrapes simultáneos y el endpoint devuelve `already_running`
  si ya hay uno activo.
- `GITHUB_ACTIONS_TOKEN` y `PRICE_CRON_SECRET` son secretos de producción. No
  los pidas en el chat, no los escribas en archivos versionados y no cambies o
  roten claves sin indicación expresa del usuario.
- No ejecutes un scrape completo, no dispares una actualización de producción,
  no alteres los intervalos ni publiques cambios remotos salvo que el usuario
  lo pida explícitamente. Para depurar, prefiere logs, fixtures y límites bajos.
- Usa fuentes públicas/autorizadas, peticiones espaciadas y caché. No intentes
  sortear CAPTCHA, autenticación o controles explícitos de acceso. Si una tienda
  bloquea la lectura, conserva el dato previo y explica la limitación.

## Estilo de colaboración

- Responde en español salvo que el usuario pida otro idioma.
- Explica con precisión qué se leyó en directo y qué procede de caché.
- No afirmes que una ejecución automática funciona hasta verificar un evento,
  su resultado y la publicación de los datos.
- No publiques, compres un plan ni crees cuentas de terceros como parte implícita
  de un cambio de código.
- Para una instalación independiente en cuentas nuevas, sigue la skill
  `.claude/skills/setup-copy/SKILL.md`; mantén nuevos tokens y claves propios de
  esa copia y no los pidas ni los repitas en el chat.
