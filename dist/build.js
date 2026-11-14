// build: copia la web estática a out/
const fs = require('fs');
fs.mkdirSync('out', {recursive: true});
for (const f of ['index.html', 'data.json']) {
  if (fs.existsSync(f)) fs.copyFileSync(f, 'out/' + f);
}
console.log('build OK: out/index.html + out/data.json');
