#!/usr/bin/env python3
"""Diagnóstico en SOLO-LECTURA de la BD de negocio de la plataforma.
Busca el registro del espacio 'zocopcc' y su error de deploy.
NUNCA imprime la cadena de conexión ni credenciales."""
import os
import sys

import psycopg2
import psycopg2.extras

# leer DATABASE_URL del entorno guardado (sin imprimirlo)
url = None
for line in open('/home/z/my-project/data/env.disabled', encoding='utf-8'):
    line = line.strip()
    if line.startswith('DATABASE_URL='):
        url = line.split('=', 1)[1].strip().strip('"').strip("'")
if not url:
    sys.exit('DATABASE_URL no encontrada')

con = psycopg2.connect(url)
cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# 1) tablas disponibles
cur.execute("""SELECT table_name FROM information_schema.tables
               WHERE table_schema='public' ORDER BY table_name""")
tablas = [r['table_name'] for r in cur.fetchall()]
print('TABLAS:', ', '.join(tablas))

# 2) buscar 'zocopcc' en tablas candidatas
candidatas = [t for t in tablas if any(k in t.lower() for k in
              ('space', 'deploy', 'publish', 'site', 'web', 'build', 'chat', 'project'))]
print('\nCANDIDATAS:', ', '.join(candidatas) or '(ninguna)')

for t in candidatas:
    try:
        cur.execute(f"SELECT * FROM {t} ORDER BY 1 DESC LIMIT 3")
        filas = cur.fetchall()
    except Exception as e:
        print(f'\n-- {t}: ERROR {e}')
        continue
    if not filas:
        continue
    print(f'\n-- {t} (últimas {len(filas)}):')
    print('   columnas:', ', '.join(filas[0].keys()))
    for f in filas:
        s = {k: (str(v)[:180] if v is not None else None) for k, v in f.items()}
        print('   ', s)

# 3) búsqueda amplia del slug en columnas de texto de todas las tablas
print('\nBÚSQUEDA "zocopcc":')
for t in tablas:
    try:
        cur.execute(f"""SELECT column_name FROM information_schema.columns
                        WHERE table_name=%s AND table_schema='public'""", (t,))
        cols = [r['column_name'] for r in cur.fetchall()]
        textcols = [c for c in cols]
        for c in textcols:
            try:
                cur.execute(f"SELECT COUNT(*) AS n FROM {t} WHERE {c}::text LIKE %s", ('%zocopcc%',))
                n = cur.fetchone()['n']
                if n:
                    print(f'   {t}.{c}: {n} filas')
                    cur.execute(f"SELECT * FROM {t} WHERE {c}::text LIKE %s LIMIT 2", ('%zocopcc%',))
                    for f in cur.fetchall():
                        print('   ', {k: (str(v)[:200] if v is not None else None) for k, v in f.items()})
            except Exception:
                pass
    except Exception:
        pass

con.close()
print('\n(solo lecturas SELECT; conexión cerrada)')
