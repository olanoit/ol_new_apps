from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Los feriados del catálogo cargados sin concepto toman el DOM de la
    nómina peruana, igual que sus descansos ya aplicados."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    dom = env.ref('al_hr_pe.wd_DOM', raise_if_not_found=False)
    if not dom:
        return
    holidays = env['pe.public.holiday'].with_context(active_test=False).search(
        [('work_entry_type_id', '=', False)])
    holidays.write({'work_entry_type_id': dom.id})
    holidays.leave_ids.filtered(lambda l: not l.work_entry_type_id).write(
        {'work_entry_type_id': dom.id})
