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
