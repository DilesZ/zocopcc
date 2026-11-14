#!/bin/bash
# Watchdog de la web pública (space-z.ai): relanza server.py si se cae.
# Uso: nohup /home/z/my-project/scripts/watchdog_web.sh >> /home/z/my-project/data/watchdog.log 2>&1 &
APP=/home/z/my-project/download/zoco-pcc-monitor
LOG=/home/z/my-project/data/server3000.log

while true; do
  if ! curl -s -m 5 http://127.0.0.1:3000/api/status > /dev/null 2>&1; then
    echo "$(date '+%F %T') servidor caído; relanzando..."
    cd "$APP" && PORT=3000 AUTO_OPEN=0 nohup python3 server.py >> "$LOG" 2>&1 &
    disown
    sleep 3
    if curl -s -m 5 http://127.0.0.1:3000/api/status > /dev/null 2>&1; then
      echo "$(date '+%F %T') relanzado OK (proxy: $(curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:81/))"
    else
      echo "$(date '+%F %T') relanzamiento FALLIDO"
    fi
  fi
  sleep 60
done
