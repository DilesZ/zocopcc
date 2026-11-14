#!/usr/bin/env python3
"""Muestra los eventos del log del driver desde una hora dada, destacando errores y deploy."""
import json
import sys

path = '/home/z/.zcode/cli/log/zcode-2026-11-14.jsonl'
desde = sys.argv[1] if len(sys.argv) > 1 else '2026-11-14T19:'
eventos = []
for line in open(path, encoding='utf-8', errors='ignore'):
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get('timestamp', '') >= desde:
        eventos.append(d)

print('entradas desde', desde, ':', len(eventos))
for d in eventos:
    lvl = d.get('level', 'info')
    ev = d.get('event', d.get('module', ''))
    msg = (d.get('message') or '')[:120]
    hh = d['timestamp'][11:19]
    marca = ' <<< ' if (lvl == 'error' or 'deploy' in (ev + ' ' + msg).lower()) else ''
    print(f"{hh} [{lvl}] {ev} · {msg}{marca}")
    if marca:
        ctx = json.dumps(d.get('context', {}), ensure_ascii=False)[:400]
        if ctx != '{}':
            print('   ctx:', ctx)
