from odoo import fields, models


class L10nPeSireReopenWizard(models.TransientModel):
    """Motivo obligatorio para reabrir un periodo SIRE ya realizado."""
    _name = 'l10n_pe.sire.reopen.wizard'
    _description = 'Reabrir periodo SIRE'

    res_model = fields.Char(string='Modelo', required=True, readonly=True)
    res_id = fields.Many2oneReference(model_field='res_model', required=True, readonly=True)
    reason = fields.Text(string='Motivo', required=True)

    def action_apply(self):
        self.ensure_one()
        self.env[self.res_model].browse(self.res_id)._sire_reopen(self.reason)
        return {'type': 'ir.actions.act_window_close'}
