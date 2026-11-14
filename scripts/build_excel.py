#!/usr/bin/env python3
"""Genera el Excel comparativo Zococity vs PCComponentes siguiendo el design system del skill xlsx."""
import json, sys, os
from datetime import date

XLSX_SKILL_DIR = '/home/z/my-project/skills/xlsx'
for sub in [XLSX_SKILL_DIR, os.path.join(XLSX_SKILL_DIR, 'templates')]:
    if sub not in sys.path:
        sys.path.insert(0, sub)
from base import (FONT_NAME, HEADER_BOLD, PRIMARY, SECONDARY, ACCENT_POSITIVE, ACCENT_NEGATIVE,
                  ACCENT_WARNING, NEUTRAL_900, NEUTRAL_600, NEUTRAL_200, NEUTRAL_100, NEUTRAL_0,
                  CF_POSITIVE_FILL, CF_POSITIVE_FONT, CF_NEGATIVE_FILL, CF_NEGATIVE_FONT,
                  font_title, font_header, font_subheader, font_body, font_caption,
                  fill_header, fill_total, fill_data_row, border_header, border_total,
                  align_title, align_header, align_number, align_text,
                  setup_sheet, style_header_row, style_data_row, style_total_row,
                  auto_fit_columns, ROW_HEIGHTS)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import CellIsRule
from openpyxl.utils import get_column_letter

DATA = '/home/z/my-project/data/final_dataset.json'
OUT = '/home/z/my-project/download/Comparativa_Zococity_vs_PCComponentes.xlsx'
HOY = '14/11/2026'

CAT_ORDER = ['Auriculares HiFi', 'Auriculares Bluetooth', 'DAC / Amplificador',
             'Amplificador integrado', 'Tocadiscos', 'Altavoces activos',
             'Altavoz Bluetooth', 'Barra de sonido', 'Streamers / En red',
             'Receptor AV', 'Reproductor CD']


def stock_txt(v):
    if v is True:
        return 'En stock'
    if v is False:
        return 'Agotado'
    return '—'


def disp_pcc(rec):
    if not rec.get('in_pcc'):
        txt = 'No disponible en PCComponentes'
        if rec.get('note_pcc'):
            txt += f" · {rec['note_pcc']}"
        return txt
    f = rec.get('pcc_flags') or {}
    parts = []
    if f.get('agotado'):
        parts.append('Agotado (según índice)')
    if f.get('vendido_pcc'):
        parts.append('Vendido y enviado por PCComponentes')
    if f.get('envio_gratis'):
        parts.append('Envío gratis')
    if f.get('entrega'):
        parts.append('Entrega rápida')
    if not parts:
        parts.append('En venta (ver ficha)')
    txt = ' · '.join(parts)
    if rec.get('note_pcc'):
        txt += f" · {rec['note_pcc']}"
    return txt


def short_url(u):
    if not u:
        return '—'
    u = u.replace('https://www.pccomponentes.com/', 'pccomponentes.com/')
    u = u.replace('https://zococity.es/', 'zococity.es/')
    return u if len(u) <= 48 else u[:45] + '…'


def main():
    recs = json.load(open(DATA))
    # ordenar por categoría y precio
    recs.sort(key=lambda r: (CAT_ORDER.index(r['cat']) if r['cat'] in CAT_ORDER else 99, r.get('price_zoco') or 0))

    wb = Workbook()

    # ================= Hoja 1: Comparativa =================
    ws = wb.active
    ws.title = 'Comparativa'
    headers = ['Categoría', 'Marca', 'Producto (Zococity)', 'Ref. Zococity', 'EAN',
               'Precio Zococity (€)', 'Stock Zococity', '¿En PCComponentes?',
               'Producto (PCComponentes)', 'Cod. art. PCC', 'Precio PCC (€)',
               'Dif. € (Zoco − PCC)', 'Dif. %', 'Más barato en',
               'Disponibilidad PCC', 'Fuente del dato PCC', 'Ficha PCC', 'Ficha Zococity']
    last_col = len(headers) + 1  # B.. => 2..19
    setup_sheet(ws, title='Comparativa de precios · Zococity vs PCComponentes · Catálogo de audio', last_col=last_col)
    ws.row_dimensions[3].height = 14
    c3 = ws.cell(row=3, column=2,
                 value=f'Consulta realizada el {HOY} · Precios con IVA · PCComponentes obtenido del índice de búsqueda (fichas y Google Shopping, últimos 90 días) · Ver hoja «Metodología»')
    c3.font = font_caption()
    ws.merge_cells(start_row=3, start_column=2, end_row=3, end_column=last_col)

    for i, h in enumerate(headers, start=2):
        ws.cell(row=4, column=i, value=h)
    style_header_row(ws, 4, 2, last_col)

    r0 = 5
    for idx, rec in enumerate(recs):
        r = r0 + idx
        pz = rec.get('price_zoco')
        pp = rec.get('price_pcc')
        ws.cell(row=r, column=2, value=rec['cat'])
        ws.cell(row=r, column=3, value=rec['brand'])
        ws.cell(row=r, column=4, value=rec['title_zoco'])
        ws.cell(row=r, column=5, value=rec.get('sku_zoco') or '—')
        ean = rec.get('ean')
        ws.cell(row=r, column=6, value=ean if ean else '—')
        cG = ws.cell(row=r, column=7, value=pz if pz is not None else None)
        ws.cell(row=r, column=8, value=stock_txt(rec.get('stock_zoco')))
        ws.cell(row=r, column=9, value='Sí' if rec.get('in_pcc') else 'No')
        ws.cell(row=r, column=10, value=(rec.get('title_pcc') or '—'))
        ws.cell(row=r, column=11, value=rec.get('code_pcc') or '—')
        cL = ws.cell(row=r, column=12, value=pp if pp is not None else None)
        cM = ws.cell(row=r, column=13,
                     value=f'=IF(OR($L{r}="",$G{r}=""),"",ROUND($G{r}-$L{r},2))')
        cN = ws.cell(row=r, column=14,
                     value=f'=IF(OR($L{r}="",$L{r}=0,$G{r}=""),"",ROUND(($G{r}-$L{r})/$L{r},4))')
        ws.cell(row=r, column=15,
                value=(f'=IF($L{r}="","No comparable en PCC",IF($G{r}="","Solo PCComponentes",'
                       f'IF($G{r}<$L{r},"Zococity",IF($L{r}<$G{r},"PCComponentes","Empate"))))'))
        ws.cell(row=r, column=16, value=disp_pcc(rec))
        ws.cell(row=r, column=17, value=rec.get('source_pcc') or '—')
        # URLs con hipervínculo
        cR = ws.cell(row=r, column=18, value=short_url(rec.get('url_pcc')))
        if rec.get('url_pcc'):
            cR.hyperlink = rec['url_pcc']
        cS = ws.cell(row=r, column=19, value=short_url(rec.get('url_zoco')))
        if rec.get('url_zoco'):
            cS.hyperlink = rec['url_zoco']
        # estilos
        style_data_row(ws, r, 2, last_col, idx)
        for col in (7, 12, 13):
            ws.cell(row=r, column=col).alignment = align_number()
            ws.cell(row=r, column=col).number_format = '#,##0.00\\ "€"'
        for col in (14,):
            ws.cell(row=r, column=col).alignment = align_number()
            ws.cell(row=r, column=col).number_format = '+0.0%;-0.0%;0.0%'
        ws.cell(row=r, column=6).alignment = align_number()
        ws.cell(row=r, column=11).alignment = align_number()
        for col in (18, 19):
            ws.cell(row=r, column=col).font = font_caption()
        if rec.get('in_pcc') and rec.get('code_pcc'):
            ws.cell(row=r, column=11).font = font_body()
        ws.cell(row=r, column=9).alignment = Alignment(horizontal='center', vertical='center')
        ws.cell(row=r, column=8).alignment = Alignment(horizontal='center', vertical='center')

    n = len(recs)
    last_data = r0 + n - 1
    # fila resumen
    tr = last_data + 1
    ws.cell(row=tr, column=2, value='Resumen')
    ws.cell(row=tr, column=3, value=f'{n} productos')
    ws.cell(row=tr, column=7, value=f'=COUNT(G{r0}:G{last_data})')
    ws.cell(row=tr, column=9, value=f'=COUNTIF(I{r0}:I{last_data},"Sí")')
    ws.cell(row=tr, column=12, value=f'=COUNT(L{r0}:L{last_data})')
    ws.cell(row=tr, column=13, value=f'=IFERROR(ROUND(AVERAGE(M{r0}:M{last_data}),2),"")')
    ws.cell(row=tr, column=14, value=f'=IFERROR(ROUND(AVERAGE(N{r0}:N{last_data}),4),"")')
    style_total_row(ws, tr, 2, last_col)
    for col in (7, 12, 13):
        ws.cell(row=tr, column=col).alignment = align_number()
        ws.cell(row=tr, column=col).number_format = '#,##0.00\\ "€"'
    ws.cell(row=tr, column=14).alignment = align_number()
    ws.cell(row=tr, column=14).number_format = '+0.0%;-0.0%;0.0%'
    ws.cell(row=tr, column=9).alignment = Alignment(horizontal='center', vertical='center')

    # formato condicional Dif € y Dif %
    rngM = f'M{r0}:M{last_data}'
    rngN = f'N{r0}:N{last_data}'
    for rng in (rngM, rngN):
        ws.conditional_formatting.add(rng, CellIsRule(operator='greaterThan', formula=['0'],
                                                      fill=CF_POSITIVE_FILL, font=CF_POSITIVE_FONT))
        ws.conditional_formatting.add(rng, CellIsRule(operator='lessThan', formula=['0'],
                                                      fill=CF_NEGATIVE_FILL, font=CF_NEGATIVE_FONT))
    # nota al pie
    note = ws.cell(row=tr + 2, column=2,
                   value='Lectura de la diferencia: positiva = PCComponentes más barato que Zococity; negativa = Zococity más barato. '
                         '«No comparable en PCC» = producto en catálogo de PCComponentes pero sin precio publicado por el índice, o no localizado en PCComponentes.')
    note.font = font_caption()
    ws.merge_cells(start_row=tr + 2, start_column=2, end_row=tr + 2, end_column=last_col)

    ws.freeze_panes = 'E5'
    auto_fit_columns(ws, min_width=8, max_width=30, header_row=4, data_start_row=r0)
    for col, w in {'D': 30, 'J': 30, 'P': 30, 'R': 30, 'S': 30, 'Q': 22, 'B': 20, 'C': 13}.items():
        ws.column_dimensions[col].width = w
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = '4:4'

    # ================= Hoja 2: Resumen =================
    rs = wb.create_sheet('Resumen')
    setup_sheet(rs, title='Resumen de la comparativa', last_col=8)
    rs.row_dimensions[3].height = 14
    k3 = rs.cell(row=3, column=2, value=f'Cálculos automáticos sobre la hoja «Comparativa» · {HOY}')
    k3.font = font_caption()
    rngI = f'Comparativa!I{r0}:I{last_data}'
    rngO = f'Comparativa!O{r0}:O{last_data}'
    rngN = f'Comparativa!N{r0}:N{last_data}'
    rngG = f'Comparativa!G{r0}:G{last_data}'
    rngL = f'Comparativa!L{r0}:L{last_data}'
    kpis = [
        ('Productos analizados', f'=COUNTA(Comparativa!D{r0}:D{last_data})', '#,##0'),
        ('Disponibles también en PCComponentes', f'=COUNTIF({rngI},"Sí")', '#,##0'),
        ('No localizados en PCComponentes', f'=COUNTIF({rngI},"No")', '#,##0'),
        ('En PCC sin precio verificable', f'=COUNTIFS({rngI},"Sí",{rngL},"")', '#,##0'),
        ('Zococity más barato', f'=COUNTIF({rngO},"Zococity")', '#,##0'),
        ('PCComponentes más barato', f'=COUNTIF({rngO},"PCComponentes")', '#,##0'),
        ('Diferencia media (PCC sobre Zococity)', f'=IFERROR(ROUND(AVERAGE({rngN}),4),"—")', '+0.0%;-0.0%;0.0%'),
        ('Precio medio en Zococity', f'=IFERROR(ROUND(AVERAGE({rngG}),2),"—")', '#,##0.00\\ "€"'),
        ('Precio medio en PCComponentes', f'=IFERROR(ROUND(AVERAGE({rngL}),2),"—")', '#,##0.00\\ "€"'),
    ]
    row = 4
    for label, formula, fmt in kpis:
        lab = rs.cell(row=row, column=2, value=label)
        lab.font = font_body()
        val = rs.cell(row=row, column=4, value=formula)
        val.font = font_subheader()
        val.number_format = fmt
        val.alignment = align_number()
        row += 1
    # tabla por categoría
    row += 2
    hd = rs.cell(row=row, column=2, value='Desglose por categoría')
    hd.font = font_subheader()
    row += 1
    cat_headers = ['Categoría', 'Productos', 'En ambas', 'Dif. media %']
    for i, h in enumerate(cat_headers, start=2):
        rs.cell(row=row, column=i, value=h)
    style_header_row(rs, row, 2, 5)
    hdr_row = row
    row += 1
    cats = {}
    for rec in recs:
        cats.setdefault(rec['cat'], []).append(rec)
    idx = 0
    for cat, lst in sorted(cats.items(), key=lambda kv: CAT_ORDER.index(kv[0]) if kv[0] in CAT_ORDER else 99):
        rs.cell(row=row, column=2, value=cat)
        rs.cell(row=row, column=3, value=len(lst))
        rs.cell(row=row, column=4, value=sum(1 for x in lst if x.get('in_pcc')))
        # dif media de la categoría como valor calculado (verificable)
        diffs = []
        for x in lst:
            if x.get('in_pcc') and x.get('price_pcc') and x.get('price_zoco'):
                diffs.append((x['price_zoco'] - x['price_pcc']) / x['price_pcc'])
        val = round(sum(diffs) / len(diffs), 4) if diffs else None
        c = rs.cell(row=row, column=5, value=val if val is not None else '—')
        c.number_format = '+0.0%;-0.0%;0.0%'
        style_data_row(rs, row, 2, 5, idx)
        for col in (3, 4, 5):
            rs.cell(row=row, column=col).alignment = align_number()
        idx += 1
        row += 1
    # top 5 mayores diferencias (valores calculados)
    row += 2
    hd2 = rs.cell(row=row, column=2, value='Top 5 mayores diferencias (|dif. %|)')
    hd2.font = font_subheader()
    row += 1
    top_headers = ['Producto', 'Precio Zococity (€)', 'Precio PCC (€)', 'Dif. %']
    for i, h in enumerate(top_headers, start=2):
        rs.cell(row=row, column=i, value=h)
    style_header_row(rs, row, 2, 5)
    row += 1
    ranked = [x for x in recs if x.get('in_pcc') and x.get('price_pcc') and x.get('price_zoco')]
    ranked.sort(key=lambda x: abs((x['price_zoco'] - x['price_pcc']) / x['price_pcc']), reverse=True)
    for i, x in enumerate(ranked[:5]):
        rs.cell(row=row, column=2, value=x['title_zoco'][:44])
        rs.cell(row=row, column=3, value=x['price_zoco']).number_format = '#,##0.00\\ "€"'
        rs.cell(row=row, column=4, value=x['price_pcc']).number_format = '#,##0.00\\ "€"'
        rs.cell(row=row, column=5, value=round((x['price_zoco'] - x['price_pcc']) / x['price_pcc'], 4)).number_format = '+0.0%;-0.0%;0.0%'
        style_data_row(rs, row, 2, 5, i)
        for col in (3, 4, 5):
            rs.cell(row=row, column=col).alignment = align_number()
        row += 1
    auto_fit_columns(rs, min_width=8, max_width=34, header_row=hdr_row, data_start_row=hdr_row + 1)

    # ================= Hoja 3: Metodología =================
    mt = wb.create_sheet('Metodología')
    setup_sheet(mt, title='Metodología y fuentes', last_col=8)
    lines = [
        ('Qué contiene este archivo', ''),
        ('', 'Comparativa de precios y referencias entre Zococity.es y PCComponentes.com sobre 54 productos de audio '
             '(auriculares, DACs, amplificadores, tocadiscos, altavoces, barras de sonido, streamers, receptores AV y reproductores de CD).'),
        ('Datos de Zococity', ''),
        ('', f'Obtenidos directamente de la tienda el {HOY}: catálogo JSON de Shopify por colección (título, marca, precio, disponibilidad) '
             'y ficha individual de cada producto para extraer la referencia interna (SKU) y el código EAN. '
             'Todos los precios incluyen IVA; la disponibilidad es la que muestra la propia web.'),
        ('Datos de PCComponentes', ''),
        ('', f'PCComponentes bloquea el acceso directo automatizado (Cloudflare), por lo que los precios se obtuvieron el {HOY} del índice de búsqueda '
             '(fichas oficiales de PCComponentes y tarjetas de Google Shopping que muestran «Vendido y enviado por PCComponentes»). '
             'Cada precio conserva la fuente en la columna «Fuente del dato PCC» y la ficha enlazada en la columna «Ficha PCC».'),
        ('Advertencias', ''),
        ('', '1) Los precios de PCComponentes proceden de la última indexación de Google y pueden diferir del precio vigente en la web '
             '(ofertas relámpago, cupones, precios de marketplace de otros vendedores). Verifica el precio final en la ficha enlazada antes de comprar.'),
        ('', '2) No se incluyen gastos de envío ni promociones por puntos o financiación de ninguna de las dos tiendas.'),
        ('', '3) El «Cod. art. PCC» es la referencia interna de PCComponentes y solo se muestra cuando el índice la publica; '
             'el EAN sirve como referencia exacta común a ambas tiendas.'),
        ('', '4) «Solo Zococity» significa que el producto no se localizó en PCComponentes el día de la consulta (puede existir en otras tiendas).'),
        ('Significado de las columnas', ''),
        ('', 'Dif. € = Precio Zococity − Precio PCC. Dif. % = Dif. € / Precio PCC. '
             'Positivo: PCComponentes es más barato. Negativo: Zococity es más barato. '
             'La hoja «Review» incluye comprobaciones automáticas de integridad de los datos.'),
    ]
    r = 4
    for head, body in lines:
        if head:
            c = mt.cell(row=r, column=2, value=head)
            c.font = font_subheader()
            r += 1
        if body:
            c = mt.cell(row=r, column=2, value=body)
            c.font = font_body()
            c.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
            mt.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
            mt.row_dimensions[r].height = max(30, 15 * (len(body) // 95 + 1))
            r += 1
        r += 0
    for col, w in {'B': 95}.items():
        mt.column_dimensions[col].width = w

    # ================= Hoja 4: Review =================
    rv = wb.create_sheet('Review')
    rv.sheet_properties.tabColor = 'FFC000'
    setup_sheet(rv, title='Review · comprobaciones de integridad', last_col=6)
    checks = [
        ['Comprobación', 'Esperado', 'Real', 'Estado'],
        ['Nº de filas de datos', n, f'=COUNTA(Comparativa!D{r0}:D{last_data})', '=IF(C5=D5,"✓ PASS","✗ FAIL")'],
        ['Filas con precio Zococity', n, f'=COUNT(Comparativa!G{r0}:G{last_data})', '=IF(C6=D6,"✓ PASS","✗ FAIL")'],
        ['Productos en ambas tiendas', sum(1 for x in recs if x.get('in_pcc')), f'=COUNTIF(Comparativa!I{r0}:I{last_data},"Sí")', '=IF(C7=D7,"✓ PASS","✗ FAIL")'],
        ['Filas con precio PCC', sum(1 for x in recs if x.get('price_pcc')), f'=COUNT(Comparativa!L{r0}:L{last_data})', '=IF(C8=D8,"✓ PASS","✗ FAIL")'],
        ['Precio mínimo Zococity > 0', 'VERDADERO', f'=MIN(Comparativa!G{r0}:G{last_data})>0', '=IF(D9=TRUE,"✓ PASS","✗ FAIL")'],
        ['Dif. % media coherente', round(sum((x['price_zoco'] - x['price_pcc']) / x['price_pcc'] for x in recs if x.get('price_pcc')) / max(1, sum(1 for x in recs if x.get('price_pcc'))), 4), '=Comparativa!N' + str(tr), '=IF(ABS(C10-D10)<0.001,"✓ PASS","✗ FAIL")'],
    ]
    for i, rowvals in enumerate(checks):
        rr = 4 + i
        for j, v in enumerate(rowvals):
            rv.cell(row=rr, column=2 + j, value=v)
        if i == 0:
            style_header_row(rv, rr, 2, 5)
        else:
            style_data_row(rv, rr, 2, 5, i - 1)
    auto_fit_columns(rv, min_width=10, max_width=34, header_row=4, data_start_row=5)

    wb.properties.creator = 'Z.ai'
    wb.save(OUT)
    print('GUARDADO:', OUT, '| filas:', n)


if __name__ == '__main__':
    main()
