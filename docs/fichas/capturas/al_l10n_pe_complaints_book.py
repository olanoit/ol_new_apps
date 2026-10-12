"""Captura del PDF de la ficha de al_l10n_pe_complaints_book: l10n_pe.complaint 000000001-2026 (hoja del libro virtual WEB-01).

Uso: python3 docs/fichas/capturas/al_l10n_pe_complaints_book.py [id]  (por defecto 98)
"""
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests  # noqa: E402
from capturar import DB, PASSWORD, ROOT, URL, USER, module_dir  # noqa: E402

M = 'al_l10n_pe_complaints_book'
RES_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 98

session = requests.Session()
session.post(f'{URL}/web/session/authenticate', json={
    'jsonrpc': '2.0', 'params': {'db': DB, 'login': USER, 'password': PASSWORD}})
pdf = session.get(f'{URL}/report/pdf/al_l10n_pe_complaints_book.report_complaint/{RES_ID}').content
out = module_dir(M) / 'static' / 'description' / 'screenshots'
(out / 'tmp.pdf').write_bytes(pdf)
# 110 ppp: una hoja A4 de 910 px de ancho, como el resto de las fichas
subprocess.run(['pdftoppm', '-r', '110', '-png', '-singlefile', '-f', '1', str(out / 'tmp.pdf'),
                str(out / '03-hoja')], check=True)
(out / 'tmp.pdf').unlink()
print('captura', (out / '03-hoja.png').relative_to(ROOT))
