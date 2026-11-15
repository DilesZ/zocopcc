#!/bin/bash
# Watchdog de la web pública: mantiene el backend (server.py) vivo en :3000
# y sincroniza la instantánea actualizada hacia public/ (versión estática de respaldo).
# Uso: nohup scripts/watchdog_web.sh >> data/watchdog.log 2>&1 &

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/download/zoco-pcc-monitor"
DATA_DIR="${DATA_DIR:-$ROOT/data}"
LOCK="$DATA_DIR/watchdog.lock"
LOG="$DATA_DIR/server3000.log"
mkdir -p "$DATA_DIR"

# lockfile: evita instancias duplicadas
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK")" 2>/dev/null; then
  echo "$(date '+%F %T') ya hay un watchdog (pid $(cat "$LOCK")); salgo"
  exit 0
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

while true; do
  if ! curl -s -m 5 http://127.0.0.1:3000/api/status > /dev/null 2>&1; then
    # tras un reciclaje del sandbox, los paquetes pip se pierden: reinstalarlos
    if ! python3 -c "import nodriver, openpyxl" 2>/dev/null; then
      echo "$(date '+%F %T') reinstalando paquetes (nodriver, openpyxl)..."
      pip install -q nodriver openpyxl >> "$DATA_DIR/watchdog.log" 2>&1
    fi
    echo "$(date '+%F %T') servidor caído; relanzando..."
    cd "$APP" && PORT=3000 AUTO_OPEN=0 nohup python3 server.py >> "$LOG" 2>&1 &
    disown
    sleep 3
    if curl -s -m 5 http://127.0.0.1:3000/api/status > /dev/null 2>&1; then
      echo "$(date '+%F %T') relanzado OK (proxy público: $(curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:81/))"
    else
      echo "$(date '+%F %T') relanzamiento FALLIDO"
    fi
  fi
  # la copia estática de public/ siempre refleja la última instantánea
  if [ "$APP/data.json" -nt "$APP/../../public/data.json" ]; then
    cp "$APP/data.json" "$ROOT/public/data.json"
    echo "$(date '+%F %T') public/data.json sincronizado"
  fi
  # refresco automático diario a las 10:00 (hora del servidor) si no hay proceso activo
  MARCA="/tmp/.refresh_$(date +%F)"
  if [ "$(date +%H)" = "10" ] && [ ! -f "$MARCA" ]; then
    if curl -s -m 5 http://127.0.0.1:3000/api/status | grep -q '"running": false'; then
      curl -s -m 10 -X POST "http://127.0.0.1:81/api/refresh?skip_search=1" > /dev/null
      echo "$(date '+%F %T') refresco diario automático lanzado"
    else
      echo "$(date '+%F %T') refresco diario: había un proceso activo; no se lanza"
    fi
    touch "$MARCA"
  fi
  sleep 60
done
