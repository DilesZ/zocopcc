#!/usr/bin/env python3
"""Servidor local de la web de seguimiento Zococity vs PCComponentes.

    python3 server.py            → http://localhost:8765
    PORT=9000 python3 server.py

Endpoints:
    GET  /                  → interfaz (index.html)
    GET  /api/data          → data.json (última instantánea)
    GET  /api/status        → {running, phase, done, total, current, last_run, log}
    POST /api/refresh?limit=N&skip_search=1 → lanza el proceso en segundo plano
    POST /api/cancel        → solicita la parada del proceso en curso
    GET  /api/excel         → genera y descarga el Excel (requiere openpyxl)
Solo usa la librería estándar; el navegador lo aporta nodriver (pip install nodriver).
"""
import io, json, os, sys, threading, time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

PORT = int(os.environ.get('PORT', '8765'))

STATE = {
    'running': False,
    'phase': None, 'done': 0, 'total': 0, 'current': '',
    'last_run': None, 'last_result': None,
    'cancel': {'stop': False},
    'log': [],
    'started_at': None,
}
STATE_LOCK = threading.Lock()


def log(msg):
    line = f'{datetime.now().strftime("%H:%M:%S")} · {msg}'
    with STATE_LOCK:
        STATE['log'].append(line)
        if len(STATE['log']) > 300:
            STATE['log'] = STATE['log'][-300:]
    print(line, flush=True)


def worker(limit, skip_search):
    try:
        import pipeline
        def cb(phase, n, total, current):
            with STATE_LOCK:
                STATE.update(phase=phase, done=n, total=total, current=current)
        snap = pipeline.run(on_progress=cb, cancel=STATE['cancel'],
                            limit=limit, skip_search=skip_search)
        n_pcc = sum(1 for r in snap['products'] if r.get('in_pcc'))
        n_diff = sum(1 for r in snap['products']
                     if r.get('price_zoco') and r.get('price_pcc'))
        with STATE_LOCK:
            STATE['last_result'] = {
                'productos': len(snap['products']), 'en_pcc': n_pcc,
                'comparables': n_diff,
                'generado': snap.get('generated_at'),
                'fichas_directo': snap['meta'].get('n_fichas'),
                'zoco_directo': snap['meta'].get('n_zoco'),
            }
        log(f"Proceso terminado: {len(snap['products'])} productos · {n_pcc} en PCC · "
            f"fichas en directo: {snap['meta'].get('n_fichas')}")
    except Exception as e:
        log(f'ERROR en el proceso: {str(e)[:300]}')
        with STATE_LOCK:
            STATE['last_result'] = {'error': str(e)[:300]}
    finally:
        with STATE_LOCK:
            STATE['running'] = False
            STATE['phase'] = None
            STATE['last_run'] = datetime.now().isoformat(timespec='seconds')


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype='application/json; charset=utf-8', extra=None):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ('/', '/index.html'):
            try:
                html = open(os.path.join(BASE, 'index.html'), encoding='utf-8').read()
                self._send(200, html, 'text/html; charset=utf-8')
            except FileNotFoundError:
                self._json({'error': 'index.html no encontrado'}, 500)
        elif p == '/api/data':
            try:
                self._send(200, open(os.path.join(BASE, 'data.json'), 'rb').read())
            except FileNotFoundError:
                self._json({'generated_at': None, 'meta': {}, 'products': []})
        elif p == '/api/status':
            with STATE_LOCK:
                self._json({'running': STATE['running'], 'phase': STATE['phase'],
                            'done': STATE['done'], 'total': STATE['total'],
                            'current': STATE['current'], 'last_run': STATE['last_run'],
                            'last_result': STATE['last_result'],
                            'log': STATE['log'][-12:]})
        elif p == '/api/excel':
            self._excel()
        elif p == '/favicon.ico':
            self._send(204, b'', 'text/plain')
        else:
            self._json({'error': 'ruta desconocida'}, 404)

    def do_POST(self):
        p, _, qs = urlparse(self.path).path, None, urlparse(self.path).query
        params = parse_qs(qs)
        if p == '/api/refresh':
            with STATE_LOCK:
                if STATE['running']:
                    self._json({'ok': False, 'error': 'Ya hay un proceso en marcha'}, 409)
                    return
                limit = int(params.get('limit', ['0'])[0] or 0) or None
                skip = params.get('skip_search', ['0'])[0] == '1'
                STATE.update(running=True, phase='inicio', done=0, total=0, current='',
                             cancel={'stop': False}, started_at=datetime.now().isoformat(timespec='seconds'),
                             last_result=None)
            t = threading.Thread(target=worker, args=(limit, skip), daemon=True)
            t.start()
            self._json({'ok': True, 'limit': limit, 'skip_search': skip})
        elif p == '/api/cancel':
            with STATE_LOCK:
                STATE['cancel']['stop'] = True
            self._json({'ok': True, 'msg': 'parada solicitada; se detiene tras la ficha actual'})
        else:
            self._json({'error': 'ruta desconocida'}, 404)

    def _excel(self):
        try:
            import excel
            buf, fname = excel.build()
            self._send(200, buf.getvalue(),
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                       {'Content-Disposition': f'attachment; filename="{fname}"'})
        except ImportError as e:
            self._json({'error': f'openpyxl no instalado: {e}. Ejecuta: pip install openpyxl'}, 501)
        except Exception as e:
            self._json({'error': str(e)[:300]}, 500)


def main():
    try:
        srv = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    except OSError as e:
        print(f'ERROR: el puerto {PORT} ya está en uso ({e}).', file=sys.stderr)
        print(f'Arranca en otro puerto:', file=sys.stderr)
        print('  Linux/macOS:  PORT=9000 python3 server.py', file=sys.stderr)
        print('  Windows:      set PORT=9000 && python server.py', file=sys.stderr)
        sys.exit(1)
    url = f'http://localhost:{PORT}'
    log(f'Servidor listo en {url}  (Ctrl+C para detener)')
    log('IMPORTANTE: usa esta URL; no abras index.html con doble clic ni con Live Server (el botón necesita este backend)')
    if os.environ.get('AUTO_OPEN', '1') != '0':
        threading.Timer(0.8, lambda: _open_browser(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log('Servidor detenido')


def _open_browser(url):
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass  # sin navegador gráfico (SSH, servidor…): abre la URL a mano


if __name__ == '__main__':
    main()
