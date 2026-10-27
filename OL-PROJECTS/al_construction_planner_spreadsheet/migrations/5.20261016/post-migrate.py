# -*- coding: utf-8 -*-
"""CR-18, a: las hojas de trabajo guardaban celdas como número JSON y no
abrían («content.startsWith is not a function»). Se pasan a texto en los
datos y en la última foto (snapshot), sin perder las revisiones."""
import base64
import json

from odoo import SUPERUSER_ID, api


def _to_text(data):
    changed = 0
    for sheet in data.get('sheets') or []:
        cells = sheet.get('cells') or {}
        for ref, cell in cells.items():
            if isinstance(cell, dict):
                content = cell.get('content')
                if content is not None and not isinstance(content, str):
                    cell['content'] = str(content)
                    changed += 1
            elif cell is not None and not isinstance(cell, str):
                cells[ref] = str(cell)
                changed += 1
    return changed


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    documents = env['documents.document'].with_context(active_test=False).search(
        [('construction_sheet_kind', '!=', False), ('handler', '=', 'spreadsheet')])
    for document in documents:
        values = {}
        for fname in ('spreadsheet_binary_data', 'spreadsheet_snapshot'):
            raw = document[fname] if fname in document._fields else False
            if not raw:
                continue
            try:
                data = json.loads(base64.b64decode(raw))
            except ValueError:
                continue
            if _to_text(data):
                values[fname] = base64.b64encode(json.dumps(data).encode())
        if values:
            document.with_context(preserve_spreadsheet_revisions=True).write(values)
