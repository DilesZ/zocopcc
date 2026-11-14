#!/bin/bash
# Script de build para el deploy a space-z.ai (llamado por el driver de la plataforma).
# Proyecto Next.js estándar de la plataforma: bun install + next build (export estático)
# + tarball del contenido de out/ (convención del artefacto build_fullstack).
set -e
cd /home/z/my-project

# registrar el contexto que pasa el driver (args + env) para diagnóstico
{ echo "== $(date '+%F %T') =="; echo "args: $*"; echo "pwd: $(pwd)"; env | sort; } \
  > /home/z/my-project/data/build_env.log 2>&1 || true

echo "[build] generando web estática fuente…"
# fuente de verdad: public/ (generada por scripts/build_public.py)
if [ ! -f public/index.html ]; then
  python3 scripts/build_public.py
fi
# copia para la ruta "/" del export (la página Next la embebe vía iframe)
cp -f public/index.html public/site.html

echo "[build] instalando dependencias si faltan…"
if [ ! -d node_modules ]; then
  bun install
fi

echo "[build] construyendo (next build, export estático)…"
bun run build

# convención estática: página completa en la raíz del workspace
cp -f public/index.html index.html
cp -f public/data.json data.json

# artefacto que espera el driver: /tmp/build_fullstack_${BUILD_ID}.tar.gz
BUILD_ID="${BUILD_ID:-$(date +%s)}"
TAR="/tmp/build_fullstack_${BUILD_ID}.tar.gz"
tar -czf "$TAR" -C out .
echo "[build] artefacto listo: $TAR ($(wc -c < "$TAR") bytes, export Next.js)"

# observador de red: graba las conexiones de los 120 s posteriores al build
( for i in $(seq 1 240); do
    echo "== $(date '+%F %T') =="; ss -tnp 2>/dev/null | grep ESTAB
    sleep 0.5
  done ) > /home/z/my-project/data/net_watch.log 2>&1 & disown || true
