# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    use_name_sequence = fields.Boolean(
        string='Numerar por secuencia',
        copy=False,
        help='Al publicar, el número del asiento sale de la secuencia '
             'configurada abajo en lugar del mecanismo nativo. Para CPE '
             'Perú, escriba la serie como prefijo (p. ej. «F001-» o '
             '«B001-»): el nombre resultante es a la vez el número de '
             'documento serie-correlativo de SUNAT.')
    name_sequence_prefix = fields.Char(
        string='Prefijo (serie)', copy=False,
        help='Serie con la que se crea la secuencia de asientos, p. ej. '
             '«F001-». Al guardar (o con el botón Generar) se crea la '
             'secuencia con este prefijo, relleno 8 y sin huecos en la '
             'compañía del diario.')
    refund_name_sequence_prefix = fields.Char(
        string='Prefijo NC (serie)', copy=False,
        help='Serie de las notas de crédito, p. ej. «FC01-». Vacío: las NC '
             'usan la secuencia de asientos.')
    name_sequence_id = fields.Many2one(
        'ir.sequence', string='Secuencia de asientos',
        copy=False, check_company=True,
        domain="[('company_id', '=', company_id)]",
        help='Secuencia usada para numerar los asientos del diario.')
    refund_name_sequence_id = fields.Many2one(
        'ir.sequence', string='Secuencia de notas de crédito',
        copy=False, check_company=True,
        domain="[('company_id', '=', company_id)]",
        help='Secuencia separada para las notas de crédito (serie propia, '
             'p. ej. «FC01-»). Vacía: se usa la secuencia de asientos.')
    edi_series_ids = fields.Many2many(
        'edi.invoice.series', string='Series CPE',
        check_company=True, copy=False,
        domain="[('company_id', '=', company_id), ('state', '=', 'publish')]",
        help='Series de comprobante electrónico disponibles en este diario. '
             'Si el comprobante lleva una serie asignada, su secuencia tiene '
             'prioridad sobre las secuencias simples de abajo; las notas de '
             'crédito/débito usan la serie rectificativa de la serie del '
             'documento de origen.')

    @api.constrains('name_sequence_id', 'refund_name_sequence_id')
    def _check_al_name_sequences(self):
        for journal in self:
            if (journal.name_sequence_id and journal.refund_name_sequence_id
                    and journal.name_sequence_id == journal.refund_name_sequence_id):
                raise ValidationError(self.env._(
                    'En el diario "%s" la secuencia de asientos y la de '
                    'notas de crédito no pueden ser la misma.',
                    journal.display_name))

    def _al_prepare_name_sequence_vals(self, refund=False):
        self.ensure_one()
        code = (self.code or '').upper()
        prefix = (self.refund_name_sequence_prefix if refund
                  else self.name_sequence_prefix)
        return {
            'name': '%s%s (%s)' % (
                self.name, self.env._(' NC') if refund else '', code),
            # Compañía del diario (= compañía actual del formulario).
            'company_id': self.company_id.id,
            # Sin huecos: SUNAT exige correlativo continuo por serie.
            'implementation': 'no_gap',
            'prefix': prefix or '%s%s-' % ('R' if refund else '', code),
            'padding': 8,
        }

    def _al_create_name_sequence(self, refund=False):
        self.ensure_one()
        return self.env['ir.sequence'].sudo().create(
            self._al_prepare_name_sequence_vals(refund=refund))

    def _al_ensure_name_sequences(self):
        """Crea las secuencias simples que falten: la principal siempre que
        la numeración esté activa; la de NC solo si se indicó su prefijo.
        Los diarios con documentos latam quedan fuera: ahí solo numeran
        las Series CPE."""
        for journal in self:
            if not journal.use_name_sequence or journal.l10n_latam_use_documents:
                continue
            if not journal.name_sequence_id:
                journal.name_sequence_id = journal._al_create_name_sequence()
            if (journal.refund_name_sequence_prefix
                    and not journal.refund_name_sequence_id):
                journal.refund_name_sequence_id = \
                    journal._al_create_name_sequence(refund=True)

    def action_al_generate_name_sequence(self):
        """Botón «Generar» junto a la secuencia de asientos."""
        for journal in self:
            if not journal.name_sequence_id:
                journal.name_sequence_id = journal._al_create_name_sequence()

    def action_al_generate_refund_name_sequence(self):
        """Botón «Generar» junto a la secuencia de notas de crédito."""
        for journal in self:
            if not journal.refund_name_sequence_id:
                journal.refund_name_sequence_id = \
                    journal._al_create_name_sequence(refund=True)

    @api.model_create_multi
    def create(self, vals_list):
        journals = super().create(vals_list)
        journals._al_ensure_name_sequences()
        return journals

    def write(self, vals):
        res = super().write(vals)
        if (vals.get('use_name_sequence')
                or vals.get('name_sequence_prefix')
                or vals.get('refund_name_sequence_prefix')):
            self._al_ensure_name_sequences()
        return res
