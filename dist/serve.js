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
