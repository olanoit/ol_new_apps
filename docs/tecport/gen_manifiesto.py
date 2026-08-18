"""Construye el manifiesto de estructura de los TXT de referencia (versionable en git)."""
import hashlib, io, os, zipfile

REF = '/home/och/odoo/ce19/myodoo/ol_new_apps/docs/tecport/referencia'
OUT = '/home/och/odoo/ce19/myodoo/ol_new_apps/docs/tecport/REFERENCIA_ESTRUCTURA.md'

# formato -> etiqueta legible, deducido del nombre SUNAT LE{ruc}{aaaa}{mm}00{libro}...
LIBROS = {
    '0101': '1.1  Libro Caja',
    '0102': '1.2  Libro Bancos',
    '0501': '5.1  Libro Diario',
    '0502': '5.2  Libro Diario simplificado',
    '0503': '5.3  Plan contable (diario)',
    '0504': '5.4  Plan contable (diario simplificado)',
    '0601': '6.1  Libro Mayor',
    '0804': '8.4  Registro de Compras nacional (RCE)',
    '0805': '8.5  Registro de Compras no domiciliados (RCE)',
    '1301': '13.1 Inventario permanente valorizado',
    '1404': '14.4 Registro de Ventas (RVIE)',
}


def libro_de(nombre):
    # LE 20517256031 2026 03 00 0501 00001 1 1 1 .txt
    base = os.path.basename(nombre)
    if not base.startswith('LE'):
        return '?', '?'
    resto = base[2:]
    ruc = resto[:11]
    periodo = resto[11:17]      # aaaamm
    codigo = resto[19:23]
    return codigo, periodo


def analiza(raw, nombre):
    txt = raw.decode('utf-8', errors='replace')
    lineas = [l for l in txt.split('\n') if l.strip()]
    campos = sorted({l.count('|') for l in lineas}) if lineas else []
    return {
        'nombre': nombre,
        'bytes': len(raw),
        'lineas': len(lineas),
        'campos': campos,
        'md5': hashlib.md5(raw).hexdigest(),
        'muestra': lineas[:2],
    }


filas = []
for periodo_dir in sorted(os.listdir(REF)):
    d = os.path.join(REF, periodo_dir)
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        if f.lower().endswith('.txt'):
            filas.append((periodo_dir, analiza(open(p, 'rb').read(), f), None))
        elif f.lower().endswith('.zip'):
            with zipfile.ZipFile(p) as z:
                for inner in z.namelist():
                    filas.append((periodo_dir, analiza(z.read(inner), inner), f))

with open(OUT, 'w', encoding='utf-8') as fh:
    w = fh.write
    w('# Referencia — estructura de los TXT generados por el proyecto origen (Odoo 18)\n\n')
    w('Generado desde `tecport-mtest`, compañía **TECPORT PERU** (RUC 20517256031), '
      'periodos 2026-01 y 2026-03. Solo lectura; sin commit.\n\n')
    w('Los archivos completos **no se versionan** (38 MB): viven en `docs/tecport/referencia/`, '
      'ignorada por git, y se regeneran con `gen_referencia.py`. Este manifiesto es lo que '
      'se usa para validar la estructura de la implementación migrada.\n\n')
    w('## Inventario\n\n')
    w('| Periodo | Libro | Archivo | Bytes | Líneas | Campos/línea | MD5 |\n')
    w('|---|---|---|---:|---:|---|---|\n')
    for per, a, zip_origen in filas:
        cod, _ = libro_de(a['nombre'])
        libro = LIBROS.get(cod, cod)
        campos = ', '.join(str(c) for c in a['campos'])
        nombre = a['nombre'] + (' *(en %s)*' % zip_origen if zip_origen else '')
        w('| %s | %s | `%s` | %d | %d | %s | `%s` |\n'
          % (per, libro, nombre, a['bytes'], a['lineas'], campos, a['md5'][:12]))

    # duplicados
    porhash = {}
    for per, a, _ in filas:
        porhash.setdefault((per, a['md5']), []).append(a['nombre'])
    dups = {k: v for k, v in porhash.items() if len(v) > 1}
    if dups:
        w('\n## ⚠ Archivos con contenido idéntico dentro del mismo periodo\n\n')
        for (per, md5), nombres in sorted(dups.items()):
            w('- **%s** — `%s…`\n' % (per, md5[:12]))
            for n in nombres:
                cod, _ = libro_de(n)
                w('  - %s → `%s`\n' % (LIBROS.get(cod, cod), n))

    w('\n## Muestras (primeras 2 líneas)\n\n')
    vistos = set()
    for per, a, _ in filas:
        cod, _ = libro_de(a['nombre'])
        if cod in vistos:
            continue
        vistos.add(cod)
        w('### %s\n\n' % LIBROS.get(cod, cod))
        w('```\n')
        for l in a['muestra']:
            w(l[:300] + ('…' if len(l) > 300 else '') + '\n')
        w('```\n\n')

print('escrito %s con %d archivos analizados' % (OUT, len(filas)))
