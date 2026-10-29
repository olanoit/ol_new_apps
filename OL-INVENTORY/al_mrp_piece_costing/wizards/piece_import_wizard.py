# -*- coding: utf-8 -*-
"""Importador del despiece (especificación de costeo de piezas CNC v1.4,
§5.2): crea o actualiza los productos-pieza desde un XLSX plano con una fila
por pieza. La orden de corte se arma aparte. Todo o nada: con un error no se
importa ninguna fila."""
import io

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

# Columnas del archivo; el encabezado se lee sin mayúsculas y con «_» en
# lugar de espacios.
COLUMNS = ('obra', 'mueble_terminado', 'modulo', 'id_pieza', 'material', 'largo_mm',
           'ancho_mm', 'area_m2', 'tapacanto_codigo', 'tapacanto_ml', 'cantidad')
REQUIRED_COLUMNS = ('obra', 'id_pieza', 'material')
# Diferencia admitida entre area_m2 y largo × ancho antes de avisar.
AREA_WARNING_RATIO = 0.02


def _to_float(value, default=0.0):
    if value in (None, ''):
        return default
    try:
        return float(str(value).replace(',', '.'))
    except ValueError:
        return None


class MrpPieceImportWizard(models.TransientModel):
    _name = 'mrp.piece.import.wizard'
    _description = 'Importar el despiece de piezas'

    file = fields.Binary(string='Archivo XLSX', required=True)
    file_name = fields.Char(string='Nombre del archivo')
    categ_id = fields.Many2one(
        'product.category', string='Categoría de las piezas', required=True,
        help='Su costo debe ser promedio o FIFO para que el costeo por medida tenga efecto.')
    summary = fields.Text(string='Resultado', readonly=True)
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Hecho')], default='draft')

    def _read_rows(self):
        """(filas, errores, avisos): cada fila es un dict con los datos de la
        pieza ya validados."""
        import openpyxl

        try:
            workbook = openpyxl.load_workbook(
                io.BytesIO(self.file.content), read_only=True, data_only=True)
        except Exception as error:  # noqa: BLE001 - cualquier archivo ilegible
            raise UserError(self.env._('No se pudo leer el archivo como XLSX: %s', error))
        raw_rows = workbook.worksheets[0].iter_rows(values_only=True)
        try:
            header = next(raw_rows)
        except StopIteration:
            raise UserError(self.env._('El archivo está vacío.')) from None
        columns = [str(cell or '').strip().lower().replace(' ', '_') for cell in header]
        missing = [column for column in REQUIRED_COLUMNS if column not in columns]
        if missing:
            raise UserError(self.env._(
                'Faltan columnas obligatorias: %(missing)s.\nColumnas esperadas: %(columns)s.',
                missing=', '.join(missing), columns=', '.join(COLUMNS)))
        if 'area_m2' not in columns and not {'largo_mm', 'ancho_mm'} <= set(columns):
            raise UserError(self.env._(
                'El archivo debe traer area_m2, o largo_mm y ancho_mm para calcular el área.'))

        rows, errors, warnings, seen = [], [], [], set()
        for number, raw in enumerate(raw_rows, start=2):
            if not any(value not in (None, '') for value in raw):
                continue
            data = dict(zip(columns, raw))
            project = str(data.get('obra') or '').strip()
            piece = str(data.get('id_pieza') or '').strip()
            material = str(data.get('material') or '').strip()
            if not (project and piece and material):
                errors.append(self.env._(
                    'Fila %s: obra, id_pieza y material son obligatorios.', number))
                continue
            if (project, piece) in seen:
                errors.append(self.env._(
                    'Fila %(row)s: la pieza %(piece)s se repite en la obra %(project)s.',
                    row=number, piece=piece, project=project))
                continue
            seen.add((project, piece))
            length, width = _to_float(data.get('largo_mm')), _to_float(data.get('ancho_mm'))
            area = _to_float(data.get('area_m2'))
            if None in (length, width, area):
                errors.append(self.env._(
                    'Fila %s: largo_mm, ancho_mm o area_m2 no son números.', number))
                continue
            computed = length * width / 1_000_000.0
            if not area:
                area = computed
            elif computed and abs(area - computed) / computed > AREA_WARNING_RATIO:
                warnings.append(self.env._(
                    'Fila %(row)s: area_m2 (%(area)s) difiere más de 2 %% de largo × ancho '
                    '(%(computed).6f); se usa area_m2.', row=number, area=area, computed=computed))
            if area <= 0:
                errors.append(self.env._('Fila %s: el área debe ser mayor que cero.', number))
                continue
            edge_ml = _to_float(data.get('tapacanto_ml'))
            if edge_ml is None or edge_ml < 0:
                errors.append(self.env._('Fila %s: tapacanto_ml no es válido.', number))
                continue
            edge_code = str(data.get('tapacanto_codigo') or '').strip()
            if edge_ml > 0 and not edge_code:
                errors.append(self.env._(
                    'Fila %s: con tapacanto_ml hace falta tapacanto_codigo.', number))
                continue
            qty = _to_float(data.get('cantidad'), default=1.0)
            if qty is None or qty < 1:
                errors.append(self.env._('Fila %s: la cantidad mínima es 1.', number))
                continue
            rows.append({
                'row': number, 'project': project, 'piece': piece, 'material': material,
                'length': length, 'width': width, 'area': area, 'edge_code': edge_code,
                'edge_ml': edge_ml, 'qty': qty,
            })
        if not rows and not errors:
            raise UserError(self.env._('El archivo no tiene filas de datos.'))
        return rows, errors, warnings

    def _find_product(self, code):
        return self.env['product.product'].search(
            ['|', ('default_code', '=', code), ('name', '=', code)], limit=1)

    def _check_references(self, rows):
        """(errores, {código: tablero}). El tapacanto debe estar marcado: la
        bolsa de tapacanto se arma por esa marca."""
        errors, materials = [], {}
        for code in sorted({row['material'] for row in rows}):
            material = self._find_product(code)
            if material:
                materials[code] = material
            else:
                errors.append(self.env._('Tablero que no está en el maestro: %s.', code))
        for code in sorted({row['edge_code'] for row in rows if row['edge_code']}):
            edge = self._find_product(code)
            if not edge:
                errors.append(self.env._('Tapacanto que no está en el maestro: %s.', code))
            elif not edge.piece_is_edge_banding:
                errors.append(self.env._(
                    '%s existe pero no está marcado como tapacanto: márquelo en el producto y '
                    'vuelva a importar.', edge.display_name))
        return errors, materials

    def action_import(self):
        self.ensure_one()
        rows, errors, warnings = self._read_rows()
        reference_errors, materials = self._check_references(rows)
        errors += reference_errors
        if errors:
            raise UserError(self.env._(
                'El archivo tiene %(count)s error(es) y no se importó nada:\n%(errors)s',
                count=len(errors), errors='\n'.join('- %s' % error for error in errors[:40])))
        Product = self.env['product.product']
        unit = self.env.ref('uom.product_uom_unit')
        created = updated = 0
        for row in rows:
            code = '%s-%s' % (row['project'], row['piece'])
            values = {
                'piece_is_cut': True,
                'piece_area_m2': row['area'],
                'piece_edge_ml': row['edge_ml'],
                'piece_project_ref': row['project'],
                'piece_material_id': materials[row['material']].id,
                'categ_id': self.categ_id.id,
            }
            piece = Product.search([('default_code', '=', code)], limit=1)
            if piece:
                piece.write(values)
                updated += 1
                continue
            name = self.env._('Pieza %(project)s %(piece)s', project=row['project'],
                              piece=row['piece'])
            if row['length'] and row['width']:
                name += ' %gx%g' % (row['length'], row['width'])
            Product.create(dict(values, name=name, default_code=code, is_storable=True,
                                uom_id=unit.id))
            created += 1
        lines = [
            self.env._('Importación terminada.'),
            self.env._('Piezas creadas: %(created)s · actualizadas: %(updated)s',
                       created=created, updated=updated),
            self.env._('Obras: %s', ', '.join(sorted({row['project'] for row in rows}))),
            self.env._(
                'Área: %(area)s m² · tapacanto: %(edge)s m · unidades: %(qty)s',
                area=formatLang(self.env, sum(r['area'] * r['qty'] for r in rows), digits=4),
                edge=formatLang(self.env, sum(r['edge_ml'] * r['qty'] for r in rows), digits=2),
                qty=formatLang(self.env, sum(r['qty'] for r in rows), digits=0)),
        ]
        if warnings:
            lines.append(self.env._('Avisos (%s):', len(warnings)))
            lines += ['- %s' % warning for warning in warnings[:20]]
        self.write({'summary': '\n'.join(lines), 'state': 'done'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
