#!/usr/bin/env python3
"""Genera el catálogo de actividades económicas de l10n_pe_vat_sunat
(``data/l10n_pe.economic.activity.csv``) desde la CIIU Rev. 4 oficial de las
Naciones Unidas en español, que es la que SUNAT usa en la ficha RUC.

Fuente (guardada junto a este script):
https://unstats.un.org/unsd/classifications/Econ/Download/In%20Text/ISIC_Rev_4_Spanish_structure.txt
(CSV «Code»,«Title», en Windows-1252). Se toman solo las clases (4 dígitos).

Uso: python3 docs/ciiu/generar_actividades_ciiu.py [--check]
"""
import csv
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'ISIC_Rev_4_Spanish_structure.txt'
TARGET = (HERE.parents[1] / 'OL-ACCOUNTING' / 'l10n_pe_vat_sunat' / 'data'
          / 'l10n_pe.economic.activity.csv')


def build():
    rows = csv.DictReader(io.StringIO(SOURCE.read_bytes().decode('cp1252')))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(['id', 'code', 'name'])
    for row in rows:
        code = (row['Code'] or '').strip()
        if len(code) == 4 and code.isdigit():
            name = ' '.join((row['Title'] or '').split()).rstrip('.')
            writer.writerow(['ciiu_%s' % code, code, name])
    return out.getvalue()


def main():
    content = build()
    if '--check' in sys.argv:
        if not TARGET.exists() or TARGET.read_text(encoding='utf-8') != content:
            raise SystemExit('Desactualizado: %s' % TARGET)
        print('Catálogo CIIU al día: %d clases.' % (content.count('\n') - 1))
        return
    TARGET.write_text(content, encoding='utf-8')
    print('%d clases → %s' % (content.count('\n') - 1, TARGET))


if __name__ == '__main__':
    main()
