# -*- coding: utf-8 -*-
"""Mixin reutilizable para asistentes de importación de planillas desde Excel.

Port a v19 del framework ``al_hr_payroll_import`` v18 (el mejor módulo del
set según el plan de migración). Cada importador hereda de
``al.import.payroll.mixin`` y solo declara:

  * ``_target_model`` — modelo destino (``hr.attendance``, etc.).
  * ``_sheet_keyword`` — substring usado para autoseleccionar la hoja del
    Excel.
  * ``_get_column_map()`` — diccionario ``{campo_lectura: indice_columna}``
    (índice 1-based, en el orden técnico de la fila de cabecera).
  * ``_process_row(row, line_no, ctx)`` — lógica específica de crear/actualizar.
  * ``_template_headers()`` (opcional) — cabeceras de la plantilla
    descargable; por defecto los campos del mapa de columnas.

El mixin se encarga de:

  * Validar que el archivo sea ``.xlsx``/``.xlsm``.
  * Listar y filtrar hojas (selector dinámico vía contexto).
  * Configurar la fila inicial de datos.
  * Iterar filas y entregar ``OrderedDict`` ``{campo: valor}``.
  * Resumir contadores (creado/actualizado/omitido/error) y log textual.
  * Lanzar la importación en un hilo con progreso en vivo y reporte xlsx.
  * Generar la plantilla Excel modelo con openpyxl (nuevo en v19;
    sustituye a los generadores xlsxwriter-a-directorio de
    ``hr_importers``/``hr_vacation_import`` v18).
"""
import base64
import io
import logging
import math
import threading
from collections import OrderedDict

from odoo import api, fields, models, modules
from odoo.exceptions import UserError, ValidationError
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


EXCEL_EXTS = ('.xlsx', '.xlsm')


def _run_import_thread(dbname, uid, wizard_model, wizard_id, progress_id,
                       rows):
    """Hilo que ejecuta la importación con su propio cursor.

    Recibe ``rows`` ya parseado (lista de ``(line_no, dict)``) para evitar
    re-leer el Excel. Va actualizando ``al.import.payroll.progress`` y al
    final guarda el reporte xlsx en el mismo registro.
    """
    try:
        registry = Registry(dbname)
        with registry.cursor() as cr:
            env = api.Environment(cr, uid, {})
            progress = env['al.import.payroll.progress'].browse(progress_id)
            wizard = env[wizard_model].browse(wizard_id)
            if not wizard.exists():
                progress.write({
                    'status': 'error',
                    'error_detail': 'El wizard origen ya no existe.',
                    'message': 'Error: wizard no encontrado.',
                    'date_end': fields.Datetime.now(),
                })
                cr.commit()
                return

            progress.write({
                'status': 'running',
                'total': len(rows),
                'date_start': fields.Datetime.now(),
                'message': 'Iniciando importación...',
            })
            cr.commit()

            results, counts, log_lines, created_ids = \
                wizard._process_all_rows(rows, progress=progress)

            report_bytes, filename = wizard._build_xlsx_report(
                results, counts)

            progress.write({
                'status': 'done',
                'current': len(rows),
                'created': counts['created'],
                'updated': counts['updated'],
                'skipped': counts['skipped'],
                'errors': counts['error'],
                'date_end': fields.Datetime.now(),
                'message': 'Completado: %d creados, %d actualizados, '
                           '%d omitidos, %d errores.' % (
                               counts['created'], counts['updated'],
                               counts['skipped'], counts['error'],
                           ),
                'log': '\n'.join(log_lines),
                'report_file': base64.b64encode(report_bytes)
                if report_bytes else False,
                'report_filename': filename,
                'created_res_ids_csv': ','.join(
                    str(i) for i in created_ids),
            })
            cr.commit()
    except Exception as exc:
        _logger.exception('Error fatal en hilo de importación: %s', exc)
        try:
            registry = Registry(dbname)
            with registry.cursor() as cr:
                env = api.Environment(cr, uid, {})
                env['al.import.payroll.progress'].browse(progress_id).write({
                    'status': 'error',
                    'error_detail': str(exc),
                    'message': 'Error durante la importación.',
                    'date_end': fields.Datetime.now(),
                })
                cr.commit()
        except Exception:
            _logger.exception('Tampoco se pudo registrar el fallo del hilo.')


class ImportPayrollMixin(models.AbstractModel):
    _name = 'al.import.payroll.mixin'
    _description = 'Mixin común para asistentes de importación de planillas'

    # ----- Archivo --------------------------------------------------------- #
    file_data = fields.Binary(string='Archivo Excel', attachment=False)
    file_name = fields.Char(string='Nombre del archivo')

    # ----- Hojas detectadas ----------------------------------------------- #
    # Mantenemos los nombres como char para auditoría y como base del domain.
    sheet_names_csv = fields.Char(
        string='Hojas detectadas',
        readonly=True,
        help='Lista separada por "||" de las hojas encontradas en el archivo.',
    )
    sheet_id = fields.Many2one(
        'al.import.payroll.sheet',
        string='Hoja a importar',
        domain="[('res_model', '=', wizard_model_name), ('res_id', '=', id)]",
        ondelete='set null',
    )
    # Helper expuesto al domain del Many2one: devuelve el ``_name`` del
    # wizard concreto y permite filtrar las hojas creadas por este wizard
    # sin acoplar el XML al modelo.
    wizard_model_name = fields.Char(
        string='Modelo wizard',
        compute='_compute_wizard_model_name',
        readonly=True,
    )

    def _compute_wizard_model_name(self):
        for rec in self:
            rec.wizard_model_name = rec._name

    # ----- Configuración de cabecera y datos ------------------------------ #
    header_row = fields.Integer(
        string='Fila de cabecera técnica',
        default=1,
        help='Fila donde están los nombres técnicos de las columnas. '
             'Sirve solo como referencia; el mapa de columnas es fijo por '
             'tipo de importación.',
    )
    start_row = fields.Integer(
        string='Primera fila de datos',
        default=2,
        required=True,
        help='Fila a partir de la cual se leen registros a importar. '
             'Editable para acomodar plantillas con más o menos cabeceras.',
    )

    # ----- Comportamiento de importación ---------------------------------- #
    update_existing = fields.Boolean(
        string='Actualizar existentes',
        default=True,
        help='Si el registro ya existe (por clave funcional), sus valores '
             'se sobrescriben con los del Excel. Si está desmarcado, se '
             'omite el registro.',
    )
    use_batching = fields.Boolean(
        string='Procesar por lotes',
        default=True,
        help='Si está activo, las filas se procesan en lotes del tamaño '
             'indicado y se hace commit al cerrar cada lote (el avance '
             'queda persistido aunque el proceso se interrumpa). '
             'Si está desactivado, se procesa todo en un solo lote.',
    )
    batch_size = fields.Integer(
        string='Tamaño de lote',
        default=100,
        help='Filas por lote cuando "Procesar por lotes" está activo.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )

    # ----- Resultado ------------------------------------------------------ #
    state = fields.Selection(
        [
            ('upload', 'Cargar archivo'),
            ('configure', 'Configurar'),
            ('done', 'Resultado'),
        ],
        default='upload',
        required=True,
    )
    created_count = fields.Integer(readonly=True)
    updated_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)
    error_count = fields.Integer(readonly=True)
    log = fields.Text(string='Registro de procesamiento', readonly=True)

    # ----- Reporte descargable -------------------------------------------- #
    report_file = fields.Binary(
        string='Reporte Excel',
        readonly=True,
        attachment=True,
    )
    report_filename = fields.Char(readonly=True)

    # ----- Plantilla descargable ------------------------------------------ #
    template_file = fields.Binary(
        string='Plantilla Excel',
        readonly=True,
        attachment=False,
    )
    template_filename = fields.Char(readonly=True)

    # ====================================================================== #
    # API a sobrescribir en clases hijas                                      #
    # ====================================================================== #

    _target_model = None  # ej. 'hr.attendance'
    _sheet_keyword = ''   # substring para autoseleccionar hoja

    def _get_column_map(self):
        """Mapa ``{campo: indice_columna_1based}``.

        El orden importa para el log y la validación visual; usar
        ``OrderedDict`` o un dict literal (Python 3.7+ preserva orden).
        """
        raise NotImplementedError(
            'Cada wizard concreto debe implementar _get_column_map().'
        )

    def _process_row(self, row, line_no, ctx):
        """Procesa una fila ya parseada como dict ``{campo: valor}``.

        Debe devolver una tupla ``(status, message)`` o
        ``(status, message, record)`` donde ``status`` es uno de
        ``'created'``, ``'updated'``, ``'skipped'``, ``'error'``. El mixin
        agrega los contadores y la línea al log automáticamente.
        """
        raise NotImplementedError(
            'Cada wizard concreto debe implementar _process_row().'
        )

    def _preprocess_rows(self, rows):
        """Permite reordenar/filtrar filas antes del procesamiento.

        Por defecto devuelve la lista intacta.
        """
        return rows

    def _validate_config(self):
        """Valida la configuración del asistente antes de importar.

        Aquí van los campos que la vista exige en el paso "Configurar"
        pero que NO pueden ser ``required`` a nivel de modelo (lo serían
        también en el paso 1, impidiendo subir el archivo o descargar la
        plantilla). Los hijos hacen ``super()`` y lanzan ``UserError``.
        """
        return True

    # ====================================================================== #
    # Validaciones y onchange                                                 #
    # ====================================================================== #

    @api.constrains('file_name')
    def _check_file_extension(self):
        for rec in self:
            if rec.file_name and not rec.file_name.lower().endswith(
                    EXCEL_EXTS):
                raise ValidationError(self.env._(
                    'Solo se aceptan archivos Excel (%s).')
                    % ', '.join(EXCEL_EXTS))

    @api.onchange('file_data', 'file_name')
    def _onchange_file_data(self):
        if not self.file_data:
            self.sheet_names_csv = False
            self.sheet_id = False
            self.state = 'upload'
            return
        if self.file_name and not self.file_name.lower().endswith(
                EXCEL_EXTS):
            self.file_data = False
            self.file_name = False
            return {
                'warning': {
                    'title': self.env._('Archivo inválido'),
                    'message': self.env._(
                        'Solo se permiten archivos Excel (.xlsx).'),
                }
            }

    # ====================================================================== #
    # Carga del libro / detección de hojas                                    #
    # ====================================================================== #

    def _open_workbook(self):
        """Devuelve un ``openpyxl.Workbook`` listo para usar
        (``data_only=True``)."""
        self.ensure_one()
        try:
            import openpyxl  # noqa: WPS433 — dependencia declarada
        except ImportError as exc:
            raise UserError(self.env._(
                'Falta la librería Python "openpyxl". Instálala en el '
                'entorno del servidor: pip install openpyxl')) from exc
        if not self.file_data:
            raise UserError(self.env._('Cargue primero un archivo Excel.'))
        raw = base64.b64decode(self.file_data)
        try:
            return openpyxl.load_workbook(
                io.BytesIO(raw), data_only=True, read_only=True,
            )
        except Exception as exc:
            raise UserError(self.env._(
                'No se pudo abrir el Excel: %s') % exc)

    def _detect_sheets(self):
        """Lista las hojas del archivo cargado."""
        wb = self._open_workbook()
        try:
            return list(wb.sheetnames)
        finally:
            wb.close()

    def action_load_file(self):
        """Detecta hojas, crea registros transient y autoselecciona."""
        self.ensure_one()
        if not self.file_data:
            raise UserError(self.env._('Cargue primero un archivo Excel.'))
        if self.file_name and not self.file_name.lower().endswith(
                EXCEL_EXTS):
            raise UserError(self.env._(
                'Solo se permiten archivos Excel (.xlsx).'))
        sheets = self._detect_sheets()
        if not sheets:
            raise UserError(self.env._('El archivo no contiene hojas.'))

        Sheet = self.env['al.import.payroll.sheet']
        # Eliminar hojas previas asociadas a este wizard antes de recrearlas.
        Sheet.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
        ]).unlink()
        sheet_records = Sheet.create([
            {
                'name': name,
                'sequence': idx * 10,
                'res_model': self._name,
                'res_id': self.id,
            }
            for idx, name in enumerate(sheets)
        ])

        keyword = (self._sheet_keyword or '').lower().strip()
        auto = self.env['al.import.payroll.sheet']
        if keyword:
            auto = sheet_records.filtered(
                lambda s: keyword in (s.name or '').lower()
            )[:1]
        if not auto and len(sheet_records) >= 1:
            # Sin coincidencia por keyword: autoseleccionar la primera hoja.
            auto = sheet_records[:1]

        self.write({
            'sheet_names_csv': '||'.join(sheets),
            'sheet_id': auto.id if auto else False,
            'state': 'configure',
        })
        return self._reopen()

    # ====================================================================== #
    # Lectura del Excel                                                       #
    # ====================================================================== #

    def _iter_data_rows(self):
        """Itera filas a partir de ``start_row`` devolviendo dicts
        campo→valor."""
        self.ensure_one()
        if not self.sheet_id:
            raise UserError(self.env._('Seleccione una hoja del archivo.'))
        sheet_name = self.sheet_id.name
        if self.start_row < 1:
            raise UserError(self.env._(
                'La fila inicial debe ser mayor o igual a 1.'))

        wb = self._open_workbook()
        try:
            if sheet_name not in wb.sheetnames:
                raise UserError(self.env._(
                    'La hoja "%s" no existe en el archivo.') % sheet_name)
            ws = wb[sheet_name]
            col_map = self._get_column_map()
            rows = []
            for line_no, row in enumerate(
                ws.iter_rows(min_row=self.start_row, values_only=True),
                start=self.start_row,
            ):
                if not any(c not in (None, '') for c in row):
                    continue
                parsed = OrderedDict()
                for fname, idx in col_map.items():
                    parsed[fname] = (
                        row[idx - 1] if 0 < idx <= len(row) else None
                    )
                rows.append((line_no, parsed))
            return rows
        finally:
            wb.close()

    # ====================================================================== #
    # Helpers comunes                                                         #
    # ====================================================================== #

    @staticmethod
    def _clean(value):
        """Normaliza una celda: ``None``/``''`` → ``False``, strip a
        strings."""
        if value is None:
            return False
        if isinstance(value, str):
            v = value.strip()
            return v or False
        return value

    @staticmethod
    def _clean_code(value):
        """Normaliza celdas que son códigos/documentos: openpyxl entrega
        los números como ``int``/``float`` (un DNI ``46271883`` llega como
        ``46271883.0``); aquí se vuelven texto sin decimales espurios."""
        if value in (None, '', False):
            return False
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, (int,)):
            return str(value)
        return str(value).strip() or False

    # ====================================================================== #
    # Ejecución                                                               #
    # ====================================================================== #

    def action_run_import(self):
        """Lanza la importación en un hilo y abre la vista de progreso.

        El hilo recibe los datos ya parseados (lista de ``(line_no, row)``)
        y procesa fila a fila con su propio cursor, actualizando el
        registro ``al.import.payroll.progress`` para que el widget OWL haga
        polling y muestre la barra de progreso.
        """
        self.ensure_one()
        self._validate_config()
        if not self.sheet_id:
            raise UserError(self.env._('Seleccione una hoja del archivo.'))
        if not self._target_model:
            raise UserError(self.env._(
                'El asistente no tiene modelo destino configurado.'))

        raw_rows = self._iter_data_rows()
        rows = self._preprocess_rows(raw_rows)
        if not rows:
            raise UserError(self.env._(
                'La hoja no contiene filas válidas.'))

        progress = self.env['al.import.payroll.progress'].create({
            'name': self.env._('Importación de %s') % self._description,
            'wizard_model': self._name,
            'wizard_id': self.id,
            'target_model': self._target_model,
            'status': 'pending',
            'total': len(rows),
            'message': self.env._('Preparando importación...'),
            'company_id': self.company_id.id,
        })

        # Commit para que el hilo (otro cursor) pueda leer el progress
        # y la transient del wizard.
        self.env.cr.commit()

        dbname = self.env.cr.dbname
        uid = self.env.uid
        thread = threading.Thread(
            target=_run_import_thread,
            args=(dbname, uid, self._name, self.id, progress.id, rows),
            daemon=True,
        )
        thread.start()

        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Progreso de Importación'),
            'res_model': 'al.import.payroll.progress',
            'res_id': progress.id,
            'view_mode': 'form',
            'target': 'new',
            'flags': {'mode': 'readonly'},
        }

    # ------------------------------------------------------------------ #
    # Núcleo de procesamiento (llamado desde el hilo o, en tests, de     #
    # forma síncrona). NO debe imprimir ni reabrir el wizard.            #
    # ------------------------------------------------------------------ #

    def _process_all_rows(self, rows, progress=None):
        """Procesa filas con dos commits desacoplados:

          * ``self.env.cr.commit()`` al cerrar cada lote → persiste los
            registros creados/actualizados del lote.
          * Un cursor dedicado (``_publish_progress``) escribe el progress
            del wizard cada N filas y commitea **independiente** del
            cursor de datos, así el widget OWL ve el avance en vivo
            aunque el lote aún esté en curso.
        """
        self.ensure_one()
        counts = {'created': 0, 'updated': 0, 'skipped': 0, 'error': 0}
        log_lines = []
        results = []
        created_ids = []
        ctx = {}
        total = len(rows)
        if self.use_batching:
            # Lotes de tamaño configurado: 1 commit por lote.
            batch_size = max(self.batch_size or 100, 1)
        else:
            # Sin batching: 1 commit por fila (más lento pero con
            # feedback en vivo del progreso).
            batch_size = 1
        n_batches = max(math.ceil(total / batch_size), 1)

        progress_id = progress.id if progress else None
        dbname = self.env.cr.dbname
        uid = self.env.uid
        # Como mucho 50 actualizaciones de progreso por lote, mínimo cada
        # 1 fila — equilibra "barra fluida" con overhead de commits.
        publish_every = max(1, batch_size // 50)

        _logger.info(
            '[%s] Importación arrancada: total=%d, use_batching=%s, '
            'batch_size=%d, lotes=%d, publish_every=%d',
            self._name, total, self.use_batching, batch_size,
            n_batches, publish_every,
        )

        def _publish_progress(current, batch_no, force_message=None):
            if not progress_id:
                return
            if self.use_batching:
                msg = force_message or (
                    'Lote %(b)s/%(n)s · %(p)s de %(t)s procesados...' % {
                        'b': batch_no, 'n': n_batches,
                        'p': current, 't': total,
                    }
                )
            else:
                msg = force_message or (
                    'Procesando %(p)s de %(t)s...' % {
                        'p': current, 't': total}
                )
            try:
                with Registry(dbname).cursor() as pcr:
                    penv = api.Environment(pcr, uid, {})
                    penv['al.import.payroll.progress'].browse(
                            progress_id).write({
                        'status': 'running',
                        'current': current,
                        'created': counts['created'],
                        'updated': counts['updated'],
                        'skipped': counts['skipped'],
                        'errors': counts['error'],
                        'message': msg,
                    })
                    pcr.commit()
            except Exception:
                _logger.exception(
                    '[%s] Error publicando progreso', self._name)

        for batch_idx in range(n_batches):
            start = batch_idx * batch_size
            end = min(start + batch_size, total)
            batch = rows[start:end]

            for j, (line_no, row) in enumerate(batch, start=1):
                record = None
                try:
                    with self.env.cr.savepoint():
                        ret = self._process_row(row, line_no, ctx)
                        if isinstance(ret, tuple) and len(ret) >= 3:
                            status, message, record = ret[0], ret[1], ret[2]
                        else:
                            status, message = ret
                except Exception as exc:
                    _logger.exception(
                        'Error importando fila %s (%s)', line_no, self._name,
                    )
                    status, message = 'error', str(exc)
                count_key = status if status in counts else 'error'
                counts[count_key] += 1
                tag = {
                    'created': 'OK',
                    'updated': 'UPD',
                    'skipped': 'SKIP',
                    'error': 'ERR',
                }.get(status, '?')
                log_lines.append(
                    '[%-4s] fila %s: %s' % (tag, line_no, message))
                results.append({
                    'line_no': line_no,
                    'status': status,
                    'message': message,
                    'row': row,
                    'fix': self._suggest_fix(status, message, row)
                    if status == 'error' else '',
                })
                if record and status in ('created', 'updated'):
                    try:
                        created_ids.append(record.id)
                    except Exception:
                        pass

                # Progreso en vivo (cursor dedicado, commit inmediato).
                current = start + j
                if current % publish_every == 0 or current == total:
                    _publish_progress(current, batch_idx + 1)

            # Commit del lote: persiste los registros del lote en la
            # transacción principal. En tests el cursor es de savepoint
            # y commitear está prohibido (el aislamiento lo da el test).
            if not modules.module.current_test:
                self.env.cr.commit()
            _logger.info(
                '[%s] Lote %d/%d cerrado (filas %d-%d, ok=%d upd=%d '
                'skip=%d err=%d)',
                self._name, batch_idx + 1, n_batches, start + 1, end,
                counts['created'], counts['updated'],
                counts['skipped'], counts['error'],
            )

        return results, counts, log_lines, created_ids

    # ====================================================================== #
    # Reporte Excel descargable                                               #
    # ====================================================================== #

    _STATUS_LABEL = {
        'created': 'CREADO',
        'updated': 'ACTUALIZADO',
        'skipped': 'OMITIDO',
        'error': 'ERROR',
    }
    # Colores de relleno (sin alpha): verde, azul, gris, rojo.
    _STATUS_FILL = {
        'created': 'C8E6C9',
        'updated': 'BBDEFB',
        'skipped': 'ECEFF1',
        'error': 'FFCDD2',
    }

    def _suggest_fix(self, status, message, row):
        """Devuelve una sugerencia de corrección legible para el usuario.

        Las clases hijas pueden ampliarlo con casos específicos.
        """
        if status != 'error':
            return ''
        return self.env._(
            'Revise la fila en la plantilla y vuelva a importar.')

    def _report_columns(self):
        """Columnas del reporte: lista de ``(header, key_in_row_dict)``.

        Se genera automáticamente del mapa de columnas de la clase
        concreta. Los hijos pueden sobrescribirlo para personalizar.
        """
        col_map = self._get_column_map()
        return [(k, k) for k in col_map]

    def _build_xlsx_report(self, results, counts):
        """Construye el xlsx con tres hojas: 'Resultado', 'Errores' y
        'Omitidos'."""
        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            _logger.warning('openpyxl no disponible: no se genera reporte')
            return None, False

        wb = openpyxl.Workbook()
        ws_all = wb.active
        ws_all.title = 'Resultado'
        ws_err = wb.create_sheet('Errores')
        ws_skip = wb.create_sheet('Omitidos')

        columns = self._report_columns()
        headers = ['Fila', 'Estado', 'Detalle / Mensaje', 'Sugerencia']
        headers += [h for h, _k in columns]

        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill('solid', fgColor='37474F')
        header_align = Alignment(vertical='center', wrap_text=True)

        def write_header(ws):
            for col_idx, label in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col_idx, value=label)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
            ws.freeze_panes = 'A2'
            ws.row_dimensions[1].height = 28

        write_header(ws_all)
        write_header(ws_err)
        write_header(ws_skip)

        def append_result(ws, idx, res):
            fill_hex = self._STATUS_FILL.get(res['status'])
            fill = PatternFill('solid', fgColor=fill_hex) \
                if fill_hex else None
            row_vals = [
                res['line_no'],
                self._STATUS_LABEL.get(res['status'], res['status']),
                res['message'] or '',
                res['fix'] or '',
            ]
            row_vals += [self._stringify(res['row'].get(k))
                         for _h, k in columns]
            for col_idx, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=idx, column=col_idx, value=val)
                if fill is not None:
                    cell.fill = fill

        for i, res in enumerate(results, start=2):
            append_result(ws_all, i, res)

        err_idx = 2
        skip_idx = 2
        for res in results:
            if res['status'] == 'error':
                append_result(ws_err, err_idx, res)
                err_idx += 1
            elif res['status'] == 'skipped':
                append_result(ws_skip, skip_idx, res)
                skip_idx += 1

        # Anchos heurísticos.
        widths = [8, 14, 60, 60] + [22] * len(columns)
        for ws in (ws_all, ws_err, ws_skip):
            for i, w in enumerate(widths, start=1):
                ws.column_dimensions[
                    openpyxl.utils.get_column_letter(i)].width = w

        # Resumen al final de la hoja principal.
        summary_row = len(results) + 3
        ws_all.cell(row=summary_row, column=1,
                    value='Resumen').font = Font(bold=True)
        for offset, (key, label) in enumerate([
            ('created', 'Creados'),
            ('updated', 'Actualizados'),
            ('skipped', 'Omitidos'),
            ('error', 'Errores'),
        ], start=0):
            r = summary_row + 1 + offset
            ws_all.cell(row=r, column=1, value=label)
            ws_all.cell(row=r, column=2, value=counts.get(key, 0))
            fill_hex = self._STATUS_FILL.get(key)
            if fill_hex:
                ws_all.cell(row=r, column=1).fill = PatternFill(
                    'solid', fgColor=fill_hex)

        buf = io.BytesIO()
        wb.save(buf)
        filename = 'import_{model}_{ts}.xlsx'.format(
            model=self._target_model.replace('.', '_'),
            ts=fields.Datetime.now().strftime('%Y%m%d_%H%M%S'),
        )
        return buf.getvalue(), filename

    @staticmethod
    def _stringify(value):
        if value is None or value is False:
            return ''
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def action_download_report(self):
        self.ensure_one()
        if not self.report_file:
            raise UserError(self.env._('No hay reporte disponible.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=report_file'
                   '&filename_field=report_filename&download=true'
                   % (self._name, self.id),
            'target': 'self',
        }

    # ====================================================================== #
    # Plantilla Excel modelo (nuevo v19)                                      #
    # ====================================================================== #

    def _template_headers(self):
        """Cabeceras de la plantilla descargable, en el orden del mapa de
        columnas. Los hijos la sobrescriben con etiquetas de negocio."""
        return list(self._get_column_map().keys())

    def _template_example_rows(self):
        """Filas de ejemplo (listas de valores) para la plantilla.

        Por defecto ninguna; los hijos pueden aportar 1-2 filas guía.
        """
        return []

    def _template_sheet_name(self):
        keyword = (self._sheet_keyword or '').strip()
        return keyword.upper() or 'DATOS'

    def _build_xlsx_template(self):
        """Genera la plantilla modelo (bytes, filename) con openpyxl."""
        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError as exc:
            raise UserError(self.env._(
                'Falta la librería Python "openpyxl". Instálala en el '
                'entorno del servidor: pip install openpyxl')) from exc

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = self._template_sheet_name()

        headers = self._template_headers()
        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill('solid', fgColor='1F4E5F')
        header_align = Alignment(vertical='center', wrap_text=True)
        for col_idx, label in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            ws.column_dimensions[
                openpyxl.utils.get_column_letter(col_idx)].width = max(
                    16, min(len(str(label)) + 4, 45))
        ws.freeze_panes = 'A2'
        ws.row_dimensions[1].height = 26

        example_fill = PatternFill('solid', fgColor='FFF9C4')
        for r_off, row_vals in enumerate(self._template_example_rows(),
                                         start=2):
            for col_idx, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=r_off, column=col_idx, value=val)
                cell.fill = example_fill

        buf = io.BytesIO()
        wb.save(buf)
        filename = 'plantilla_{model}.xlsx'.format(
            model=(self._target_model or self._name).replace('.', '_'))
        return buf.getvalue(), filename

    def action_download_template(self):
        """Genera y descarga la plantilla Excel modelo del importador."""
        self.ensure_one()
        data, filename = self._build_xlsx_template()
        self.write({
            'template_file': base64.b64encode(data),
            'template_filename': filename,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=template_file'
                   '&filename_field=template_filename&download=true'
                   % (self._name, self.id),
            'target': 'self',
        }

    # ====================================================================== #
    # Reapertura del wizard preservando contexto                              #
    # ====================================================================== #

    def _reopen(self, extra_ctx=None):
        self.ensure_one()
        ctx = dict(self.env.context, **(extra_ctx or {}))
        return {
            'type': 'ir.actions.act_window',
            'name': self._description,
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }
