# -*- coding: utf-8 -*-
"""Botones de planillas renombrados a la convención de Odoo (action_<verbo>).

Al actualizar, Odoo valida cada vista padre junto con sus vistas hijas YA
guardadas, que todavía llaman a los métodos antiguos («generate_tramos no es
una acción válida»). Este módulo se actualiza antes que los demás de
planillas: aquí se renombran los botones en las vistas guardadas, y cada
módulo vuelve a escribir las suyas al cargar sus datos.
"""
from odoo.tools import SQL

RENAMED = [
    ('export_plame', 'action_export_plame_rem'),
    ('export_plame_hours', 'action_export_plame_jor'),
    ('export_plame_suspencion', 'action_export_plame_snl'),
    ('export_plame_other_conditions', 'action_export_plame_toc'),
    ('afp_net', 'action_export_afpnet'),
    ('export_payroll_summary', 'action_export_payroll_summary'),
    ('compute_provision_cts', 'action_load_provisions'),
    ('compute_provision_grati', 'action_load_provisions'),
    ('compute_provision_liqui', 'action_load_provisions'),
    ('get_move_wizard', 'action_open_move_wizard'),
    ('get_liquidation_move_wizard', 'action_open_move_wizard'),
    ('generate_move', 'action_generate_move'),
    ('action_open_asiento', 'action_open_move'),
    ('set_close', 'action_close'),
    ('set_reopen', 'action_reopen'),
    ('view_detail', 'action_show_details'),
    ('set_not_payed', 'action_set_unpaid'),
    ('get_fees', 'action_generate_fees'),
    ('refresh_fees', 'action_recompute_fees'),
    ('import_advances_by_lot', 'action_import_advances'),
    ('import_loans_by_lot', 'action_import_loans'),
    ('compute_cts_line', 'action_compute'),
    ('view_detail_cts', 'action_show_details'),
    ('get_cts', 'action_process'),
    ('compute_cts_line_all', 'action_recompute'),
    ('export_cts', 'action_export_to_payslips'),
    ('turn_draft', 'action_draft'),
    ('action_open_cts', 'action_open_lines'),
    ('generate_tramos', 'action_generate_brackets'),
    ('compute_fifth_line', 'action_compute'),
    ('generate_fifth', 'action_generate'),
    ('get_employees_excluidos', 'action_add_excluded_employees'),
    ('recompute_fifth', 'action_recompute'),
    ('export_fifth', 'action_export_to_payslips'),
    ('turn_verify', 'action_reopen'),
    ('generate_payslips', 'action_generate_payslips'),
    ('recompute_payslips', 'action_recompute'),
    ('import_advances_ade_quin', 'action_import_advances'),
    ('import_loans_ade_quin', 'action_import_loans'),
    ('export_quincena', 'action_export_to_payslips'),
    ('set_draft', 'action_draft'),
    ('reopen_payroll', 'action_reopen'),
    ('compute_grati_line', 'action_compute'),
    ('view_detail_grat', 'action_show_details'),
    ('get_gratification', 'action_process'),
    ('compute_grati_line_all', 'action_recompute'),
    ('export_gratification', 'action_export_to_payslips'),
    ('action_open_grati', 'action_open_lines'),
    ('compute_vacation_line', 'action_compute'),
    ('get_concepts_view', 'action_add_concepts'),
    ('get_liquidation', 'action_process'),
    ('compute_liquidation_all', 'action_recompute'),
    ('export_liquidation', 'action_export_to_payslips'),
    ('get_liquidation_employees', 'action_add_employees'),
    ('compute_acumulado', 'action_compute_accumulated'),
    ('close_provisiones', 'action_close'),
    ('get_subsidies', 'action_process'),
    ('turn_done', 'action_close'),
    ('get_information', 'action_load_information'),
    ('get_calculation', 'action_compute'),
    ('import_subsidies_by_lot', 'action_import_subsidies'),
    ('compute_utilities_line_all', 'action_recompute'),
    ('export_utilities', 'action_export_to_payslips'),
    ('action_open_utili', 'action_open_lines'),
    ('compute_utilitie_line', 'action_compute'),
    ('generate_vacation_report', 'action_compute_balances'),
    ('view_detail_vac', 'action_show_details'),
    ('get_vacation', 'action_process'),
    ('compute_vaca_line_all', 'action_recompute'),
    ('compute_fifth', 'action_import_fifth'),
    ('export_vacation', 'action_export_to_payslips'),
    ('get_excel_vacation', 'action_export_xlsx'),
    ('export_certificate', 'action_print_certificate'),
    ('export_letter', 'action_print_letter'),
    ('generate_multipayments', 'action_generate_multipayment'),
    ('get_multipayments_view', 'action_open_multipayments'),
]

# Nombres genéricos: solo en las vistas de su modelo.
RENAMED_BY_MODEL = [
    ('hr.utilities', 'calculate', 'action_process'),
    ('hr.provisiones', 'actualizar', 'action_process'),
    ('hr.employee.excluidos.wizard', 'insert', 'action_add'),
]


def _rename(cr, old, new, model=None):
    """Reemplaza el botón en cada traducción del arch (arch_db es jsonb: en
    su texto las comillas van escapadas, por eso se recorre por idioma)."""
    old_attr, new_attr = 'name="%s"' % old, 'name="%s"' % new
    cr.execute(SQL(
        """UPDATE ir_ui_view v
              SET arch_db = (SELECT jsonb_object_agg(e.key, replace(e.value, %s, %s))
                               FROM jsonb_each_text(v.arch_db) e)
            WHERE EXISTS (SELECT 1 FROM jsonb_each_text(v.arch_db) e
                           WHERE e.value LIKE %s) %s""",
        old_attr, new_attr, '%' + old_attr + '%',
        SQL("AND v.model = %s", model) if model else SQL(""),
    ))


def migrate(cr, version):
    for old, new in RENAMED:
        _rename(cr, old, new)
    for model, old, new in RENAMED_BY_MODEL:
        _rename(cr, old, new, model)
