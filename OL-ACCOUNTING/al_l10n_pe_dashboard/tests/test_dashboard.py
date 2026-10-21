"""Tablero Perú: vista de ventas, compras e IGV y armado de la hoja."""
import json

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestPeDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.igv_sale = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id), ('type_tax_use', '=', 'sale'),
            ('l10n_pe_edi_tax_code', '=', '1000'), ('amount', '=', 18)], limit=1)
        cls.igv_purchase = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id), ('type_tax_use', '=', 'purchase'),
            ('l10n_pe_edi_tax_code', '=', '1000'), ('amount', '=', 18)], limit=1)
        cls.partner = cls.env['res.partner'].create({'name': 'CLIENTE TABLERO SAC'})
        # Diarios sin documentos LATAM: la prueba no depende de series ni del envío a SUNAT.
        cls.journals = {
            kind: cls.env['account.journal'].create({
                'name': f'Tablero {kind}', 'code': f'TB{kind[0].upper()}', 'type': kind,
                'l10n_latam_use_documents': False})
            for kind in ('sale', 'purchase')
        }
        cls.users = cls.env['res.users'].create([{
            'name': name, 'login': login,
            'group_ids': [Command.set([cls.env.ref(group).id])],
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
        } for name, login, group in (
            ('Contadora Tablero', 'contadora_tablero', 'account.group_account_user'),
            ('Auditor Tablero', 'auditor_tablero', 'account.group_account_readonly'),
        )])

    def _move(self, move_type, amount, tax):
        journal = self.journals['sale' if move_type.startswith('out') else 'purchase']
        move = self.env['account.move'].create({
            'move_type': move_type, 'partner_id': self.partner.id, 'journal_id': journal.id,
            'invoice_date': fields.Date.context_today(self.partner), 'ref': f'F001-{amount}',
            'invoice_line_ids': [Command.create({'name': 'Servicio', 'price_unit': amount,
                                                 'tax_ids': [Command.set(tax.ids)]})],
        })
        move.action_post()
        return move

    def test_tax_view_signs(self):
        sale = self._move('out_invoice', 1000, self.igv_sale)
        refund = self._move('out_refund', 200, self.igv_sale)
        bill = self._move('in_invoice', 500, self.igv_purchase)
        rows = self.env['l10n_pe.dashboard.tax'].search([('move_id', 'in', (sale | refund | bill).ids)])
        values = {row.move_id: (row.kind, row.base, row.igv) for row in rows}
        self.assertEqual(values[sale], ('sale', 1000.0, 180.0))
        self.assertEqual(values[refund], ('sale', -200.0, -36.0))
        self.assertEqual(values[bill], ('purchase', 500.0, 90.0))

    def test_dashboard_is_built_and_readable(self):
        self._move('out_invoice', 1000, self.igv_sale)
        builder = self.env['l10n_pe.dashboard.builder']
        dashboard = self.env.ref('al_l10n_pe_dashboard.dashboard_pe')
        builder._refresh_dashboard(force=True)
        self.assertFalse(builder._refresh_dashboard(force=True), 'sin cambios no se reescribe')
        dashboard._check_spreadsheet_data()  # modelos y campos del JSON existen
        data = json.loads(dashboard.spreadsheet_data)
        cells = data['sheets'][0]['cells'].values()
        self.assertIn('Ventas, compras e IGV', cells)
        self.assertIn('Comprobantes electrónicos', cells)
        # Cada fuente responde con los permisos del contable y del auditor.
        for user in self.users:
            for source in list(data['pivots'].values()) + list(data['lists'].values()):
                self.env[source['model']].with_user(user).search_count(source['domain'])
            self.assertIn(dashboard, self.env['spreadsheet.dashboard'].with_user(user).search([]))
        action = self.env.ref('al_l10n_pe_dashboard.action_pe_dashboard')
        self.assertEqual(action.params, {'dashboard_id': dashboard.id})

    def test_sections_follow_installed_modules(self):
        builder = self.env['l10n_pe.dashboard.builder']
        cells = set(builder._build_snapshot()['sheets'][0]['cells'].values())
        has_detraction = 'l10n_pe_detraction_amount' in self.env['account.move']._fields
        self.assertEqual('Detracciones, retenciones y percepciones' in cells, has_detraction)
        self.assertEqual('Declaraciones mensuales' in cells, 'l10n_pe.monthly.tax' in self.env)
