#!/bin/bash
# Servidor de la web para el espacio (usado si la plataforma ejecuta la app).
set -e
cd /home/z/my-project
bash "$(dirname "$0")/build.sh"
PORT="${PORT:-3000}"
echo "[start] sirviendo la web en el puerto $PORT…"
exec python3 -m http.server "$PORT" --bind 0.0.0.0 --directory /home/z/my-project/dist
