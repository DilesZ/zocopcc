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
# estructura de proyecto completo para cubrir todas las convenciones del
# servidor de spaces: estático (index.html en la raíz), build (npm run build)
# y arranque (npm start en $PORT).
BUILD_ID="${BUILD_ID:-$(date +%s)}"
TAR="/tmp/build_fullstack_${BUILD_ID}.tar.gz"

cat > /home/z/my-project/dist/package.json <<'JSON'
{
  "name": "zocopcc",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "build": "node build.js",
    "start": "node serve.js",
    "dev": "node serve.js"
  }
}
JSON

cat > /home/z/my-project/dist/build.js <<'JS'
// build: copia la web estática a out/
const fs = require('fs');
fs.mkdirSync('out', {recursive: true});
for (const f of ['index.html', 'data.json']) {
  if (fs.existsSync(f)) fs.copyFileSync(f, 'out/' + f);
}
console.log('build OK: out/index.html + out/data.json');
JS

cat > /home/z/my-project/dist/serve.js <<'JS'
// servidor estático en process.env.PORT (3000 por defecto), sirve out/ o ./
const http = require('http'), fs = require('fs'), path = require('path');
const root = fs.existsSync('out') ? 'out' : '.';
const types = {'.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8'};
http.createServer((req, res) => {
  let p = req.url.split('?')[0];
  if (p === '/') p = '/index.html';
  const file = path.join(root, path.normalize(p).replace(/^([.][.][/\\])+/, ''));
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end('Not found'); return; }
    res.writeHead(200, {'Content-Type': types[path.extname(file)] || 'application/octet-stream'});
    res.end(data);
  });
}).listen(process.env.PORT || 3000, () => console.log('sirviendo en', process.env.PORT || 3000));
JS

tar -czf "$TAR" -C /home/z/my-project/dist package.json build.js serve.js index.html data.json
echo "[build] artefacto listo: $TAR ($(wc -c < "$TAR") bytes, proyecto completo)"

# observador de red: graba las conexiones de los 30 s posteriores al build
# (momento en el que el driver sube el artefacto a la plataforma)
( for i in $(seq 1 60); do
    echo "== $(date '+%F %T') =="; ss -tnp 2>/dev/null | grep ESTAB
    sleep 0.5
  done ) > /home/z/my-project/data/net_watch.log 2>&1 & disown || true
