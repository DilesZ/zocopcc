#!/usr/bin/env python3
"""Genera el Excel comparativo a partir de data.json (requiere openpyxl: pip install openpyxl)."""
import io, json, os
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data.json')

CAT_ORDER = ['Auriculares HiFi', 'Auriculares Bluetooth', 'DAC / Amplificador',
             'Amplificador integrado', 'Tocadiscos', 'Altavoces activos',
             'Altavoz Bluetooth', 'Barra de sonido', 'Streamers / En red',
             'Receptor AV', 'Reproductor CD']

HEADERS = ['Categoría', 'Marca', 'Producto (Zococity)', 'Ref. Zoco', 'EAN',
           'Precio Zococity (€)', 'Stock Zococity', '¿En PCC?', 'Producto PCC',
           'Cod. art. PCC', 'Vendedor PCC', 'Precio PCC (€)', 'Precio Carrefour (€)', 'Vendedor Carrefour',
           'Stock Carrefour', 'Fuente Carrefour', 'Ficha Carrefour', 'Precio Fnac (€)', 'Vendedor Fnac',
           'Stock Fnac', 'Fuente Fnac', 'Ficha Fnac', 'Dif. €', 'Dif. %', 'Más barato en',
           'Disponibilidad PCC', 'Fuente del dato PCC', 'Ficha PCC', 'Ficha Zoco']

GREEN = 'C6EFCE'; GREEN_F = '006100'; BLUE = 'DDEBF7'; BLUE_F = '1F4E78'
GRAY = 'F2F2F2'; DARK = '203864'; ORANGE = 'FFF2CC'


def fmt_eur(v):
    return float(v) if v is not None else None


def build():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    data = json.load(open(DATA, encoding='utf-8'))
    recs = data.get('products') or []
    recs.sort(key=lambda r: (CAT_ORDER.index(r['cat']) if r.get('cat') in CAT_ORDER else 99,
                             r.get('price_zoco') or 0))
    gen = (data.get('generated_at') or '')[:16].replace('T', ' ')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Comparativa'
    ws.sheet_properties.tabColor = DARK[2:] if DARK.startswith('#') else '203864'

    # Título
    ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=len(HEADERS) + 1)
    c = ws.cell(row=1, column=2, value='Comparativa de precios · Zococity, PCComponentes, Carrefour y Fnac')
    c.font = Font(bold=True, size=14, color=DARK)
    ws.merge_cells(start_row=2, start_column=2, end_row=2, end_column=len(HEADERS) + 1)
    c2 = ws.cell(row=2, column=2, value=f'Generado el {gen} · Precios con IVA · Fuente: fichas oficiales de pccomponentes.com (navegador automatizado que supera Cloudflare)')
    c2.font = Font(size=9, color='666666')

    # Cabecera
    r0 = 4
    for i, h in enumerate(HEADERS, start=2):
        cell = ws.cell(row=r0, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF', size=10)
        cell.fill = PatternFill('solid', fgColor=DARK)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = Border(*[Side(style='thin', color='B0B0B0')] * 4)
    ws.row_dimensions[r0].height = 30

    def disp_pcc(r):
        if not r.get('in_pcc'):
            return 'No disponible en PCComponentes' + (f" · {r['note_pcc']}" if r.get('note_pcc') else '')
        parts = []
        seller = r.get('seller_pcc')
        av = r.get('pcc_avail')
        if seller:
            tag = 'PCComponentes (propio)' if 'pccomponentes' in seller.lower() else seller
            av_txt = {'InStock': 'en stock', 'OutOfStock': 'agotado'}.get(av, '')
            parts.append(f'Vendido por {tag}' + (f' · {av_txt}' if av_txt else ''))
        else:
            parts.append('En venta (ver ficha)')
        if (r.get('source_pcc') or '').startswith('Ficha') and r.get('pcc_avail') == 'InStock':
            parts.append('Envío gratis')
        txt = ' · '.join(parts)
        if r.get('note_pcc'):
            txt += f" · {r['note_pcc']}"
        return txt

    row = r0 + 1
    for idx, r in enumerate(recs):
        pz = fmt_eur(r.get('price_zoco'))
        competitors = [(name, fmt_eur(r.get('price_' + key))) for name, key in [('PCComponentes','pcc'),('Carrefour','carrefour'),('Fnac','fnac')]]
        competitors = [(name, price) for name, price in competitors if price is not None]
        best_name, best_price = min(competitors, key=lambda x: x[1]) if competitors else (None, None)
        dif = (pz - best_price) if (pz is not None and best_price is not None) else None
        difp = (dif / best_price) if dif is not None and best_price else None
        mejor = ('Empate' if dif == 0 else best_name if dif > 0 else 'Zococity') if dif is not None else None
        vals = [r.get('cat'), r.get('brand'), r.get('title_zoco'), r.get('sku_zoco'), r.get('ean'),
                pz, 'En stock' if r.get('stock_zoco') else ('Agotado' if r.get('stock_zoco') is False else '—'),
                'Sí' if r.get('in_pcc') else 'No', r.get('title_pcc'), r.get('code_pcc'),
                r.get('seller_pcc'), fmt_eur(r.get('price_pcc')), fmt_eur(r.get('price_carrefour')), r.get('seller_carrefour'),
                ('En stock' if r.get('stock_carrefour') is True else 'Agotado' if r.get('stock_carrefour') is False else '—'), r.get('source_carrefour') or '—', r.get('url_carrefour') or '—',
                fmt_eur(r.get('price_fnac')), r.get('seller_fnac'), ('En stock' if r.get('stock_fnac') is True else 'Agotado' if r.get('stock_fnac') is False else '—'), r.get('source_fnac') or '—', r.get('url_fnac') or '—', dif, difp, mejor, disp_pcc(r),
                r.get('source_pcc') or '—',
                (r.get('url_pcc') or '—').replace('https://www.pccomponentes.com/', 'pccomponentes.com/'),
                r.get('url_zoco', '').replace('https://zococity.es/', 'zococity.es/')]
        for i, v in enumerate(vals, start=2):
            cell = ws.cell(row=row, column=i, value=v)
            cell.font = Font(size=10)
            cell.border = Border(*[Side(style='thin', color='DDDDDD')] * 4)
            if idx % 2 == 0:
                cell.fill = PatternFill('solid', fgColor=GRAY)
            if i in (7, 13, 14) and v is not None:
                cell.number_format = '€#,##0.00'
            if i == 15 and v is not None:
                cell.number_format = '+0.0%;-0.0%;0.0%'
            if i == 2:
                cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            if i == 10:
                cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            if i == 17:
                cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            if i == 16 and v == 'Zococity':
                cell.fill = PatternFill('solid', fgColor=GREEN)
                cell.font = Font(size=10, color=GREEN_F, bold=True)
            elif i == 16 and v == 'PCComponentes':
                cell.fill = PatternFill('solid', fgColor=BLUE)
                cell.font = Font(size=10, color=BLUE_F, bold=True)
            elif i == 9 and v == 'No':
                cell.font = Font(size=10, color='999999', italic=True)
        row += 1
    last = row - 1

    # Totales / KPIs
    row += 1
    import statistics
    pz_list = [r.get('price_zoco') for r in recs if r.get('price_zoco')]
    pp_list = [r.get('price_pcc') for r in recs if r.get('price_pcc')]
    difp_list = []
    for r in recs:
        pz, pp = fmt_eur(r.get('price_zoco')), fmt_eur(r.get('price_pcc'))
        if pz and pp:
            difp_list.append((pz - pp) / pp)
    zoco_cheaper = 0
    rival_cheaper = 0
    same = 0
    with_comparison = 0
    for r in recs:
        z = fmt_eur(r.get('price_zoco'))
        rival_prices = [fmt_eur(r.get('price_' + key)) for key in ('pcc', 'carrefour', 'fnac')]
        rival_prices = [value for value in rival_prices if value is not None]
        if z is not None and rival_prices:
            with_comparison += 1
            rival = min(rival_prices)
            zoco_cheaper += z < rival
            rival_cheaper += z > rival
            same += z == rival
    kpis = [
        ('Productos analizados', len(recs), '#,##0'),
        ('Con comparación entre tiendas', with_comparison, '#,##0'),
        ('Solo Zococity con precio', sum(1 for r in recs if r.get('price_zoco') is not None and not any(r.get('price_' + k) is not None for k in ('pcc', 'carrefour', 'fnac'))), '#,##0'),
        ('Zococity más barato', zoco_cheaper, '#,##0'),
        ('Tienda competidora más barata', rival_cheaper, '#,##0'),
        ('Empate con la oferta más baja', same, '#,##0'),
        ('Diferencia media (PCC sobre Zoco)', statistics.mean(difp_list) if difp_list else None, '+0.0%;-0.0%;0.0%'),
        ('Precio medio Zococity', statistics.mean([x for x in pz_list if x]) if pz_list else None, '€#,##0.00'),
        ('Precio medio PCComponentes', statistics.mean([x for x in pp_list if x]) if pp_list else None, '€#,##0.00'),
    ]
    ws.cell(row=row, column=2, value='Resumen').font = Font(bold=True, size=12, color=DARK)
    row += 1
    for lab, val, fmt in kpis:
        ws.cell(row=row, column=2, value=lab).font = Font(size=10, bold=True)
        c = ws.cell(row=row, column=4, value=val)
        c.font = Font(size=10)
        c.number_format = fmt
        row += 1

    # Metodología
    row += 2
    ws.cell(row=row, column=2, value='Metodología').font = Font(bold=True, size=12, color=DARK)
    row += 1
    lines = [
        'Zococity: catálogo Shopify leído en directo con navegador automatizado (nodriver): /products/<handle>.js por producto (precio, stock, SKU, EAN).',
        'PCComponentes: ficha oficial de cada producto abierta en directo con nodriver (Chrome real no detectable que supera el reto de Cloudflare); del JSON-LD se lee precio, stock, vendedor, SKU interno y EAN.',
        'Los productos sin ficha conocida se verifican con el buscador interno de PCComponentes en directo; «No disponible» significa ausencia comprobada el día de la consulta.',
        'Excepciones señaladas en la columna «Fuente del dato PCC» (índice de búsqueda o tarjeta del buscador cuando la ficha está blindada).',
        'Carrefour y Fnac: fichas oficiales y asociación solo con EAN exacto; se conserva el último precio confirmado si una lectura falla. Dif. € = Zoco − oferta competidora más baja; positivo = esa tienda es más barata. No se incluyen gastos de envío ni promociones.',
    ]
    for ln in lines:
        c = ws.cell(row=row, column=2, value=ln)
        c.font = Font(size=9, color='555555')
        c.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=12)
        ws.row_dimensions[row].height = 24
        row += 1

    widths = {'A': 2, 'B': 16, 'C': 13, 'D': 34, 'E': 15, 'F': 15, 'G': 12, 'H': 12,
              'I': 8, 'J': 34, 'K': 12, 'L': 16, 'M': 16, 'N': 19, 'O': 16,
              'P': 30, 'Q': 38, 'R': 16, 'S': 19, 'T': 16, 'U': 30, 'V': 38,
              'W': 14, 'X': 46, 'Y': 30, 'Z': 38, 'AA': 30}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.freeze_panes = f'D{r0 + 1}'

    buf = io.BytesIO()
    wb.save(buf)
    fname = 'Comparativa_Zococity_PCComponentes_Carrefour_Fnac.xlsx'
    return buf, fname


if __name__ == '__main__':
    b, f = build()
    out = os.path.join(BASE, f)
    open(out, 'wb').write(b.getvalue())
    print('OK:', out)
