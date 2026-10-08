# -*- coding: utf-8 -*-
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

from .res_company import L10N_PE_DEST_TYPE_SELECTION

# Porcentaje como fracción (1 = 100 %). 6 decimales de fracción ≈ 4 del %.
PERCENTAGE_DIGITS = 6
PERCENTAGE_TOLERANCE = 1e-4  # ±0.01 % para cubrir redondeos (3×33.33 % = 99.99 %)


class AccountAccount(models.Model):
    _inherit = 'account.account'

    l10n_pe_dest_type = fields.Selection(
        selection=L10N_PE_DEST_TYPE_SELECTION,
        string='Tipo de cuenta destino',
        compute='_compute_l10n_pe_dest_type',
        help='Sentido de la dinámica de destinos según la compañía actual.')
    l10n_pe_work_destinies = fields.Boolean(
        string='Trabaja con destinos', compute='_compute_l10n_pe_work_destinies')
    # Por compañía, con el mismo patrón que el código de la cuenta
    # (``code`` / ``code_store``): el valor se guarda por compañía
    # (company_dependent) y se lee y escribe en la compañía raíz, así las
    # sucursales usan la configuración de su RUC.
    l10n_pe_no_destiny_store = fields.Boolean(company_dependent=True)
    l10n_pe_load_account_store = fields.Many2one('account.account', company_dependent=True)
    l10n_pe_no_destiny = fields.Boolean(
        string='Desactivar destinos',
        compute='_compute_l10n_pe_company_values', inverse='_inverse_l10n_pe_no_destiny',
        help='No se generará asiento de destino para esta cuenta aunque tenga '
             'o no configuradas sus cuentas destino.')
    # Las cuentas v19 se comparten entre compañías: el reparto es de cada
    # compañía raíz (como el código de la cuenta) y se ve el de la activa.
    l10n_pe_destiny_ids = fields.One2many(
        'l10n_pe.account.destiny', 'parent_account_id', string='Cuenta(s) destino',
        domain=lambda self: [('company_id', '=', self.env.company.root_id.id)])
    l10n_pe_load_account_id = fields.Many2one(
        'account.account', string='Cuenta de carga',
        compute='_compute_l10n_pe_company_values', inverse='_inverse_l10n_pe_load_account',
        domain="['|', '|', ('code', '=like', '72%'), ('code', '=like', '78%'), ('code', '=like', '79%')]",
        help='Excepción a la cuenta de carga de la compañía (Ajustes): p. ej. '
             '78 para gastos cubiertos por provisiones o 72 para producción de '
             'activo inmovilizado. Vacío: la de la compañía (791).')
    l10n_pe_has_destiny = fields.Boolean(
        string='Incluye destino', compute='_compute_l10n_pe_has_destiny',
        help='La cuenta tiene al menos una cuenta destino configurada.')
    l10n_pe_allowed_dest_ids = fields.Many2many(
        'account.account', compute='_compute_l10n_pe_allowed_dest_ids',
        string='Cuentas destino permitidas')

    @api.depends_context('company')
    @api.depends('l10n_pe_no_destiny_store', 'l10n_pe_load_account_store')
    def _compute_l10n_pe_company_values(self):
        # sudo: como en ``account.account._compute_code``, la compañía raíz
        # puede no estar entre las permitidas de un usuario de la sucursal.
        accounts_root_sudo = self.with_company(self.env.company.root_id).sudo()
        for account, account_root_sudo in zip(self, accounts_root_sudo):
            account.l10n_pe_no_destiny = account_root_sudo.l10n_pe_no_destiny_store
            account.l10n_pe_load_account_id = account_root_sudo.l10n_pe_load_account_store.sudo(False)

    def _inverse_l10n_pe_no_destiny(self):
        # sudo: se escribe en la compañía raíz (ver el cálculo).
        accounts_root_sudo = self.with_company(self.env.company.root_id).sudo()
        for account, account_root_sudo in zip(self, accounts_root_sudo):
            account_root_sudo.l10n_pe_no_destiny_store = account.l10n_pe_no_destiny

    def _inverse_l10n_pe_load_account(self):
        # sudo: se escribe en la compañía raíz (ver el cálculo).
        accounts_root_sudo = self.with_company(self.env.company.root_id).sudo()
        for account, account_root_sudo in zip(self, accounts_root_sudo):
            account_root_sudo.l10n_pe_load_account_store = account.l10n_pe_load_account_id

    @api.depends_context('company')
    def _compute_l10n_pe_dest_type(self):
        # Como el código de la cuenta: lo decide la compañía raíz (el RUC).
        dest_type = self.env.company.root_id.l10n_pe_dest_type
        for account in self:
            account.l10n_pe_dest_type = dest_type

    @api.depends('code', 'l10n_pe_dest_type')
    def _compute_l10n_pe_work_destinies(self):
        for account in self:
            prefix = (account.code or '')[:1]
            account.l10n_pe_work_destinies = (
                (prefix == '6' and account.l10n_pe_dest_type == '6a9')
                or (prefix == '9' and account.l10n_pe_dest_type == '9a6'))

    @api.depends('l10n_pe_work_destinies')
    def _compute_l10n_pe_allowed_dest_ids(self):
        # Destinos permitidos: la clase opuesta (9 si 6→9, 6 si 9→6). Una sola
        # búsqueda por prefijo para todo el lote.
        allowed_by_prefix = {}
        for account in self:
            if not account.l10n_pe_work_destinies:
                account.l10n_pe_allowed_dest_ids = [Command.clear()]
                continue
            target_prefix = '9%' if account.l10n_pe_dest_type == '6a9' else '6%'
            if target_prefix not in allowed_by_prefix:
                # v19: 'deprecated' ya no existe; las cuentas dadas de baja son
                # active=False (filtrado por defecto en search).
                allowed_by_prefix[target_prefix] = self.env['account.account'].search(
                    [('code', '=like', target_prefix)])
            account.l10n_pe_allowed_dest_ids = [
                Command.set(allowed_by_prefix[target_prefix].ids)]

    @api.depends_context('company')
    @api.depends('l10n_pe_destiny_ids')
    def _compute_l10n_pe_has_destiny(self):
        for account in self:
            account.l10n_pe_has_destiny = bool(account.l10n_pe_destiny_ids)

    # ------------------------------------------------------------------ #
    # Validación del 100 %                                                #
    # ------------------------------------------------------------------ #

    def _l10n_pe_destiny_total(self):
        self.ensure_one()
        return sum(self.l10n_pe_destiny_ids.mapped('percentage'))

    def l10n_pe_check_destiny_percentage(self):
        """Suma de porcentajes destino = 100 %. Fuente única de la validación
        (la usan la restricción del formulario y la generación del asiento)."""
        self.ensure_one()
        if not self.l10n_pe_destiny_ids:
            return
        total = self._l10n_pe_destiny_total()
        if abs(total - 1.0) > PERCENTAGE_TOLERANCE:
            raise UserError(_(
                'La suma de los porcentajes de las cuentas destino debe ser '
                '100%% para la cuenta %(code)s.\nSuma actual: %(total).4f%%.',
                code=self.code or '', total=total * 100))

    @api.constrains('l10n_pe_destiny_ids')
    def _constrain_l10n_pe_destiny(self):
        for account in self:
            account.l10n_pe_check_destiny_percentage()

    def copy_data(self, default=None):
        # v19: copy_data es por lote y devuelve una lista de dicts. Se copian
        # las líneas destino de cada cuenta.
        vals_list = super().copy_data(default=default)
        if not (default and 'l10n_pe_destiny_ids' in default):
            for account, vals in zip(self, vals_list):
                vals['l10n_pe_destiny_ids'] = [
                    Command.create({'dest_account_id': line.dest_account_id.id,
                                    'percentage': line.percentage,
                                    'company_id': line.company_id.id})
                    for line in account.l10n_pe_destiny_ids]
        return vals_list


class L10nPeAccountDestiny(models.Model):
    _name = 'l10n_pe.account.destiny'
    _description = 'Cuenta destino (dinámica PCGE)'
    _order = 'id asc'
    _rec_name = 'dest_account_id'
    _check_company_auto = True

    # Compañía raíz (el RUC): sus sucursales usan el mismo reparto, igual que
    # comparten el código de la cuenta.
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company.root_id)
    parent_account_id = fields.Many2one(
        'account.account', string='Cuenta principal', required=True,
        ondelete='cascade', index=True, check_company=True)
    dest_account_id = fields.Many2one(
        'account.account', string='Cuenta destino', required=True,
        ondelete='cascade', check_company=True)
    percentage = fields.Float(
        string='Porcentaje %', required=True, default=1.0,
        digits=(16, PERCENTAGE_DIGITS),
        help='Fracción del importe destinada a esta cuenta (1 = 100 %). '
             'La suma de todas las líneas debe ser 100 %.')
    allowed_dest_ids = fields.Many2many(
        'account.account', related='parent_account_id.l10n_pe_allowed_dest_ids',
        string='Cuentas permitidas')

    @api.constrains('percentage')
    def _check_percentage(self):
        for line in self:
            if float_compare(line.percentage, 0.0,
                             precision_digits=PERCENTAGE_DIGITS) <= 0:
                raise UserError(_('El porcentaje de la cuenta destino debe ser mayor que 0.'))

    # La suma del 100 % no se valida línea a línea: desde la lista de
    # destinos las líneas se crean de una en una y la primera (p. ej. 60 %)
    # nunca cuadraría. Se valida al guardar la cuenta con sus destinos
    # (``_constrain_l10n_pe_destiny``) y, siempre, al generar el asiento.
