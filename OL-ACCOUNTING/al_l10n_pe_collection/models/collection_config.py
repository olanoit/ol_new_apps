from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: Canales en los que el art. 62 de la Ley 29571 limita el horario con consumidores.
GUARDED_CHANNELS = ('call', 'visit', 'whatsapp', 'sms')

CHANNELS = [
    ('call', 'Llamada'),
    ('visit', 'Visita'),
    ('email', 'Correo'),
    ('whatsapp', 'WhatsApp'),
    ('sms', 'SMS'),
    ('letter', 'Carta'),
    ('other', 'Otro'),
]


class L10nPeCollectionZone(models.Model):
    _name = 'l10n_pe.collection.zone'
    _description = 'Zona de cobranza'
    _order = 'name'

    name = fields.Char(string='Zona', required=True)
    active = fields.Boolean(default=True)
    user_id = fields.Many2one('res.users', string='Gestor por defecto',
                              help='Se propone como gestor de los clientes de la zona.')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)


class L10nPeCollectionBucket(models.Model):
    """Tramo de antigüedad: agrupa la cartera y da la probabilidad de cobro que
    usa la proyección."""
    _name = 'l10n_pe.collection.bucket'
    _description = 'Tramo de antigüedad'
    _order = 'days_from'

    name = fields.Char(string='Tramo', required=True)
    days_from = fields.Integer(string='Desde (días de atraso)', required=True,
                               help='Negativo: días antes del vencimiento.')
    days_to = fields.Integer(string='Hasta (días de atraso)',
                             help='Vacío o cero en el último tramo: sin límite.')
    probability = fields.Float(string='Probabilidad de cobro (%)', default=100.0, digits=(5, 1))
    company_id = fields.Many2one('res.company', string='Compañía')

    @api.constrains('probability', 'days_from', 'days_to')
    def _check_values(self):
        for bucket in self:
            if not 0 <= bucket.probability <= 100:
                raise ValidationError(_('La probabilidad va de 0 a 100.'))
            if bucket.days_to and bucket.days_to < bucket.days_from:
                raise ValidationError(_('El tramo %s termina antes de empezar.', bucket.name))

    @api.model
    def _l10n_pe_for_days(self, days, company=None):
        """Tramo de una cuota con ``days`` días de atraso (negativo: por vencer)."""
        company = company or self.env.company
        buckets = self.search(['|', ('company_id', '=', False), ('company_id', '=', company.root_id.id)])
        for bucket in buckets.sorted('days_from', reverse=True):
            if days >= bucket.days_from and (not bucket.days_to or days <= bucket.days_to):
                return bucket
        return buckets[:1]


class L10nPeCollectionResult(models.Model):
    """Resultado de una gestión: «Promete pagar», «No contesta», «Reclamo»…"""
    _name = 'l10n_pe.collection.result'
    _description = 'Resultado de gestión'
    _order = 'sequence, name'

    name = fields.Char(string='Resultado', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_promise = fields.Boolean(string='Es compromiso de pago',
                                help='La gestión pide fecha e importe y crea el compromiso de pago.')
    is_contact = fields.Boolean(string='Hubo contacto', default=True,
                                help='Para medir la tasa de contacto de los gestores.')
    is_dispute = fields.Boolean(string='Es reclamo',
                                help='La gestión pide el motivo y abre un reclamo con sus documentos, que salen '
                                     'del seguimiento hasta resolverse.')
    next_action_days = fields.Integer(string='Próxima acción en (días)',
                                      help='Programa una actividad al gestor; 0 para no programar.')
