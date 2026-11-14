// Búsqueda en PCComponentes con fingerprint de Chrome real
// Uso: node pcc_search.js "consulta" [archivo_salida]
const path = require('path');
const fs = require('fs');

function resolvePlaywright() {
  const roots = [
    '/home/z/.npm-global/lib/node_modules',
    '/usr/lib/node_modules',
  ];
  for (const r of roots) {
    const p = path.join(r, 'playwright');
    if (fs.existsSync(p)) return require(p);
  }
  throw new Error('playwright no encontrado');
}

const { chromium } = resolvePlaywright();

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36';

async function main() {
  const query = process.argv[2] || 'fiio ft1';
  const outFile = process.argv[3];

  const browser = await chromium.launch({
    headless: process.env.PCC_HEADED === '1' ? false : true,
    executablePath: '/home/z/.cache/puppeteer/chrome/linux-157.0.8103.50/chrome-linux64/chrome',
    args: ['--disable-blink-features=AutomationControlled', '--no-sandbox'],
  });
  const ctx = await browser.newContext({
    userAgent: UA,
    locale: 'es-ES',
    timezoneId: 'Europe/Madrid',
    viewport: { width: 1920, height: 1080 },
    extraHTTPHeaders: { 'Accept-Language': 'es-ES,es;q=0.9,en;q=0.5' },
  });
  await ctx.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });
  const page = await ctx.newPage();
  const url = 'https://www.pccomponentes.com/buscar/?query=' + encodeURIComponent(query);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  // esperar a que pase el reto CF
  for (let i = 0; i < 45; i++) {
    const t = await page.title();
    if (!/just a moment|attention required|verify/i.test(t)) break;
    await page.waitForTimeout(2500);
  }
  await page.waitForTimeout(4000);
  const title = await page.title();

  // extraer tarjetas de producto genéricas
  const items = await page.evaluate(() => {
    const seen = new Map();
    document.querySelectorAll('a[href]').forEach(a => {
      const href = a.href || '';
      if (!href.includes('pccomponentes.com/')) return;
      // URLs de producto: sin /buscar /categorias /marcas etc.
      const u = new URL(href);
      const segs = u.pathname.split('/').filter(Boolean);
      if (segs.length === 0) return;
      const banned = ['buscar', 'categorias', 'marcas', 'grupos', 'blog', 'cookies', 'empresa', 'comunidad', 'informacion', 'mi-cuenta', 'carrito', 'checkout', 'login', 'register', 'wishlist', 'configurador', 'outlet', 'reacondicionado'];
      if (banned.some(b => segs[0] === b || segs[0].startsWith('?'))) return;
      if (u.pathname.includes('#')) return;
      const txt = (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim();
      if (!txt || txt.length < 8) return;
      if (!seen.has(u.pathname)) seen.set(u.pathname, txt.slice(0, 220));
    });
    return Array.from(seen, ([path, text]) => ({ path, text }));
  });

  const result = { query, url, title, count: items.length, items: items.slice(0, 30) };
  console.log('TITULO:', title);
  console.log('ITEMS:', items.length);
  console.log(JSON.stringify(result.items.slice(0, 8), null, 1));
  if (outFile) fs.writeFileSync(outFile, JSON.stringify(result, null, 1), 'utf-8');
  await browser.close();
}

main().catch(e => { console.error('ERROR:', e.message); process.exit(1); });
