# Usar este proyecto con Claude Code

El proyecto ya está preparado para Claude Code. Al abrir el repositorio desde su
carpeta raíz, Claude lee `CLAUDE.md`; la skill del proyecto queda en
`.claude/skills/price-monitor/SKILL.md` y también puede invocarse como
`/price-monitor`. La skill sigue el formato estándar `SKILL.md` y sus referencias
se cargan solo cuando hacen falta. Para una instalación nueva de un amigo, usa
la skill `/setup-copy`.

## Abrir el proyecto

Si ya tienes la carpeta, abre una terminal en ella y ejecuta:

```powershell
claude
```

Para traerlo en otro ordenador:

```powershell
git clone https://github.com/<usuario>/<repositorio-propio>.git
Set-Location <repositorio-propio>
claude
```

Comprueba que Claude cargó las instrucciones con `/memory` o `/context` y que la
skill aparece como `/price-monitor` o pídela por su nombre.

## Credenciales y producción

El repositorio no contiene credenciales. El botón online usa `GITHUB_ACTIONS_TOKEN`
en Vercel Production. El cron-job.org activo usa `PRICE_CRON_SECRET` en Vercel
Production y la cabecera `Authorization` del job. Mantén ambos secretos fuera del
chat, de archivos del repo, capturas y commits. `.env.local` es local y está
ignorado por Git; no hace falta copiarlo al usar Claude Code.

No es necesario volver a crear la tarea de cron para clonar o abrir el proyecto.
El cron y la integración de Vercel permanecen en sus servicios asociados al repo.
Si cambias de cuenta, dominio o proveedor, migra los secretos y el job de forma
deliberada antes de desactivar la configuración actual.

Para una copia completamente independiente en otras cuentas de GitHub, Vercel y
cron-job.org, sigue [`duplicar-proyecto.md`](duplicar-proyecto.md) e invoca
`/setup-copy` en Claude Code.

## Primera tarea recomendada para añadir una tienda

Invoca `/price-monitor` y pide, por ejemplo: “Analiza cómo añadir [tienda] a la
comparativa; primero revisa sus fuentes públicas y presenta una propuesta de
adaptador, matching y campos sin cambiar el cron ni ejecutar scraping completo”.
Después de revisar la propuesta, pide la implementación y la validación acotada.

No copies `download/zoco-pcc-monitor` a la carpeta `.claude/skills`: esa carpeta
contiene la aplicación y el scraper. La skill está separada bajo `.claude/skills`.
