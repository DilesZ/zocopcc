# Crear una copia independiente del comparador

Esta guía es para que otra persona tenga su propia instalación y sus propios
recursos. La copia tendrá un repo de GitHub, un proyecto de Vercel y una tarea de
cron-job.org bajo sus cuentas. No transfiere el proyecto ni las credenciales
originales. En Claude Code, abre la raíz de la copia e invoca `/setup-copy`.

## 1. Crear el repo propio

En GitHub, importa el repositorio fuente a un **repositorio nuevo** bajo la cuenta
del amigo. Si el repositorio de origen es privado, el propietario debe conceder
acceso de lectura o facilitar una exportación autorizada. No uses **Fork** si se
quiere que la copia sea independiente y no aparezca como fork.

Como alternativa, desde una copia local del origen crea un repositorio vacío en
la cuenta nueva, apunta el remoto `origin` al destino y sube la rama `main`. No
incluyas `.env.local`, tokens, archivos de sesión ni `.vercel/`; `.gitignore` ya
los excluye. Comprueba el remoto antes de subir:

```bash
git remote -v
```

Debe mostrar el repo nuevo como `origin`. Si el destino tiene commits propios,
detente y resuelve eso antes de hacer push; no uses `--force` para sobrescribirlo.

## 2. Crear el proyecto de Vercel

En la cuenta del amigo, elige **New Project** e importa el nuevo repo de GitHub.
Selecciona la raíz del repo. La configuración estática de `vercel.json` usa
`public` como directorio de publicación; no hace falta un build de framework. La
API `api/refresh.js` se despliega como función de Node junto al sitio.

En GitHub, crea un Fine-grained Personal Access Token limitado solo al repo nuevo,
con permiso **Actions: Read and write**. Añade en Vercel → Project → Settings →
Environment Variables, para **Production**:

| Variable | Tipo | Valor |
|---|---|---|
| `GITHUB_OWNER` | Config | Usuario u organización dueña del repo nuevo |
| `GITHUB_REPO` | Config | Nombre exacto del repo nuevo |
| `GITHUB_ACTIONS_TOKEN` | Secret | Token fino de GitHub para ese repo |
| `PRICE_CRON_SECRET` | Secret | Clave nueva, aleatoria y exclusiva para esta copia |

No copies valores secretos del proyecto original. Introduce el token y la clave
directamente en Vercel, no en Claude Code ni en archivos versionados. Guarda
`PRICE_CRON_SECRET` también en un gestor de contraseñas para introducir la misma
clave en cron-job.org.

Vuelve a desplegar Production después de añadir las variables. Anota la URL
`https://<proyecto-nuevo>.vercel.app` que muestra Vercel. La API valida el mismo
host que sirve la web, así que no hay que editar un dominio fijo en el código.

## 3. Activar y probar GitHub Actions

Abre el repo nuevo → **Actions**. Habilita Actions si GitHub lo solicita y
comprueba que aparece **Refrescar precios**. El workflow usa `workflow_dispatch`
y `schedule`, y declara `contents: write` para guardar la instantánea en `main`.
Ejecuta manualmente **Run workflow** una vez y espera a que termine. Comprueba:

1. El run exitoso aparece bajo el repo nuevo.
2. Un commit de datos se publica en la rama `main` nueva (si no había cambios,
   el log explica que la instantánea seguía vigente).
3. Vercel registra un nuevo Production deployment desde ese repo.
4. La web nueva muestra el sello de actualización y carga sus propios datos.

La API del botón consulta y dispara el workflow en `GITHUB_OWNER/GITHUB_REPO`.
Verifica en el historial de Actions que no haya ejecutado el repo de origen.

## 4. Crear el cron de la cuenta nueva

En la cuenta del amigo de [cron-job.org](https://console.cron-job.org/), crea un
job con:

- **URL:** `https://<proyecto-nuevo>.vercel.app/api/refresh?skip_search=1&source=automatic`
- **Método:** `POST`
- **Horario:** cada 15 minutos, zona `Europe/Madrid`
- **Cabecera HTTP:** `Authorization: Bearer <PRICE_CRON_SECRET nuevo>`

El secreto debe coincidir con `PRICE_CRON_SECRET` en Vercel Production. Introduce
la clave directamente en ambos paneles y no la pegues en un chat o commit. Guarda
el job habilitado y ejecuta una prueba. Un HTTP 202 es aceptación de la solicitud,
no confirmación de que el scraping haya terminado.

## 5. Verificación de punta a punta

Tras la prueba de cron, revisa el historial del job, el nuevo repo → Actions →
**Refrescar precios**, el commit de datos y el nuevo sello de actualización en la
web. El tiempo completo de lectura puede rondar 10–15 minutos. El `schedule` de
GitHub queda como disparador adicional; comprueba sus eventos en Actions y no
asumas que la programación se ejecutó por ver el cron escrito en YAML.

La carga de precios puede depender de la disponibilidad de GitHub Actions y de
los sitios de origen. El nuevo dueño debe revisar sus cuotas y políticas. Esta
guía no modifica ni apaga el repo, proyecto Vercel o job cron del dueño original.
