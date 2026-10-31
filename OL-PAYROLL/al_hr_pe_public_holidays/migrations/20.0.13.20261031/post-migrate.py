from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """El cron de feriados pasa de anual a mensual (es idempotente): los
    calendarios nuevos y los trabajadores que entran al régimen de
    construcción ya no esperan al 2 de enero. El registro es noupdate."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref('al_hr_pe_public_holidays.ir_cron_apply_yearly_holidays',
                   raise_if_not_found=False)
    if cron:
        cron.write({
            'name': 'Feriados de Perú: aplicación mensual',
            'interval_number': 1,
            'interval_type': 'months',
        })
    # Calendarios compartidos entre compañías: un descanso por compañía
    # (antes uno solo, con la compañía de la última pasada del cron).
    env['pe.public.holiday'].cron_apply_yearly_holidays()
