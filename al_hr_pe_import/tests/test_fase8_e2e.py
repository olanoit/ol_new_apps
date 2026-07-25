# -*- coding: utf-8 -*-
"""Fase 8: prueba extremo a extremo multicompañía de la suite PE.

Dos compañías peruanas (Alfa y Beta, moneda PEN) con datos totalmente
independientes recorren un periodo completo cada una:

    nómina (lotes mensuales Nov-2025 → Abr-2026 con ``periodo_id``)
    → BBSS (CTS semestral vía el motor ``compute_benefits``)
    → asiento contable único del lote (al_hr_pe_account)
    → datos de la boleta de pago (``_get_voucher_report_data``).

El caso de referencia es el mismo de las fases 2-5 (régimen general,
sueldo estable, sin variables): las expectativas se derivan de las
fórmulas, no de números mágicos. Además, un trabajador de Alfa lleva
una retención judicial (input RET_JUD) para ejercitar la categoría
DES_NET de punta a punta (boleta y asiento).

El setup NO hereda de ``BenefitsCaseBase`` (al_hr_pe_benefits): esa
clase fija UNA compañía en ``cls.env``; aquí el mismo pipeline se
replica por compañía con ``with_company`` para poder afirmar el
aislamiento cruzado (lo de Alfa no aparece en Beta y viceversa).
"""
from datetime import date

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_hr_pe.tools import custom_round

#: Semestre CTS Nov-2025 → Abr-2026 (año, mes, último día del mes).
MESES_SEMESTRE_CTS = [
    (2025, 11, 30), (2025, 12, 31), (2026, 1, 31),
    (2026, 2, 28), (2026, 3, 31), (2026, 4, 30),
]
#: Retención judicial del trabajador 1 de Alfa en la boleta de Abril.
IMPORTE_RET_JUD = 50.0


@tagged('post_install', '-at_install')
class TestFase8E2EMulticompania(TransactionCase):
    """2 compañías, 1 periodo completo: nómina → BBSS → asientos →
    boletas, con aserciones cruzadas de aislamiento multicompañía."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # --- Moneda PEN activa y dos compañías peruanas ---
        cls.pen = cls.env.ref('base.PEN')
        cls.pen.active = True
        Company = cls.env['res.company']
        cls.company_a = Company.create({
            'name': 'PE E2E Alfa SAC',
            'country_id': cls.env.ref('base.pe').id,
            'currency_id': cls.pen.id,
        })
        cls.company_b = Company.create({
            'name': 'PE E2E Beta SAC',
            'country_id': cls.env.ref('base.pe').id,
            'currency_id': cls.pen.id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company_a.id, cls.company_b.id]))
        cls.env.user.company_ids |= cls.company_a | cls.company_b
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')

        # --- Datos maestros compartidos (las reglas no tienen compañía
        # en v19; sus cuentas son company_dependent) ---
        cls.structure = cls.env.ref('al_hr_pe.base_structure')
        Rule = cls.env['hr.salary.rule']

        def _regla(code):
            return Rule.search([
                ('code', '=', code),
                ('struct_id', '=', cls.structure.id)], limit=1)

        cls.rule_bas = _regla('BAS')
        cls.rule_neto = _regla('NETO')
        cls.rule_ret_jud = _regla('RET_JUD')
        cls.afp_rules = Rule.browse()
        for code in ('A_JUB', 'COMFI', 'COMMIX', 'SEGI'):
            cls.afp_rules |= _regla(code)
        cls.afp = cls.env['hr.membership'].search(
            [('is_afp', '=', True), ('company_id', '=', False)], limit=1)
        cls.input_ret_jud = cls.env.ref('al_hr_pe.input_type_RET_JUD')
        # Reglas de variables en estructura aparte: el caso de referencia
        # no tiene comisiones/bonos (promedios = 0). Compartidas.
        cls.dummy_comis = cls._regla_auxiliar('TCOMIS')
        cls.dummy_bono = cls._regla_auxiliar('TBON')

        # --- Pipeline completo por compañía ---
        cls.a = cls._configurar_compania(
            cls.company_a,
            [('Rosa', 'Huamán', 'Cruz', 3000.0),
             ('Julio', 'Paredes', 'Soto', 2000.0)],
            con_ret_jud=True)
        cls.b = cls._configurar_compania(
            cls.company_b,
            [('Carmen', 'Flores', 'Díaz', 4000.0)],
            con_ret_jud=False)

    # ------------------------------------------------------------------
    # Helpers de setup
    # ------------------------------------------------------------------
    @classmethod
    def _regla_auxiliar(cls, code):
        """Regla 0.0 en estructura auxiliar (patrón de la Fase 3)."""
        struct = cls.env['hr.payroll.structure'].create({
            'name': 'Aux %s' % code,
            'type_id': cls.structure.type_id.id,
        })
        return cls.env['hr.salary.rule'].create({
            'name': code, 'code': code,
            'category_id': cls.env.ref('al_hr_pe.ING').id,
            'struct_id': struct.id, 'sequence': 5,
            'amount_select': 'fix', 'amount_fix': 0.0,
        })

    @classmethod
    def _configurar_compania(cls, company, empleados, con_ret_jud):
        """Parámetros, plan contable mínimo, empleados, periodos y
        lotes mensuales Nov-2025 → Abr-2026 (boletas calculadas y
        confirmadas) de UNA compañía. Devuelve un dict con todo."""
        env = cls.env
        Rule = env['hr.salary.rule']

        # Parámetros principales de la compañía (motor de BBSS + boleta)
        param = env['hr.main.parameter'].create({
            'company_id': company.id, 'rmv': 1130.0,
            'basic_sr_id': cls.rule_bas.id,
            'household_allowance_sr_id':
                Rule.search([('code', '=', 'AF')], limit=1).id,
            'extra_hours_sr_id':
                Rule.search([('code', '=', 'HE25')], limit=1).id,
            'commission_sr_ids': [(6, 0, cls.dummy_comis.ids)],
            'bonus_sr_ids': [(6, 0, cls.dummy_bono.ids)],
            'cts_input_id': env['hr.payslip.input.type'].search(
                [], limit=1).id,
            'gratification_input_id':
                env['hr.payslip.input.type'].search([], limit=1).id,
            'bonus_nine_input_id':
                env['hr.payslip.input.type'].search([], limit=1).id,
            'lack_wd_ids': [(6, 0, env['hr.work.entry.type'].search(
                [('code', '=', 'FAL')]).ids)],
            'working_wd_ids': [(6, 0, env['hr.work.entry.type'].search(
                [('code', 'in', ('DLAB', 'DOM'))]).ids)],
            # La boleta lee el neto de esta regla (fallback: net_wage
            # nativo, que la estructura BASE portada no alimenta).
            'net_to_pay_sr_id': cls.rule_neto.id,
        })

        # Plan contable mínimo de la compañía
        Account = env['account.account'].with_company(company)

        def _cuenta(code, name, tipo):
            return Account.create(
                {'code': code, 'name': name, 'account_type': tipo})

        cuentas = {
            'gasto': _cuenta('621000', 'Gasto planilla', 'expense'),
            'neto': _cuenta('411000', 'Remuneraciones por pagar',
                            'liability_current'),
            'afp': _cuenta('403000', 'AFP por pagar', 'liability_current'),
            'retjud': _cuenta('427000', 'Retenciones judiciales',
                              'liability_current'),
            'ajuste': _cuenta('659000', 'Ajuste por redondeo', 'expense'),
        }
        journal = env['account.journal'].create({
            'name': 'Planillas', 'code': 'PLAN', 'type': 'general',
            'company_id': company.id})

        # Cuentas company_dependent: reglas y afiliación AFP se asignan
        # POR compañía con with_company (aserción cruzada en test_05).
        cls.rule_bas.with_company(company).account_debit = cuentas['gasto']
        cls.rule_neto.with_company(company).account_credit = cuentas['neto']
        cls.rule_ret_jud.with_company(company).account_credit = \
            cuentas['retjud']
        cls.afp.with_company(company).account_id = cuentas['afp']
        param.write({
            'move_journal_id': journal.id,
            'move_partner_id': company.partner_id.id,
            'afp_rule_ids': [(6, 0, cls.afp_rules.ids)],
        })

        # Empleados con hr.version (campos PE: sueldo, AFP, régimen
        # general por defecto)
        Employee = env['hr.employee'].with_company(company)
        trabajadores = env['hr.employee']
        wages = {}
        for names, last_name, m_last_name, wage in empleados:
            emp = Employee.create({
                'names': names, 'last_name': last_name,
                'm_last_name': m_last_name,
                'company_id': company.id,
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'wage': wage,
                'structure_type_id': cls.structure.type_id.id,
            })
            emp.version_id.membership_id = cls.afp
            trabajadores |= emp
            wages[emp.id] = wage

        # Periodos 2025-2026 (el motor de BBSS exige el de cierre)
        for year in (2025, 2026):
            env['hr.period.generator'].create({
                'year': year, 'company_id': company.id,
            }).action_generate()

        # Lotes mensuales del semestre CTS con periodo_id: el motor
        # selecciona empleados vía el LOTE del periodo de cierre y
        # cuenta los meses por los lotes del semestre.
        lotes = {}
        boletas = env['hr.payslip']
        boleta_ret_jud = env['hr.payslip']
        for year, month, last in MESES_SEMESTRE_CTS:
            periodo = env['hr.period'].search([
                ('code', '=', '%04d%02d' % (year, month)),
                ('company_id', '=', company.id)], limit=1)
            lote = env['hr.payslip.run'].create({
                'name': 'Lote %s %s-%02d' % (company.name, year, month),
                'date_start': date(year, month, 1),
                'date_end': date(year, month, last),
                'company_id': company.id,
                'periodo_id': periodo.id,
            })
            for emp in trabajadores:
                vals = {
                    'name': 'Boleta %s %s-%02d' % (emp.names, year, month),
                    'employee_id': emp.id,
                    'struct_id': cls.structure.id,
                    'date_from': date(year, month, 1),
                    'date_to': date(year, month, last),
                    'payslip_run_id': lote.id,
                }
                # Retención judicial solo en Abril del trabajador 1 de
                # Alfa: ejercita DES_NET en boleta y asiento.
                if (con_ret_jud and emp == trabajadores[0]
                        and (year, month) == (2026, 4)):
                    vals['input_line_ids'] = [(0, 0, {
                        'input_type_id': cls.input_ret_jud.id,
                        'amount': IMPORTE_RET_JUD,
                    })]
                slip = env['hr.payslip'].with_company(company).create(vals)
                slip.compute_sheet()
                slip.action_payslip_done()
                boletas |= slip
                if vals.get('input_line_ids'):
                    boleta_ret_jud = slip
            lotes[(year, month)] = lote

        return {
            'company': company, 'param': param, 'journal': journal,
            'cuentas': cuentas, 'empleados': trabajadores, 'wages': wages,
            'lotes': lotes, 'batch': lotes[(2026, 4)], 'boletas': boletas,
            'boleta_ret_jud': boleta_ret_jud,
        }

    def _linea(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.code == code)

    # ------------------------------------------------------------------
    # 1. Nómina
    # ------------------------------------------------------------------
    def test_01_nomina_por_compania(self):
        """Boletas del lote calculadas por compañía: neto > 0,
        categorías presentes y cero contaminación cruzada."""
        for datos in (self.a, self.b):
            lote = datos['batch']
            self.assertEqual(
                len(lote.slip_ids), len(datos['empleados']),
                'El lote de %s no tiene una boleta por empleado'
                % datos['company'].name)
            for slip in lote.slip_ids:
                wage = datos['wages'][slip.employee_id.id]
                self.assertEqual(slip.company_id, datos['company'])
                # Básico del mes completo = sueldo
                self.assertAlmostEqual(
                    self._linea(slip, 'BAS').total, wage, places=1)
                neto = self._linea(slip, 'NETO')
                self.assertTrue(neto, 'Boleta sin línea NETO')
                self.assertGreater(neto.total, 0.0)
                # Totales PLAME por categoría (aportes reales)
                self.assertGreater(slip.worker_contributions, 0.0)
                categorias = set(slip.line_ids.mapped('category_id.code'))
                self.assertIn('ING', categorias)
                self.assertIn('APOR_TRA', categorias)
            # Todas las boletas del semestre pertenecen a SU compañía
            self.assertEqual(
                datos['boletas'].mapped('company_id'), datos['company'])

        # Retención judicial de Alfa: DES_NET con importe y neto
        # coherente (NETO = ingresos − aportes − descuentos al neto)
        slip_rj = self.a['boleta_ret_jud']
        self.assertTrue(slip_rj, 'No se creó la boleta con RET_JUD')
        linea_rj = self._linea(slip_rj, 'RET_JUD')
        self.assertAlmostEqual(
            abs(linea_rj.total), IMPORTE_RET_JUD, places=2)
        self.assertIn(
            'DES_NET', set(slip_rj.line_ids.mapped('category_id.code')))
        wage_rj = self.a['wages'][slip_rj.employee_id.id]
        self.assertAlmostEqual(
            self._linea(slip_rj, 'NETO').total,
            wage_rj - slip_rj.worker_contributions - IMPORTE_RET_JUD,
            delta=0.05)

        # Aislamiento cruzado: ningún empleado de Beta en lotes de Alfa
        self.assertFalse(
            set(self.a['boletas'].employee_id.ids)
            & set(self.b['empleados'].ids))
        self.assertFalse(
            set(self.b['boletas'].employee_id.ids)
            & set(self.a['empleados'].ids))

    # ------------------------------------------------------------------
    # 2. BBSS (motor compute_benefits vía hr.cts)
    # ------------------------------------------------------------------
    def test_02_bbss_cts_por_compania(self):
        """CTS semestral Nov-Abr por compañía con el motor de BBSS:
        6 meses, computable = sueldo, total = computable/2; las líneas
        de cada cabecera son EXACTAMENTE los empleados de su compañía."""
        cabeceras = {}
        for datos in (self.a, self.b):
            cts = self.env['hr.cts'].with_company(datos['company']).create({
                'company_id': datos['company'].id,
                'year': 2026,
                'type': '05',  # semestre Nov-Abr
                'payslip_run_id': datos['batch'].id,
                'deposit_date': date(2026, 5, 15),
            })
            cts.get_cts()
            # El motor selecciona vía el lote del periodo de cierre:
            # ni un empleado de más (otra compañía) ni de menos.
            self.assertEqual(
                set(cts.line_ids.employee_id.ids),
                set(datos['empleados'].ids),
                'Las líneas CTS de %s no son sus empleados'
                % datos['company'].name)
            for line in cts.line_ids:
                wage = datos['wages'][line.employee_id.id]
                # Semestre completo con 6 lotes mensuales
                self.assertEqual(line.months, 6)
                self.assertEqual(line.days, 0)
                # Sin grati previa ni variables: computable = sueldo
                self.assertAlmostEqual(
                    line.computable_remuneration, wage, places=1)
                # 6 meses → computable/12 × 6 = computable/2
                self.assertAlmostEqual(
                    line.total_cts, wage / 2, delta=1.0)
            cabeceras[datos['company']] = cts
        # Aislamiento: cabeceras y líneas separadas por compañía
        cts_a = cabeceras[self.company_a]
        cts_b = cabeceras[self.company_b]
        self.assertNotEqual(cts_a, cts_b)
        self.assertFalse(
            set(cts_a.line_ids.employee_id.ids)
            & set(cts_b.line_ids.employee_id.ids))

    # ------------------------------------------------------------------
    # 3. Asientos contables (al_hr_pe_account)
    # ------------------------------------------------------------------
    def test_03_asiento_lote_por_compania(self):
        """Asiento único del lote por compañía: cuadrado, en SU diario
        y SUS cuentas, enlazado al move_id del lote y sus boletas."""
        for datos in (self.a, self.b):
            lote = datos['batch'].with_company(datos['company'])
            lote._pe_generate_batch_move(
                adjust_account=datos['cuentas']['ajuste'])
            move = lote.move_id
            self.assertTrue(move, 'El lote de %s no tiene asiento'
                            % datos['company'].name)
            self.assertEqual(move.state, 'posted')
            self.assertEqual(move.ref, 'PLA042026')
            self.assertEqual(move.journal_id, datos['journal'])
            self.assertEqual(move.company_id, datos['company'])
            # Cuadrado: debe = haber
            total_debit = sum(move.line_ids.mapped('debit'))
            total_credit = sum(move.line_ids.mapped('credit'))
            self.assertAlmostEqual(total_debit, total_credit, places=2)

            def haber(cuenta, move=move):
                return sum(move.line_ids.filtered(
                    lambda l: l.account_id == cuenta).mapped('credit'))

            # Bloque 1 (cargo): gasto BAS = suma de sueldos del mes
            total_sueldos = sum(datos['wages'].values())
            gasto = sum(move.line_ids.filtered(
                lambda l: l.account_id == datos['cuentas']['gasto']
            ).mapped('debit'))
            self.assertAlmostEqual(gasto, total_sueldos, places=2)
            # Bloque 3 (AFP): abono a la cuenta de la afiliación
            aportes_afp = haber(datos['cuentas']['afp'])
            self.assertGreater(aportes_afp, 0.0)
            # Bloque 2 (abonos): neto + AFP + ret. judicial = sueldos
            self.assertAlmostEqual(
                haber(datos['cuentas']['neto']) + aportes_afp
                + haber(datos['cuentas']['retjud']),
                total_sueldos, delta=0.05)
            # Enlace nativo del asiento en lote y boletas
            for slip in lote.slip_ids:
                self.assertEqual(slip.move_id, move)
        # La retención judicial solo abona en el asiento de Alfa
        move_a = self.a['batch'].move_id
        move_b = self.b['batch'].move_id
        self.assertAlmostEqual(
            sum(move_a.line_ids.filtered(
                lambda l: l.account_id == self.a['cuentas']['retjud']
            ).mapped('credit')), IMPORTE_RET_JUD, places=2)
        # Aislamiento: asientos distintos, sin cuentas compartidas
        self.assertNotEqual(move_a, move_b)
        self.assertFalse(
            set(move_a.line_ids.account_id.ids)
            & set(move_b.line_ids.account_id.ids),
            'El asiento de una compañía usa cuentas de la otra')

    # ------------------------------------------------------------------
    # 4. Boletas de pago (al_hr_pe_reports)
    # ------------------------------------------------------------------
    def test_04_boleta_datos_y_qweb(self):
        """`_get_voucher_report_data`: totales por columna = suma de
        sus líneas, neto = regla NETO y render QWeb sin excepción."""
        for datos in (self.a, self.b):
            slip = datos['batch'].slip_ids[0]
            data = slip._get_voucher_report_data()
            # El voucher usa los parámetros de SU compañía
            self.assertEqual(data['param'], datos['param'])
            # Totales por columna coherentes con las filas alineadas
            ingresos = [f[0] for f in data['filas'] if f[0]]
            descuentos = [f[1] for f in data['filas'] if f[1]]
            aportes = [f[2] for f in data['filas'] if f[2]]
            self.assertAlmostEqual(
                data['total_ingresos'],
                custom_round(sum(l['importe'] for l in ingresos)),
                places=2)
            self.assertAlmostEqual(
                data['total_descuentos'],
                custom_round(sum(l['importe'] for l in descuentos)),
                places=2)
            self.assertAlmostEqual(
                data['total_aportes'],
                custom_round(sum(l['importe'] for l in aportes)),
                places=2)
            self.assertGreater(data['total_ingresos'], 0.0)
            self.assertGreater(data['total_descuentos'], 0.0)
            # Neto = regla NETO configurada en parámetros y coherente
            # con las columnas (NETO = TINGR − TDES)
            self.assertAlmostEqual(
                data['neto'],
                custom_round(self._linea(slip, 'NETO').total), places=2)
            self.assertAlmostEqual(
                data['neto'],
                data['total_ingresos'] - data['total_descuentos'],
                delta=0.1)
            self.assertTrue(data['neto_letras'].startswith('SON:'))
            self.assertGreater(data['dias_laborados'], 0)
            # Render HTML del QWeb (el PDF es pesado para un e2e)
            html = self.env['ir.actions.report']._render_qweb_html(
                'al_hr_pe_reports.action_report_boleta_pago', slip.ids)[0]
            texto = html.decode() if isinstance(html, bytes) else str(html)
            self.assertIn('Boleta de pago emitida conforme', texto)

        # La retención judicial (SUNAT 0703) sale en la columna de
        # descuentos de la boleta de Alfa
        data_rj = self.a['boleta_ret_jud']._get_voucher_report_data()
        descuentos_rj = [f[1] for f in data_rj['filas'] if f[1]]
        self.assertIn(
            ('0703', IMPORTE_RET_JUD),
            [(l['codigo'], l['importe']) for l in descuentos_rj],
            'La boleta no muestra la retención judicial 0703')

    # ------------------------------------------------------------------
    # 5. Aislamiento multicompañía
    # ------------------------------------------------------------------
    def test_05_aislamiento_multicompania(self):
        """Un usuario restringido a Beta no ve nómina de Alfa; las
        cuentas company_dependent difieren entre compañías."""
        usuario_b = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Gestor Beta', 'login': 'fase8.gestor.beta',
                'company_id': self.company_b.id,
                'company_ids': [(6, 0, self.company_b.ids)],
                'group_ids': [(6, 0, (
                    self.env.ref('base.group_user')
                    | self.env.ref('hr_payroll.group_hr_payroll_manager')
                ).ids)],
            })

        def como_beta(model):
            return self.env[model].with_user(usuario_b).with_context(
                allowed_company_ids=self.company_b.ids)

        # Boletas: de todas las del semestre solo ve las de Beta
        todas = self.a['boletas'] | self.b['boletas']
        visibles = como_beta('hr.payslip').search(
            [('id', 'in', todas.ids)])
        self.assertEqual(set(visibles.ids), set(self.b['boletas'].ids),
                         'El usuario de Beta ve boletas de Alfa')
        # Lotes y empleados de Alfa invisibles
        self.assertFalse(como_beta('hr.payslip.run').search(
            [('id', 'in', self.a['batch'].ids)]))
        self.assertFalse(como_beta('hr.employee').search(
            [('id', 'in', self.a['empleados'].ids)]))
        # Leer una boleta de Alfa directamente debe fallar
        with self.assertRaises(AccessError):
            self.a['boletas'][0].with_user(usuario_b).with_context(
                allowed_company_ids=self.company_b.ids).read(['name'])

        # Cuentas company_dependent: cada compañía resuelve la SUYA
        self.assertNotEqual(
            self.afp.with_company(self.company_a).account_id,
            self.afp.with_company(self.company_b).account_id)
        self.assertEqual(
            self.afp.with_company(self.company_a).account_id,
            self.a['cuentas']['afp'])
        self.assertEqual(
            self.afp.with_company(self.company_b).account_id,
            self.b['cuentas']['afp'])
        self.assertNotEqual(
            self.rule_bas.with_company(self.company_a).account_debit,
            self.rule_bas.with_company(self.company_b).account_debit)
        self.assertNotEqual(
            self.rule_neto.with_company(self.company_a).account_credit,
            self.rule_neto.with_company(self.company_b).account_credit)
        # Parámetros principales separados por compañía
        Param = self.env['hr.main.parameter']
        self.assertEqual(
            Param.get_main_parameter(self.company_a), self.a['param'])
        self.assertEqual(
            Param.get_main_parameter(self.company_b), self.b['param'])
        self.assertNotEqual(self.a['param'], self.b['param'])
