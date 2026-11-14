#!/bin/bash
# Script de build para el deploy a space-z.ai (llamado por el driver de la plataforma).
# La web es una página estática auto-contenida: la prepara en la raíz del workspace
# y en dist/ para cubrir las dos convenciones posibles del servidor de spaces.
set -e
cd /home/z/my-project

# registrar el contexto que pasa el driver (args + env) para diagnóstico
{ echo "== $(date '+%F %T') =="; echo "args: $*"; echo "pwd: $(pwd)"; env | sort; } \
  > /home/z/my-project/data/build_env.log 2>&1 || true

echo "[build] preparando web estática…"
mkdir -p dist

# fuente de verdad: public/ (generada por scripts/build_public.py)
if [ ! -f public/index.html ]; then
  python3 scripts/build_public.py
fi

# 1) raíz del workspace (si el servidor de spaces sirve el proyecto completo)
cp -f public/index.html index.html
cp -f public/data.json data.json

# 2) dist/ (convención habitual de salida de build)
cp -f public/index.html dist/index.html
cp -f public/data.json dist/data.json

# el backend completo queda en download/zoco-pcc-monitor/ (no forma parte del estático)
echo "[build] OK: index.html + data.json en raíz y en dist/ ($(wc -c < index.html) bytes)"

# artefacto que espera el driver: /tmp/build_fullstack_${BUILD_ID}.tar.gz
BUILD_ID="${BUILD_ID:-$(date +%s)}"
TAR="/tmp/build_fullstack_${BUILD_ID}.tar.gz"
tar -czf "$TAR" -C /home/z/my-project/dist index.html data.json
echo "[build] artefacto listo: $TAR ($(wc -c < "$TAR") bytes)"

# observador de red: graba las conexiones de los 30 s posteriores al build
# (momento en el que el driver sube el artefacto a la plataforma)
( for i in $(seq 1 60); do
    echo "== $(date '+%F %T') =="; ss -tnp 2>/dev/null | grep ESTAB
    sleep 0.5
  done ) > /home/z/my-project/data/net_watch.log 2>&1 & disown || true
