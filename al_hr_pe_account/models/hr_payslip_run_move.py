# -*- coding: utf-8 -*-
"""Asiento contable de planilla por lote (partición peruana).

Portado de ``hr_payslip_run_move`` + ``hr_payslip_run_move_analytic``
(v18), donde una vista SQL (``payslip_run_move``) y dos funciones
PL/pgSQL agregaban las líneas de ``hr.payslip.line`` por cuenta para
generar un asiento único del lote. En v19 toda la agregación se hace
por ORM sobre ``hr.payslip.line`` — la vista SQL desaparece.

Convivencia con el flujo nativo (``hr_payroll_account`` v19, "nativo
primero"): al validar boletas, ``action_payslip_done`` genera asientos
usando ``account_debit``/``account_credit`` (company_dependent) de cada
regla y el diario de la estructura (``struct_id.journal_id``). Ese flujo
queda intacto. El asiento de lote peruano es **opt-in**: la compañía que
lo use deja el diario de la estructura vacío (el nativo no genera nada)
y lanza el asistente «Asiento de planilla por lote», que aporta lo que
el nativo no da:

* **Bloque AFP por afiliación**: el abono de las reglas de aportes AFP
  (configurables en ``hr.main.parameter.afp_rule_ids``; en v18 códigos
  fijos COMFI/COMMIX/SEGI/A_JUB) se imputa a la cuenta de la afiliación
  del trabajador (``hr.membership.account_id``, company_dependent), una
  línea por AFP.
* **Asiento único del lote** agrupado por regla salarial y cuenta
  (paridad con la función ``payslip_run_move(int, int)`` v18).
* **Detalle por trabajador**: las reglas con ``employee_move_line``
  (nativo; sustituye al ``is_detail_cta`` v18) abonan una línea por
  empleado con su partner.
* **Analítica opcional** (`detail_analytic` por compañía): las líneas
  llevan el ``analytic_distribution`` JSON nativo de la regla o de
  ``hr.version`` (el modelo propio v18 ``hr.analytic.distribution``
  queda eliminado). El prorrateo por porcentaje lo hace el motor
  analítico nativo — no se desdoblan importes como en v18.
"""
import json

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round

# v18: el bloque AFP se emitía con secuencia fija 58 para ordenarlo al
# final del asiento, después de los descuentos al trabajador.
AFP_MOVE_SEQUENCE = 58


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    # ``move_id`` ya existe en hr_payroll_account (reemplaza al
    # ``account_move_id`` propio de v18): reutilizamos su stat button del
    # kanban y ``action_open_move``.

    def action_pe_open_batch_move_wizard(self):
        """Abre el asistente de generación del asiento de lote."""
        if len(self) > 1:
            raise UserError(self.env._(
                'No se puede seleccionar más de un lote para este '
                'proceso.'))
        self.ensure_one()
        if self.move_id:
            raise UserError(self.env._(
                'El lote ya tiene un asiento contable (%(move)s). '
                'Anúlelo y elimínelo para generar uno nuevo.',
                move=self.move_id.display_name))
        return {
            'name': self.env._('Asiento de planilla por lote'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.run.move.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payslip_run_id': self.id},
        }

    # ------------------------------------------------------------------
    # Núcleo: agregación ORM (reemplaza la vista SQL payslip_run_move)
    # ------------------------------------------------------------------
    def _pe_get_batch_slips(self):
        """Boletas del lote que entran al asiento.

        v18 tomaba todas las líneas del lote sin filtrar estado; aquí se
        excluyen solo las anuladas.
        """
        self.ensure_one()
        return self.slip_ids.filtered(lambda slip: slip.state != 'cancel')

    def _pe_prepare_batch_move_lines(self, with_analytic=None):
        """Agrega ``hr.payslip.line`` del lote en líneas de asiento.

        Paridad con ``payslip_run_move(payslip_run_id, company_id)`` v18
        (y su variante ``payslip_run_analytic_move``), en tres bloques:

        1. **Cargo** por ``account_debit`` de cada regla, agrupado por
           (regla, cuenta[, distribución analítica]).
        2. **Abono** por ``account_credit`` (excluyendo reglas AFP),
           agrupado igual; las reglas con ``employee_move_line`` se
           detallan por trabajador con su partner (v18:
           ``is_detail_cta`` + ``he.user_partner_id``).
        3. **Abono AFP**: reglas de ``afp_rule_ids`` imputadas a la
           cuenta de la afiliación (una línea por ``hr.membership``),
           con secuencia fija 58.

        :param with_analytic: fuerza el modo analítico; ``None`` usa el
            flag ``detail_analytic`` de ``hr.main.parameter``.
        :return: lista de dicts con claves ``sequence``,
            ``salary_rule_id``, ``name``, ``account_id``, ``partner_id``,
            ``analytic_distribution``, ``debit`` y ``credit``.
        """
        self.ensure_one()
        company = self.company_id
        param = self.env['hr.main.parameter'].get_main_parameter(company)
        if with_analytic is None:
            with_analytic = param.detail_analytic
        afp_rules = param.afp_rule_ids

        groups = {}
        missing_afp_account = []

        def accumulate(key, amount, **vals):
            group = groups.setdefault(key, dict(vals, amount=0.0))
            group['amount'] += amount

        for slip in self._pe_get_batch_slips():
            version = slip.version_id
            for line in slip.line_ids:
                # Igual que el flujo nativo, solo cuentan las líneas con
                # categoría (resultados de reglas reales).
                if not line.category_id or not line.total:
                    continue
                # with_company: account_debit/account_credit son
                # company_dependent en v19 (la regla ya no tiene
                # company_id).
                rule = line.salary_rule_id.with_company(company)
                total = line.total
                distribution = False
                if with_analytic:
                    # Misma precedencia que el nativo
                    # (_prepare_line_values): regla > hr.version.
                    # TODO(fase5-revisar): v18 solo desdoblaba cuentas
                    # con check_moorage (account.account); en v19 la
                    # aplicabilidad analítica por cuenta la gobiernan
                    # los planes analíticos nativos.
                    distribution = (rule.analytic_distribution
                                    or version.analytic_distribution
                                    or False)
                dist_key = (json.dumps(distribution, sort_keys=True)
                            if distribution else False)

                # Bloque 1: cargo por cuenta de débito de la regla
                # (v18: sin exclusión de códigos AFP).
                if rule.account_debit:
                    accumulate(
                        ('debit', rule.id, rule.account_debit.id, dist_key),
                        total,
                        sequence=rule.sequence,
                        salary_rule_id=rule.id,
                        name=rule.name,
                        account_id=rule.account_debit.id,
                        partner_id=False,
                        analytic_distribution=distribution,
                        side='debit',
                    )

                # Bloque 3: abono AFP a la cuenta de la afiliación (la
                # cuenta de crédito de la regla se ignora, como en v18).
                if rule in afp_rules:
                    membership = version.membership_id
                    account = (membership.with_company(company).account_id
                               if membership else False)
                    if not account:
                        # TODO(fase5-revisar): v18 descartaba en
                        # silencio estas líneas (el descuadre acababa en
                        # la línea de ajuste); aquí se detiene el
                        # proceso para no perder importes.
                        missing_afp_account.append(self.env._(
                            '%(employee)s (afiliación: %(membership)s)',
                            employee=slip.employee_id.display_name,
                            membership=membership.name or self.env._(
                                'sin afiliación')))
                        continue
                    accumulate(
                        ('afp', membership.id, account.id),
                        total,
                        sequence=AFP_MOVE_SEQUENCE,
                        salary_rule_id=False,
                        name=membership.name,
                        account_id=account.id,
                        partner_id=False,
                        # v18: el bloque AFP nunca llevaba analítica
                        # (cuenta de pasivo).
                        analytic_distribution=False,
                        side='credit',
                    )
                # Bloque 2b: detalle por trabajador (v18 is_detail_cta →
                # flag nativo employee_move_line).
                elif rule.account_credit and rule.employee_move_line:
                    # TODO(fase5-revisar): v18 usaba he.user_partner_id;
                    # el nativo v19 usa work_contact_id — se sigue al
                    # nativo.
                    partner = slip.employee_id.work_contact_id
                    accumulate(
                        ('detail', rule.id, rule.account_credit.id,
                         partner.id),
                        total,
                        sequence=rule.sequence,
                        salary_rule_id=rule.id,
                        name=rule.name,
                        account_id=rule.account_credit.id,
                        partner_id=partner.id,
                        # v18: las líneas detalladas iban sin analítica.
                        analytic_distribution=False,
                        side='credit',
                    )
                # Bloque 2: abono agregado por cuenta de crédito.
                elif rule.account_credit:
                    accumulate(
                        ('credit', rule.id, rule.account_credit.id,
                         dist_key),
                        total,
                        sequence=rule.sequence,
                        salary_rule_id=rule.id,
                        name=rule.name,
                        account_id=rule.account_credit.id,
                        partner_id=False,
                        analytic_distribution=distribution,
                        side='credit',
                    )

        if missing_afp_account:
            raise UserError(self.env._(
                'Los siguientes trabajadores tienen aportes AFP pero su '
                'afiliación no tiene cuenta contable configurada para '
                'la compañía %(company)s:\n- %(employees)s',
                company=company.display_name,
                employees='\n- '.join(sorted(set(missing_afp_account)))))

        # Redondeo por grupo (v18: round(sum(total), 2) en el SQL) y
        # normalización de signos: account.move.line no admite importes
        # negativos, así que un grupo negativo cambia de columna (mismo
        # criterio que el nativo _prepare_slip_lines).
        lines = []
        for vals in groups.values():
            amount = custom_round(vals.pop('amount'))
            if not amount:
                # v18: WHERE debit != 0 OR credit != 0.
                continue
            side = vals.pop('side')
            if side == 'debit':
                debit, credit = (amount, 0.0) if amount > 0 \
                    else (0.0, -amount)
            else:
                debit, credit = (0.0, amount) if amount > 0 \
                    else (-amount, 0.0)
            vals.update(debit=debit, credit=credit)
            lines.append(vals)
        lines.sort(key=lambda vals: (vals['sequence'], vals['name'] or ''))
        return lines

    # ------------------------------------------------------------------
    # Generación del asiento
    # ------------------------------------------------------------------
    def _pe_get_batch_move_ref(self):
        """Referencia del asiento: ``PLA`` + MM + AAAA (paridad v18).

        v18: ``'PLA' + periodo.code[4:6] + periodo.code[0:4]`` con el
        código de periodo en formato AAAAMM. Sin periodo se deriva de
        ``date_end``.
        """
        self.ensure_one()
        code = self.periodo_id.code or ''
        if len(code) >= 6:
            return 'PLA%s%s' % (code[4:6], code[0:4])
        if self.date_end:
            return self.date_end.strftime('PLA%m%Y')
        return self.name

    def _pe_generate_batch_move(self, adjust_account=None,
                                with_analytic=None):
        """Crea y publica el asiento único del lote.

        Paridad con ``hr.payslip.run.move.wizard.generate_move`` v18:
        diario y partner por defecto de ``hr.main.parameter``, fecha =
        fin del lote, línea «Ajuste por Redondeo» contra la cuenta de
        ajuste si debe y haber difieren.

        Cambios v19: el asiento se enlaza en el ``move_id`` nativo del
        lote y de sus boletas (igual que el modo *batch* nativo), con lo
        que anular una boleta revierte/elimina el asiento compartido.

        TODO(fase5-revisar): v18 además forzaba ``run.state = 'close'``
        y marcaba las boletas como hechas; en v19 los estados los
        gobierna el flujo nativo (``action_validate`` del lote) y no se
        tocan aquí.
        """
        self.ensure_one()
        if self.move_id:
            raise UserError(self.env._(
                'El lote ya tiene un asiento contable. Anúlelo y '
                'elimínelo para generar uno nuevo.'))
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        param.check_batch_move_values()

        lines = self._pe_prepare_batch_move_lines(
            with_analytic=with_analytic)
        if not lines:
            raise UserError(self.env._(
                'El lote no tiene líneas contabilizables: revise las '
                'cuentas de las reglas salariales y que las boletas '
                'estén calculadas.'))

        total_debit = custom_round(sum(l['debit'] for l in lines))
        total_credit = custom_round(sum(l['credit'] for l in lines))
        difference = custom_round(abs(total_debit - total_credit))
        currency = self.company_id.currency_id

        line_vals = [{
            'account_id': line['account_id'],
            'name': line['name'] or '/',
            'partner_id': line['partner_id'] or param.move_partner_id.id,
            'analytic_distribution': line['analytic_distribution'] or False,
            'debit': line['debit'],
            'credit': line['credit'],
        } for line in lines]

        if not currency.is_zero(difference):
            if not adjust_account:
                raise UserError(self.env._(
                    'El asiento no cuadra (diferencia %(diff)s): '
                    'indique una cuenta de ajuste por redondeo.',
                    diff=difference))
            line_vals.append({
                'account_id': adjust_account.id,
                'name': self.env._('Ajuste por Redondeo'),
                'partner_id': param.move_partner_id.id,
                'debit': difference if total_credit > total_debit else 0.0,
                'credit': difference if total_debit > total_credit else 0.0,
            })

        # sudo como el nativo (_create_account_move): el gestor de
        # nómina puede no tener permisos contables.
        move = self.env['account.move'].sudo().create({
            'journal_id': param.move_journal_id.id,
            'date': self.date_end,
            'ref': self._pe_get_batch_move_ref(),
            'line_ids': [(0, 0, vals) for vals in line_vals],
        })
        move.action_post()
        self.move_id = move
        # Igual que el modo batch nativo: el mismo asiento en todas las
        # boletas y la fecha contable sincronizada.
        self._pe_get_batch_slips().write({
            'move_id': move.id,
            'date': self.date_end,
        })
        return move
