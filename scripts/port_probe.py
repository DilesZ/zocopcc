#!/usr/bin/env python3
"""Detecta qué puerto local usa Caddy (:81) como upstream: sirve en varios puertos
y registra cada petición entrante."""
import socket, threading, sys, time

PORTS = [3000, 8000, 8080, 8081, 5000, 5001, 4200, 19002, 19003, 19004, 19007, 19008]
hits = {}
lock = threading.Lock()


def serve(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', port))
        s.listen(8)
    except OSError as e:
        print(f'[{port}] no disponible: {e}', flush=True)
        return
    while True:
        try:
            c, a = s.accept()
        except OSError:
            return
        c.settimeout(2)
        try:
            data = c.recv(4096).decode('utf-8', 'ignore')
        except Exception:
            data = ''
        with lock:
            hits.setdefault(port, []).append(data.split('\r\n')[0])
            print(f'>>> PETICIÓN en puerto {port} desde {a}: {data.split(chr(13)+chr(10))[0]}', flush=True)
        body = b'<html><body><h1>PUBLISHED-OK port %d</h1></body></html>' % port
        c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: ' +
                  str(len(body)).encode() + b'\r\nConnection: close\r\n\r\n' + body)
        c.close()


for p in PORTS:
    threading.Thread(target=serve, args=(p,), daemon=True).start()

time.sleep(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
print('RESUMEN:', {k: v[:3] for k, v in hits.items()}, flush=True)
