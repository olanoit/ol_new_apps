# -*- coding: utf-8 -*-
"""Parámetros de las hojas de trabajo (paquete 1.17, M117-15).

Oficina Técnica mantiene aquí, por compañía, la lista de parámetros y su valor
inicial. Cada hoja nueva copia los de su tipo a su pestaña PARAMETROS, y el
analista cambia el valor solo para su hoja. Las fórmulas de las plantillas leen el
valor por su clave: ninguna lleva un número de negocio escrito.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from . import sheet_design as design

PARAMETERS_SHEET = 'PARAMETROS'
# Columnas de la pestaña. Las dos últimas van ocultas: el valor que leen las
# fórmulas (vacío, el inicial) y el inicial vigente en la configuración.
PARAMETER_HEADERS = ('Grupo', 'Parámetro', 'Valor', 'Unidad', 'Para qué sirve',
                     'Valor inicial (calc.)', 'Clave (calc.)', 'Motivo del cambio',
                     'Valor usado (calc.)', 'Vigente (calc.)')
COL_VALUE, COL_INITIAL, COL_KEY, COL_REASON, COL_USED, COL_CURRENT = 2, 5, 6, 7, 8, 9
NAMED_FLOORS = 'Azotea=AZ;Semisótano=SS;Sótano=SO'
# Los valores que no salen de la compañía ni de la cotización: (hoja, grupo,
# clave, parámetro, valor, tipo, valores, mínimo, máximo, unidad, para qué sirve).
_PERCENT = dict(value_type='percent', min_value=0, max_value=100, use_range=True, unit='%')
DEFAULT_PARAMETERS = (
    dict(sheet='sale', group='Impuestos', key='igv', name='IGV', value_type='percent', unit='%',
         use_range=True, min_value=0, max_value=100, locked=True,
         help_text='Impuesto de venta de la compañía: lo usa RESUMEN VENTA.'),
    dict(sheet='sale', group='Impuestos', key='precio_sin_igv',
         name='Precios del tarifario sin IGV', value_initial='Sí', value_type='list',
         allowed_values='Sí;No', help_text='En No, los precios ya traen IGV.'),
    dict(sheet='sale', group='Moneda', key='moneda', name='Moneda de la cotización',
         value_type='text', locked=True,
         help_text='La de la lista de precios de la cotización: se cambia en Ventas.'),
    dict(sheet='sale', group='Precio', key='redondeo_multiplo', name='Redondeo: múltiplo',
         value_initial='5', value_type='number', use_range=True, min_value=0, max_value=1000,
         help_text='El precio se redondea a múltiplos de este valor.'),
    dict(sheet='sale', group='Precio', key='redondeo_sentido', name='Redondeo: sentido',
         value_initial='Hacia arriba', value_type='list',
         allowed_values='Hacia arriba;Al más cercano;Sin redondeo',
         help_text='Hacia dónde se redondea.'),
    dict(sheet='sale', group='Precio', key='regla_tres',
         name='Ajustar el precio por la medida (regla de tres)', value_initial='Sí',
         value_type='list', allowed_values='Sí;No',
         help_text='Precio base por medida real entre medida base.'),
    dict(sheet='sale', group='Precio', key='factor_costo', name='Factor de venta sobre costo',
         value_type='number', use_range=True, min_value=0, max_value=100,
         help_text='Multiplica el costo estimado de los ítems «Por costo».'),
    dict(sheet='sale', group='Acabados', key='rec_estandar', name='Recargo: Estándar blanco',
         value_initial='0', help_text='Recargo por zona de este acabado.', **_PERCENT),
    dict(sheet='sale', group='Acabados', key='rec_color', name='Recargo: Color o maderado',
         value_initial='10', help_text='Recargo por zona de este acabado.', **_PERCENT),
    dict(sheet='sale', group='Acabados', key='rec_blanco_rh', name='Recargo: Blanco RH',
         value_initial='30', help_text='Recargo por zona de este acabado.', **_PERCENT),
    dict(sheet='sale', group='Acabados', key='rec_color_rh', name='Recargo: Color RH',
         value_initial='40', help_text='Recargo por zona de este acabado.', **_PERCENT),
    dict(sheet='sale', group='Metrado', key='medida_mayor',
         name='Si el detalle y el plano difieren, vale la mayor medida', value_initial='Sí',
         value_type='list', allowed_values='Sí;No',
         help_text='En No, vale la medida del detalle.'),
    dict(sheet='sale', group='Edificio', key='dpto_factor',
         name='Factor del piso en el número de departamento', value_initial='100',
         value_type='number', use_range=True, min_value=1, max_value=10000,
         help_text='Piso por factor más posición: 201.'),
    dict(sheet='sale', group='Edificio', key='amb_cuenta',
         name='Ambiente que cuenta departamentos', value_initial='Cocina', value_type='text',
         help_text='Las filas de este ambiente cuentan los departamentos de la obra.'),
    dict(sheet='sale', group='Edificio', key='pisos_nombre', name='Pisos con nombre',
         value_initial=NAMED_FLOORS, value_type='text',
         help_text='Nombre=prefijo, separados por punto y coma.'),
    dict(sheet='sale', group='Textos', key='ambientes', name='Ambientes de la lista',
         value_initial='Cocina;Closet dormitorio principal;Closet dormitorio secundario;'
                       'Baño principal;Baño secundario;Lavandería;Ducto',
         value_type='text', in_sheet=False,
         help_text='Lista de ambientes de EDIFICIO, con el que cuenta departamentos primero.'),
    dict(sheet='sale', group='Textos', key='cond_generales', name='Condiciones generales',
         value_type='text', in_sheet=False, help_text='Llegan a OBRA al crear la hoja.'),
    dict(sheet='sale', group='Textos', key='forma_pago', name='Forma de pago',
         value_type='text', in_sheet=False, help_text='Llega a OBRA al crear la hoja.'),
    dict(sheet='sale', group='Textos', key='garantia', name='Garantía',
         value_type='text', in_sheet=False, help_text='Llega a OBRA al crear la hoja.'),
    dict(sheet='sale', group='Textos', key='validez', name='Validez de la oferta',
         value_type='text', in_sheet=False, help_text='Llega a OBRA al crear la hoja.'),
    dict(sheet='planning', group='Piezas', key='piezas_frente',
         name='Tipos de pieza que toman el acabado de frentes',
         value_initial='PUERTA;FRENTE;TAPA', value_type='text',
         help_text='Las demás toman el de estructura, en las propuestas de tablero.'),
    dict(sheet='planning', group='Programa', key='dias_semana', name='Días de trabajo por semana',
         value_initial='5', value_type='number', use_range=True, min_value=1, max_value=7,
         unit='días', help_text='Divide los días de cada sub etapa en PROGRAMA.'),
    dict(sheet='planning', group='Programa', key='dias_sub_etapa',
         name='Días por sub etapa, si la celda de PROGRAMA está vacía', value_initial='5',
         value_type='number', use_range=True, min_value=1, max_value=365, unit='días',
         help_text='Lo usa PROGRAMA cuando «Días por sub etapa» está vacío.'),
    dict(sheet='planning', group='Control', key='tolerancia_ml',
         name='Tolerancia de ML entre hoja y planificador', value_initial='0.5',
         help_text='CONTROL acepta esta diferencia.', **_PERCENT),
    dict(sheet='planning', group='Control', key='tolerancia_ml_venta',
         name='Tolerancia de ML entre lo fabricado y lo vendido', value_initial='5',
         help_text='CONTROL marca en ámbar lo que se pasa.', **_PERCENT),
)


def parameter_formula(key):
    """Lee un parámetro por su clave: ninguna fórmula lleva el número escrito."""
    return 'XLOOKUP("%s",%s!$G:$G,%s!$I:$I)' % (key, PARAMETERS_SHEET, PARAMETERS_SHEET)


class ConstructionSheetParameter(models.Model):
    _name = 'construction.sheet.parameter'
    _description = 'Parámetro de las hojas de trabajo'
    _order = 'sheet, sequence, id'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)
    sheet = fields.Selection([('sale', 'Hoja de venta'), ('planning', 'Hoja de planificación')],
                             string='Hoja', required=True, default='sale')
    sequence = fields.Integer(string='Secuencia', default=10)
    group = fields.Char(string='Grupo', required=True)
    name = fields.Char(string='Parámetro', required=True, translate=True)
    key = fields.Char(string='Clave', required=True,
                      help='La que usan las fórmulas de la hoja. No se cambia si alguna la usa.')
    value_initial = fields.Char(string='Valor inicial',
                                help='Una hoja nueva copia este valor. En un porcentaje, 18 es '
                                     '18 %. Vacío: la hoja no tiene valor hasta que se escriba.')
    value_type = fields.Selection(
        [('number', 'Número'), ('percent', 'Porcentaje'), ('list', 'Lista'), ('text', 'Texto')],
        string='Tipo', required=True, default='number')
    allowed_values = fields.Char(string='Valores de la lista',
                                 help='Separados por punto y coma.')
    use_range = fields.Boolean(string='Tiene rango')
    min_value = fields.Float(string='Mínimo')
    max_value = fields.Float(string='Máximo')
    unit = fields.Char(string='Unidad')
    help_text = fields.Char(string='Para qué sirve', translate=True)
    locked = fields.Boolean(string='Solo lectura en la hoja',
                            help='El valor viene de la compañía o de la cotización.')
    in_sheet = fields.Boolean(string='Se muestra en PARAMETROS', default=True,
                              help='Apagado: textos y listas que la hoja recibe en otro lugar.')
    active = fields.Boolean(string='Activo', default=True)

    _key_unique = models.Constraint(
        'unique(company_id, sheet, key)',
        'Ya hay un parámetro con esa clave en esa hoja.')

    def _check_value(self, value):
        """Mensaje de error si ``value`` (como lo escribe Oficina Técnica) no es
        de su tipo o está fuera de su rango; ``False`` si está bien."""
        self.ensure_one()
        if value in (False, None, ''):
            return False
        if self.value_type == 'list':
            allowed = [item.strip() for item in (self.allowed_values or '').split(';')]
            return False if str(value) in allowed else self.env._(
                '«%(value)s» no está en la lista de %(name)s: %(allowed)s.',
                value=value, name=self.name, allowed=', '.join(allowed))
        if self.value_type not in ('number', 'percent'):
            return False
        try:
            number = float(value)
        except (TypeError, ValueError):
            return self.env._('%(name)s debe ser un número: «%(value)s».',
                              name=self.name, value=value)
        if self.use_range and not self.min_value <= number <= self.max_value:
            return self.env._('%(name)s debe estar entre %(min)s y %(max)s.', name=self.name,
                              min=self.min_value, max=self.max_value)
        return False

    @api.constrains('value_initial', 'value_type', 'allowed_values', 'use_range', 'min_value',
                    'max_value')
    def _check_value_initial(self):
        for parameter in self:
            message = parameter._check_value(parameter.value_initial)
            if message:
                raise ValidationError(message)

    @api.model
    def _construction_ensure(self, company):
        """Los parámetros iniciales de la compañía (los que no tiene)."""
        # Lo corre quien crea una hoja, sin permiso sobre la configuración: solo
        # agrega las filas iniciales que faltan en su compañía.
        Parameter_sudo = self.sudo().with_context(active_test=False)
        existing = set(Parameter_sudo.search([('company_id', '=', company.id)]).mapped(
            lambda parameter: (parameter.sheet, parameter.key)))
        values = [dict(vals, company_id=company.id, sequence=index * 10)
                  for index, vals in enumerate(DEFAULT_PARAMETERS, start=1)
                  if (vals['sheet'], vals['key']) not in existing]
        if values:
            Parameter_sudo.create(values)

    def _sheet_value(self, value):
        """El valor como va en la celda: un porcentaje, como fracción."""
        self.ensure_one()
        if value in (False, None, ''):
            return ''
        if self.value_type == 'percent':
            return repr(round(float(value) / 100, 6))
        return str(value)

    def _construction_cell_format(self):
        self.ensure_one()
        if self.value_type != 'percent':
            return None
        return '0.0%' if float(self.value_initial or 0) % 1 else '0%'

    @api.model
    def _construction_for_sheet(self, sheet, company, overrides=None):
        """Parámetros de ``sheet``, con el valor inicial de cada uno (``overrides``
        trae los que vienen de la compañía o de la cotización)."""
        self._construction_ensure(company)
        overrides = overrides or {}
        parameters = self.sudo().search([('company_id', '=', company.id), ('sheet', '=', sheet),
                                         ('in_sheet', '=', True)])
        return [(parameter, overrides.get(parameter.key, parameter.value_initial))
                for parameter in parameters]

    @api.model
    def _construction_sheet_data(self, sheet, company, styles, formats, overrides=None):
        """La pestaña PARAMETROS de una hoja.

        :param styles: ``{'head_data', 'head_calc', 'data', 'calc', 'border'}``
            con los ids de estilo de la plantilla.
        :param formats: diccionario de formatos de la plantilla, que se completa.
        """
        rows = self._construction_for_sheet(sheet, company, overrides)
        last = len(rows) + 1
        cells = {chr(65 + index) + '1': header for index, header in enumerate(PARAMETER_HEADERS)}
        sheet_styles = {'A1:B1': styles['head_calc'], 'C1': styles['head_data'],
                        'D1:G1': styles['head_calc'], 'H1': styles['head_data'],
                        'I1:J1': styles['head_calc']}
        sheet_formats, rules, conditional = {}, [], []
        for row, (parameter, value) in enumerate(rows, start=2):
            shown = parameter._sheet_value(value)
            cells.update({
                'A%s' % row: parameter.group, 'B%s' % row: parameter.name,
                'D%s' % row: parameter.unit or '', 'E%s' % row: parameter.help_text or '',
                'G%s' % row: parameter.key,
                'I%s' % row: '=IF(C{r}="",F{r},C{r})'.format(r=row),
            })
            if shown:
                cells['C%s' % row] = shown
                cells['F%s' % row] = shown
            style = styles['calc'] if parameter.locked else styles['data']
            sheet_styles['C%s' % row] = style
            sheet_styles['H%s' % row] = styles['data']
            for letter in 'ABDEFG':
                sheet_styles['%s%s' % (letter, row)] = styles['calc']
            cell_format = parameter._construction_cell_format()
            if cell_format:
                format_id = formats.setdefault(cell_format, len(formats) + 1)
                sheet_formats['C%s' % row] = sheet_formats['F%s' % row] = \
                    sheet_formats['I%s' % row] = format_id
            if parameter.value_type == 'list' and parameter.allowed_values:
                rules.append({
                    'id': 'parameter_%s' % parameter.key, 'isBlocking': True,
                    'ranges': ['C%s' % row],
                    'criterion': {'type': 'isValueInList', 'displayStyle': 'arrow', 'values': [
                        item.strip() for item in parameter.allowed_values.split(';')]}})
            if parameter.use_range and parameter.value_type in ('number', 'percent'):
                factor = 100 if parameter.value_type == 'percent' else 1
                conditional.append(_mark(
                    'range_%s' % parameter.key, ['C%s' % row],
                    '=AND(C{r}<>"",OR(C{r}<{min},C{r}>{max}))'.format(
                        r=row, min=parameter.min_value / factor,
                        max=parameter.max_value / factor), design.ERROR_FILL, design.ERROR_TEXT))
        data_range = '2:%s' % last
        conditional += [
            _mark('no_reason', ['H%s' % data_range.replace(':', ':H')],
                  '=AND($C2<>"",$C2<>$F2,$H2="")', design.ERROR_FILL, design.ERROR_TEXT),
            _mark('changed', ['C%s' % data_range.replace(':', ':C')],
                  '=AND($C2<>"",$C2<>$F2)', None, design.WARNING_TEXT, bold=True),
            _mark('current', ['F%s' % data_range.replace(':', ':F')],
                  '=AND($J2<>"",$J2<>$F2)', design.WARNING_FILL, design.WARNING_TEXT),
        ]
        widths = (105, 300, 120, 105, 330, 110, 130, 220, 105, 105)
        cols = {str(index): {'size': width} for index, width in enumerate(widths)}
        cols['8']['isHidden'] = cols['9']['isHidden'] = True
        return {
            'id': 'sheet_parametros', 'name': PARAMETERS_SHEET, 'colNumber': 12,
            'rowNumber': max(last + 40, 60), 'cells': cells, 'styles': sheet_styles,
            'formats': sheet_formats, 'borders': {'A1:H1': styles['border']},
            'cols': cols, 'rows': {'0': {'size': design.HEADER_HEIGHT}},
            'panes': {'xSplit': 2, 'ySplit': 1},
            'tables': [{'range': 'A1:H%s' % last, 'type': 'static',
                        'config': design.table_config(PARAMETERS_SHEET)}],
            'dataValidationRules': rules, 'conditionalFormats': conditional,
        }

    @api.model
    def _construction_current_values(self, sheet, company, overrides=None):
        """{clave: valor de la celda}: el inicial vigente, para el aviso de una
        hoja ya creada (M117-15, punto 7)."""
        return {parameter.key: parameter._sheet_value(value)
                for parameter, value in self._construction_for_sheet(sheet, company, overrides)}

    @api.model
    def _construction_issues(self, rows, sheet, company, used=()):
        """Errores de la pestaña PARAMETROS (M117-15, punto 8): ``[(hoja, fila,
        columna, mensaje, tipo)]``.

        :param rows: las filas de la pestaña, con encabezado.
        :param used: las claves que alguna fila de la hoja usa: vacías, son error.
        """
        parameters = {parameter.key: parameter for parameter, _value in
                      self._construction_for_sheet(sheet, company)}
        issues = []
        for number, row in enumerate(rows or [], start=1):
            if number == 1 or len(row) <= COL_KEY or not row[COL_KEY]:
                continue
            key = row[COL_KEY]
            parameter = parameters.get(key)
            value = row[COL_VALUE] if len(row) > COL_VALUE else ''
            initial = row[COL_INITIAL] if len(row) > COL_INITIAL else ''
            reason = row[COL_REASON] if len(row) > COL_REASON else ''
            current = row[COL_CURRENT] if len(row) > COL_CURRENT else ''
            name = parameter.name if parameter else key
            if value in ('', False) and initial in ('', False):
                if key in used:
                    issues.append((PARAMETERS_SHEET, number, 'Valor', self.env._(
                        '%s está vacío y alguna fila lo usa.', name), 'error'))
                continue
            if parameter and value not in ('', False):
                shown = value * 100 if parameter.value_type == 'percent' \
                    and isinstance(value, (int, float)) else value
                message = parameter._check_value(shown)
                if message:
                    issues.append((PARAMETERS_SHEET, number, 'Valor', message, 'error'))
            if value not in ('', False) and str(value) != str(initial) and not reason:
                issues.append((PARAMETERS_SHEET, number, 'Motivo del cambio', self.env._(
                    '%s cambió sin motivo.', name), 'error'))
            if current not in ('', False) and str(current) != str(initial):
                issues.append((PARAMETERS_SHEET, number, 'Valor inicial (calc.)', self.env._(
                    'El valor inicial vigente de %(name)s es %(current)s.',
                    name=name, current=current), 'warning'))
        return issues


def _mark(mark_id, ranges, formula, fill, text, bold=False):
    style = {'textColor': text}
    if fill:
        style['fillColor'] = fill
    if bold:
        style['bold'] = True
    return {'id': 'parameter_%s' % mark_id, 'ranges': ranges, 'stopIfTrue': False,
            'rule': {'type': 'CellIsRule', 'operator': 'customFormula', 'values': [formula],
                     'style': style}}


class ConstructionVerticalProfile(models.Model):
    _inherit = 'construction.vertical.profile'

    def _export_data(self):
        """El perfil lleva los parámetros de la compañía, para que un perfil
        nuevo funcione sin desarrollo."""
        data = super()._export_data()
        Parameter = self.env['construction.sheet.parameter']
        Parameter._construction_ensure(self.env.company)
        data['sheet_parameters'] = [{
            field: parameter[field] for field in (
                'sheet', 'sequence', 'group', 'name', 'key', 'value_initial', 'value_type',
                'allowed_values', 'use_range', 'min_value', 'max_value', 'unit', 'help_text',
                'locked', 'in_sheet')
        } for parameter in Parameter.search([('company_id', '=', self.env.company.id)])]
        return data

    @api.model
    def _import_data(self, data):
        profile = super()._import_data(data)
        Parameter = self.env['construction.sheet.parameter'].with_context(active_test=False)
        company = self.env.company
        for vals in data.get('sheet_parameters', []):
            parameter = Parameter.search([('company_id', '=', company.id),
                                          ('sheet', '=', vals['sheet']),
                                          ('key', '=', vals['key'])], limit=1)
            if parameter:
                parameter.write(vals)
            else:
                Parameter.create(dict(vals, company_id=company.id))
        return profile
