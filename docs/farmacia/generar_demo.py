"""Genera los datos de demostración de la suite de farmacia.

Cada módulo lleva los registros que necesita para probarse solo (con sus
dependencias): instalar uno con datos de demostración basta para recorrer
sus pantallas, sus reportes y su guion de prueba. El catálogo es el de una
botica con marcas y laboratorios inventados y precios en soles.

Uso (desde la raíz del repositorio)::

    python3 docs/farmacia/generar_demo.py          # escribe los demo/*.xml
    python3 docs/farmacia/generar_demo.py --check  # ¿están al día?
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]

LABS = {
    'lab_andino': 'Laboratorios Andinos S.A.C.',
    'lab_rimac': 'Laboratorio Rímac S.A.C.',
    'lab_sol': 'Laboratorios Sol del Sur S.A.C.',
}
INGREDIENTS = {
    'ingredient_paracetamol': 'Paracetamol', 'ingredient_ibuprofeno': 'Ibuprofeno',
    'ingredient_amoxicilina': 'Amoxicilina', 'ingredient_insulina_humana': 'Insulina humana',
    'ingredient_azitromicina': 'Azitromicina', 'ingredient_losartan': 'Losartán',
    'ingredient_metformina': 'Metformina', 'ingredient_clonazepam': 'Clonazepam',
    'ingredient_alprazolam': 'Alprazolam', 'ingredient_loratadina': 'Loratadina',
    'ingredient_omeprazol': 'Omeprazol',
}
# (xmlid, nombre, tipo, condición, [(ingrediente, concentración, unidad)], forma, vía,
#  precio por unidad, costo, [(presentación, unidades, precio)], registro sanitario,
#  código DIGEMID, extra)
PRODUCTS = [
    ('product_paracetamol', 'Paracetamol 500 mg tableta', 'generic_dci', 'otc',
     [('ingredient_paracetamol', 500, 'mg')], 'tablet', 'oral', 0.20, 0.08,
     [('Blíster', 10, 1.50), ('Caja', 100, 12.00)], 'EN-04512', '05463', {'categ': 'otc'}),
    ('product_dolofen', 'Dolofen 500 mg tableta', 'innovator', 'otc',
     [('ingredient_paracetamol', 500, 'mg')], 'tablet', 'oral', 0.60, 0.30,
     [('Blíster', 10, 5.50), ('Caja', 100, 50.00)], 'E-21876', '05464', {'lab': 'lab_rimac', 'categ': 'otc'}),
    ('product_ibuprofen', 'Ibuprofeno 400 mg tableta', 'generic_dci', 'otc',
     [('ingredient_ibuprofeno', 400, 'mg')], 'tablet', 'oral', 0.25, 0.10,
     [('Blíster', 10, 2.00), ('Caja', 100, 15.00)], 'EN-03891', '04120', {'categ': 'otc'}),
    ('product_ibuflam', 'Ibuflam 400 mg tableta', 'generic_brand', 'otc',
     [('ingredient_ibuprofeno', 400, 'mg')], 'tablet', 'oral', 0.45, 0.20,
     [('Blíster', 10, 4.00)], 'EG-07722', '04121', {'lab': 'lab_sol', 'categ': 'otc'}),
    ('product_loratadine', 'Loratadina 10 mg tableta', 'generic_dci', 'otc',
     [('ingredient_loratadina', 10, 'mg')], 'tablet', 'oral', 0.30, 0.10,
     [('Blíster', 10, 2.50)], 'EN-06102', '06210', {'categ': 'otc'}),
    ('product_omeprazole', 'Omeprazol 20 mg cápsula', 'generic_dci', 'otc',
     [('ingredient_omeprazol', 20, 'mg')], 'capsule', 'oral', 0.30, 0.12,
     [('Blíster', 10, 2.50), ('Caja', 100, 22.00)], 'EN-05988', '06015', {'categ': 'otc'}),
    ('product_amoxicillin', 'Amoxicilina 500 mg cápsula', 'generic_dci', 'prescription',
     [('ingredient_amoxicilina', 500, 'mg')], 'capsule', 'oral', 0.50, 0.22,
     [('Blíster', 10, 4.50), ('Caja', 100, 40.00)], 'EN-05127', '01287', {'categ': 'rx'}),
    ('product_amoxival', 'Amoxival 500 mg cápsula', 'innovator', 'prescription',
     [('ingredient_amoxicilina', 500, 'mg')], 'capsule', 'oral', 1.40, 0.70,
     [('Blíster', 10, 13.00)], 'E-18350', '01288', {'lab': 'lab_andino', 'categ': 'rx'}),
    ('product_azithromycin', 'Azitromicina 500 mg tableta', 'generic_dci', 'prescription',
     [('ingredient_azitromicina', 500, 'mg')], 'coated_tablet', 'oral', 3.00, 1.20,
     [('Caja', 3, 8.00)], 'EN-04410', '02954', {'categ': 'rx'}),
    ('product_losartan', 'Losartán 50 mg tableta', 'generic_dci', 'prescription',
     [('ingredient_losartan', 50, 'mg')], 'coated_tablet', 'oral', 0.30, 0.10,
     [('Blíster', 10, 2.50), ('Caja', 100, 20.00)], 'EN-05341', '03322', {'categ': 'rx'}),
    ('product_metformin', 'Metformina 850 mg tableta', 'generic_dci', 'prescription',
     [('ingredient_metformina', 850, 'mg')], 'tablet', 'oral', 0.25, 0.09,
     [('Blíster', 10, 2.00), ('Caja', 100, 18.00)], 'EN-04987', '03510', {'igv': 'diabetes', 'categ': 'rx'}),
    ('product_insulin', 'Insulina humana NPH 100 UI/mL frasco 10 mL', 'generic_dci', 'prescription',
     [('ingredient_insulina_humana', 100, 'ui')], 'injection', 'sc', 58.00, 41.00,
     [], 'BE-01046', '03601', {'igv': 'diabetes', 'cold': True, 'categ': 'rx'}),
    ('product_clonazepam', 'Clonazepam 2 mg tableta', 'generic_dci', 'prescription',
     [('ingredient_clonazepam', 2, 'mg')], 'tablet', 'oral', 0.80, 0.30,
     [('Blíster', 10, 7.50)], 'EN-03117', '02210', {'control': 'IVA', 'categ': 'controlled'}),
    ('product_alprazolam', 'Alprazolam 0,5 mg tableta', 'generic_dci', 'prescription',
     [('ingredient_alprazolam', 0.5, 'mg')], 'tablet', 'oral', 0.60, 0.25,
     [('Blíster', 10, 5.50)], 'EN-03205', '02215', {'control': 'IVA', 'categ': 'controlled'}),
]
TRACKED = [p[0] for p in PRODUCTS]
ESSENTIAL = [('ingredient_paracetamol', '500 mg', 'tablet'), ('ingredient_ibuprofeno', '400 mg', 'tablet'),
             ('ingredient_amoxicilina', '500 mg', 'capsule'), ('ingredient_losartan', '50 mg', 'coated_tablet'),
             ('ingredient_metformina', '850 mg', 'tablet'), ('ingredient_omeprazol', '20 mg', 'capsule')]
PRESCRIBERS = [
    ('prescriber_torres', 'Dra. Ana Torres Quispe', '067890', 'Medicina interna', 'enabled'),
    ('prescriber_salazar', 'Dr. Jorge Salazar Pérez', '045678', 'Pediatría', False),
    ('prescriber_rojas', 'Dr. Martín Rojas León', '031245', 'Psiquiatría', 'disabled'),
]

BASE = 'al_pharmacy_base'


def x(text):
    return escape(str(text), {'"': '&quot;'})


def ref(xmlid):
    return xmlid if '.' in xmlid else f'{BASE}.{xmlid}'


def variant(xmlid):
    """Variante de una plantilla de la demo (las presentaciones van en la plantilla)."""
    return f'model="product.template" eval="obj().env.ref(\'{ref(xmlid)}\').product_variant_id.id"'


def days(n, kind='datetime'):
    fmt = '%Y-%m-%d %H:%M:%S' if kind == 'datetime' else '%Y-%m-%d'
    return f'eval="(DateTime.today() + relativedelta(days={n})).strftime(\'{fmt}\')"'


def stock_location():
    return 'model="stock.location" eval="obj().env.ref(\'stock.warehouse0\').lot_stock_id.id"'


def record(xmlid, model, fields, context=None):
    attrs = f' context="{context}"' if context else ''
    out = [f'        <record id="{xmlid}" model="{model}"{attrs}>']
    for field in fields:
        out.append(f'            {field}')
    out.append('        </record>')
    return out


def f(name, value=None, **attrs):
    """<field>: valor de texto, o atributos ref/eval tal cual."""
    if 'obj()' in attrs.get('eval', '') and 'model' not in attrs:
        # obj() solo existe en un eval con modelo.
        attrs['model'] = 'product.template'
    if attrs:
        extra = ' '.join(f'{k}="{v}"' for k, v in attrs.items())
        return f'<field name="{name}" {extra}/>'
    return f'<field name="{name}">{x(value)}</field>'


def fe(name, expression):
    return f'<field name="{name}" {expression}/>'


def document(comment, body):
    return '\n'.join(['<?xml version="1.0" encoding="utf-8"?>', '<odoo>', f'    <!-- {comment} -->',
                      '    <data noupdate="1">', *body, '    </data>', '</odoo>', ''])


# ----------------------------------------------------------------------
# al_pharmacy_base: catálogo, presentaciones, existencias, personal, local
# ----------------------------------------------------------------------
def demo_base():
    body = ['        <!-- Laboratorios y principios activos -->']
    for key, name in LABS.items():
        body += record(key, 'res.partner', [f('name', name), f('is_company', eval='True')])
    for key, name in INGREDIENTS.items():
        body += record(key, 'pharmacy.ingredient', [f('name', name)])
    body.append('        <!-- Medicamentos con sus presentaciones -->')
    for (pid, name, ptype, cond, ingredients, form, route, price, cost, presentations,
         registry, _code, extra) in PRODUCTS:
        lines = ', '.join(
            f"Command.create({{'ingredient_id': ref('{i}'), 'strength': {s}, 'strength_unit': '{u}'}})"
            for i, s, u in ingredients)
        fields = [
            f('name', name), f('list_price', price), f('standard_price', cost), f('type', 'consu'),
            f('is_storable', eval='True'), f('tracking', 'lot'), f('use_expiration_date', eval='True'),
            f('expiration_time', 730), f('pharmacy_ok', eval='True'), f('pharmacy_product_type', ptype),
            f('pharmacy_sale_condition', cond), f('pharmacy_sanitary_registry', registry),
            fe('pharmacy_registry_expiry', days(900, 'date')),
            f('pharmacy_dosage_form_id', ref=f'dosage_form_{form}'),
            f('pharmacy_route_id', ref=f'route_{route}'),
            f('pharmacy_ingredient_line_ids', eval=f'[{lines}]'),
        ]
        if extra.get('lab'):
            fields.append(f('pharmacy_laboratory_id', ref=extra['lab']))
        if extra.get('cold'):
            fields += [f('pharmacy_cold_chain', eval='True'),
                       f('pharmacy_storage_conditions', 'Refrigerar entre 2 °C y 8 °C. No congelar.')]
        body += record(pid, 'product.template', fields)
        for index, (pname, factor, pprice) in enumerate(presentations, 1):
            body += record(f'{pid}_presentation_{index}', 'pharmacy.presentation', [
                f('product_tmpl_id', ref=pid), f('name', pname), f('factor', factor), f('price', pprice)])
    body.append('        <!-- Personal, local y turnos -->')
    body += record('employee_director', 'hr.employee', [
        f('name', 'Rosa Quispe Huamán'), f('job_title', 'Directora técnica'),
        f('pharmacy_role', 'pharmacist'), f('pharmacy_license_number', '15432'),
        f('work_email', 'rosa.quispe@example.com')])
    body += record('employee_pharmacist', 'hr.employee', [
        f('name', 'Luis Paredes Soto'), f('job_title', 'Químico farmacéutico'),
        f('pharmacy_role', 'pharmacist'), f('pharmacy_license_number', '18877')])
    body += record('employee_technician', 'hr.employee', [
        f('name', 'Carmen Flores Díaz'), f('job_title', 'Técnica en farmacia'),
        f('pharmacy_role', 'technician')])
    body += record('stock.warehouse0', 'stock.warehouse', [
        f('pharmacy_director_id', ref='employee_director'), f('pharmacy_establishment_code', '0123456')])
    body += record('shift_director', 'pharmacy.shift', [
        f('employee_id', ref='employee_director'), f('warehouse_id', ref='stock.warehouse0'),
        f('role', 'director'), fe('date_start', days(-1)), fe('date_end', days(30)),
        f('note', 'Lunes a sábado de 8:00 a 16:00')])
    body += record('shift_assistant', 'pharmacy.shift', [
        f('employee_id', ref='employee_pharmacist'), f('warehouse_id', ref='stock.warehouse0'),
        f('role', 'assistant'), fe('date_start', days(-1)), fe('date_end', days(30)),
        f('note', 'Lunes a sábado de 16:00 a 22:00')])
    body += record('logbook_opening', 'pharmacy.logbook.entry', [
        f('entry_type', 'other'), f('warehouse_id', ref='stock.warehouse0'), fe('date', days(-2)),
        f('description', 'Apertura del libro de ocurrencias del establecimiento.')])
    body += record('logbook_power_cut', 'pharmacy.logbook.entry', [
        f('entry_type', 'incident'), f('warehouse_id', ref='stock.warehouse0'), fe('date', days(-1)),
        f('description', 'Corte de luz de 40 minutos; la refrigeradora se mantuvo entre 2 °C y 8 °C.')])
    return document('Botica de demostración: marcas y laboratorios inventados.', body)


# ----------------------------------------------------------------------
# al_pharmacy_stock: control ambiental, compra con bonificación, lotes
# ----------------------------------------------------------------------
def demo_stock():
    body = []
    body.append('        <!-- Lotes y existencias: uno por medicamento; la amoxicilina tiene además\n'
                '             un lote que vence en 45 días (aviso «Por vencer») -->')
    quants = []
    for index, (pid, _name, *_rest) in enumerate(PRODUCTS):
        code = PRODUCTS[index][11]
        controlled = bool(PRODUCTS[index][12].get('control'))
        lots = [(f'{pid}_lot_1', f'{code}2610', 540, 30 if controlled else 500)]
        if pid == 'product_amoxicillin':
            lots.append((f'{pid}_lot_2', f'{code}2604', 45, 120))
        for lot_id, lot_name, expiry, quantity in lots:
            body += record(lot_id, 'stock.lot', [
                f('name', lot_name), fe('product_id', variant(pid)),
                fe('expiration_date', days(expiry)), f('company_id', ref='base.main_company')])
            body += record(f'{lot_id}_quant', 'stock.quant', [
                fe('product_id', variant(pid)), f('lot_id', ref=lot_id),
                f('inventory_quantity', quantity), fe('location_id', stock_location())])
            quants.append(f'{lot_id}_quant')
    ids = ', '.join(f"ref('{q}')" for q in quants)
    body += ['        <function model="stock.quant" name="action_apply_inventory">',
             f'            <function eval="[[(\'id\', \'in\', [{ids}])]]" model="stock.quant" name="search"/>',
             '        </function>']
    body.append('        <!-- Control ambiental (BPA) -->')
    body += record('environment_point_room', 'pharmacy.environment.point', [
        f('name', 'Sala de ventas'), f('warehouse_id', ref='stock.warehouse0'),
        f('equipment', 'Termohigrómetro digital TH-20'), fe('calibration_date', days(-120, 'date')),
        fe('next_calibration_date', days(245, 'date'))])
    body += record('environment_point_fridge', 'pharmacy.environment.point', [
        f('name', 'Refrigeradora de insulinas'), f('warehouse_id', ref='stock.warehouse0'),
        f('point_type', 'cold'), f('temp_min', 2), f('temp_max', 8), f('humidity_max', 0),
        f('equipment', 'Termómetro de máximas y mínimas'), fe('calibration_date', days(-60, 'date')),
        fe('next_calibration_date', days(305, 'date'))])
    readings = [
        ('reading_room_1', 'environment_point_room', -2, 23.5, 55, ''),
        ('reading_room_2', 'environment_point_room', -1, 24.0, 58, ''),
        ('reading_fridge_1', 'environment_point_fridge', -2, 5.0, 0, ''),
        ('reading_fridge_2', 'environment_point_fridge', -1, 9.5, 0,
         'Se cerró bien la puerta y se comprobó a los 30 minutos: 6 °C.'),
    ]
    for key, point, day, temperature, humidity, action in readings:
        fields = [f('point_id', ref=point), fe('date', days(day)), f('temperature', temperature),
                  f('humidity', humidity)]
        if action:
            fields.append(f('corrective_action', action))
        body += record(key, 'pharmacy.environment.reading', fields)
    body.append('        <!-- Compra con bonificación (12 + 1) y su recepción por inspeccionar -->')
    body += record('supplier_pacifico', 'res.partner', [
        f('name', 'Distribuidora Farmacéutica del Pacífico S.A.C.'), f('is_company', eval='True'),
        f('street', 'Av. Argentina 2450'), f('city', 'Lima'), f('country_id', ref='base.pe')])
    body += record('purchase_losartan', 'purchase.order', [
        f('partner_id', ref='supplier_pacifico'),
        f('order_line', eval="[Command.create({'product_id': obj().env.ref('al_pharmacy_base.product_losartan')"
                             ".product_variant_id.id, 'product_qty': 1200, 'price_unit': 0.10, "
                             "'pharmacy_bonus_qty': 100})]")])
    body += ['        <function model="purchase.order" name="button_confirm" eval="[[ref(\'purchase_losartan\')]]"/>']
    body.append('        <!-- Lote en cuarentena por una recepción no conforme -->')
    body += record('lot_omeprazole_quarantine', 'stock.lot', [
        f('name', '060152609Q'), fe('product_id', variant('product_omeprazole')),
        fe('expiration_date', days(400)), f('company_id', ref='base.main_company')])
    body += record('lot_omeprazole_quarantine_quant', 'stock.quant', [
        fe('product_id', variant('product_omeprazole')), f('lot_id', ref='lot_omeprazole_quarantine'),
        f('inventory_quantity', 200), fe('location_id', stock_location())])
    body += ['        <function model="stock.quant" name="action_apply_inventory">',
             "            <function eval=\"[[('id', '=', ref('lot_omeprazole_quarantine_quant'))]]\" "
             'model="stock.quant" name="search"/>', '        </function>',
             '        <function model="stock.lot" name="_pharmacy_set_state" eval="[[ref(\'lot_omeprazole_quarantine\')], '
             "'quarantine', 'Recepción no conforme: cajas mojadas']\"/>"]
    body.append('        <!-- Alerta sanitaria por confirmar y acta de baja en borrador -->')
    body += record('alert_amoxicillin', 'pharmacy.alert', [
        f('name', 'ALERTA DIGEMID N.° 45-2026'), f('source', 'authority'),
        f('description', 'Retiro del mercado del lote 012872604 de Amoxicilina 500 mg cápsula por '
                         'resultado no conforme en disolución.'),
        f('line_ids', eval="[Command.create({'product_tmpl_id': ref('al_pharmacy_base.product_amoxicillin'), "
                           "'lot_names': '012872604', 'sanitary_registry': 'EN-05127'})]")])
    body += record('destruction_expired', 'pharmacy.destruction', [
        f('warehouse_id', ref='stock.warehouse0'), f('method', 'Entrega a empresa operadora de residuos'),
        f('witness', 'Carmen Flores Díaz'),
        f('line_ids', eval="[Command.create({'product_id': obj().env.ref('al_pharmacy_base.product_amoxicillin')"
                           ".product_variant_id.id, 'lot_id': ref('product_amoxicillin_lot_2'), "
                           "'location_id': obj().env.ref('stock.warehouse0').lot_stock_id.id, "
                           "'quantity': 20, 'reason': 'damaged'})]")])
    return document('Almacén de la botica de demostración.', body)


# ----------------------------------------------------------------------
# al_pharmacy_prescription: prescriptores, pacientes, recetas
# ----------------------------------------------------------------------
def prescriber_records(with_status=True):
    body = []
    for key, name, license_number, specialty, status in PRESCRIBERS:
        fields = [f('name', name), f('pharmacy_is_prescriber', eval='True'),
                  f('pharmacy_profession', 'physician'), f('pharmacy_prescriber_license', license_number),
                  f('pharmacy_specialty', specialty)]
        if with_status and status:
            fields += [f('pharmacy_prescriber_status', status), fe('pharmacy_prescriber_checked', days(-3))]
        body += record(key, 'res.partner', fields)
    return body


def demo_prescription():
    body = ['        <!-- Prescriptores: hábil, sin verificar e inhábil -->', *prescriber_records()]
    body.append('        <!-- Pacientes -->')
    body += record('patient_mendoza', 'res.partner', [
        f('name', 'Rosa Mendoza Vargas'), f('phone', '987 654 321'),
        f('street', 'Jr. Huallaga 345'), f('city', 'Lima'), f('country_id', ref='base.pe'),
        fe('pharmacy_birthdate', days(-365 * 54, 'date')),
        f('pharmacy_allergy_ids', eval="[Command.set([ref('al_pharmacy_base.ingredient_amoxicilina')])]"),
        f('pharmacy_chronic_conditions', 'Hipertensión arterial')])
    body += record('patient_castro', 'res.partner', [
        f('name', 'Pedro Castro Ñahui'), f('phone', '956 123 478'),
        f('street', 'Av. Brasil 1820'), f('city', 'Lima'), f('country_id', ref='base.pe'),
        fe('pharmacy_birthdate', days(-365 * 38, 'date')), f('pharmacy_chronic_conditions', 'Diabetes tipo 2')])
    body.append('        <!-- Recetas: por validar, vigente, dispensada en parte y vencida -->')
    prescriptions = [
        ('prescription_draft', '000101', 'prescriber_salazar', 'patient_castro', 0, 'draft',
         'Faringitis aguda', [('product_azithromycin', None, 3, '1 tableta al día', '3 días')]),
        ('prescription_valid', '000102', 'prescriber_torres', 'patient_mendoza', -1, 'valid',
         'Hipertensión arterial', [('product_losartan', None, 30, '1 tableta al día', '30 días')]),
        ('prescription_partial', '000103', 'prescriber_torres', 'patient_castro', -2, 'valid',
         'Diabetes tipo 2', [('product_metformin', None, 60, '1 tableta cada 12 horas', '30 días'),
                             (None, 'ingredient_ibuprofeno', 10, '1 tableta cada 8 horas', '3 días')]),
        ('prescription_expired', '000090', 'prescriber_torres', 'patient_mendoza', -45, 'valid',
         'Gastritis', [('product_omeprazole', None, 14, '1 cápsula en ayunas', '14 días')]),
    ]
    for key, number, prescriber, patient, day, state, diagnosis, lines in prescriptions:
        commands = []
        for index, (product, ingredient, quantity, posology, duration) in enumerate(lines, 1):
            values = [f"'sequence': {index}", f"'quantity': {quantity}", f"'posology': '{posology}'",
                      f"'duration': '{duration}'"]
            if product:
                values.append(f"'product_id': obj().env.ref('{ref(product)}').product_variant_id.id")
            else:
                values.append(f"'ingredient_id': ref('{ref(ingredient)}')")
            commands.append('Command.create({%s})' % ', '.join(values))
        body += record(key, 'pharmacy.prescription', [
            f('prescription_number', number), f('prescriber_id', ref=prescriber), f('patient_id', ref=patient),
            fe('date', days(day, 'date')), f('health_facility', 'Clínica San Gabriel'),
            f('diagnosis', diagnosis), f('warehouse_id', ref='stock.warehouse0'),
            f('manual_state', state), f('line_ids', eval='[%s]' % ', '.join(commands))])
    body += record('dispensation_partial', 'pharmacy.dispensation', [
        f('prescription_id', ref='prescription_partial'),
        f('prescription_line_id', eval="obj().env.ref('al_pharmacy_prescription.prescription_partial')"
                                       ".line_ids.sorted('sequence')[:1].id", model='pharmacy.prescription'),
        fe('product_id', variant('product_metformin')), f('quantity', 30), fe('date', days(-1)),
        f('pharmacist_id', ref='al_pharmacy_base.employee_director'), f('source', 'Mostrador')])
    body += ['        <function model="pharmacy.prescription" name="_cron_expire_prescriptions"/>']
    return document('Recetas de la botica de demostración.', body)


# ----------------------------------------------------------------------
# al_pharmacy_pos: productos en la caja
# ----------------------------------------------------------------------
def demo_pos():
    body = ['        <!-- Los medicamentos de la botica se venden en la caja -->']
    for pid, *_rest in PRODUCTS:
        body += record(ref(pid), 'product.template', [f('available_in_pos', eval='True')])
    return document('Caja de la botica de demostración.', body)


# ----------------------------------------------------------------------
# al_l10n_pe_pharmacy_edi: clientes para boleta y factura
# ----------------------------------------------------------------------
def demo_edi():
    body = ['        <!-- Clientes con DNI (boleta) y RUC (factura) -->']
    body += record('customer_dni', 'res.partner', [
        f('name', 'Lucía Fernández Ríos'), f('vat', '44556677'),
        f('l10n_latam_identification_type_id', ref='l10n_pe.it_DNI'), f('country_id', ref='base.pe'),
        f('street', 'Calle Los Pinos 120'), f('city', 'Lima')])
    body += record('customer_ruc', 'res.partner', [
        f('name', 'Distribuidora Médica Lima S.A.C.'), f('is_company', eval='True'),
        f('vat', '20512528458'), f('l10n_latam_identification_type_id', ref='l10n_pe.it_RUC'),
        f('country_id', ref='base.pe'), f('street', 'Av. Javier Prado Este 4200'), f('city', 'Lima')])
    return document('Clientes de la botica de demostración.', body)


# ----------------------------------------------------------------------
# al_l10n_pe_prescriber_cmp: verificación en el CMP
# ----------------------------------------------------------------------
def demo_cmp():
    body = ['        <!-- Prescriptores verificados en el portal del CMP -->']
    for key, _name, _license, _specialty, status in PRESCRIBERS:
        fields = [f('pharmacy_cmp_council', 'CR III Lima')]
        if status:
            fields.append(f('pharmacy_prescriber_checked_by_id', ref='base.user_admin'))
        body += record(f'al_pharmacy_prescription.{key}', 'res.partner', fields)
    return document('Verificación de colegiaturas de la botica de demostración.', body)


# ----------------------------------------------------------------------
# al_l10n_pe_pharmacy_controlled: listas, receta especial y retenida
# ----------------------------------------------------------------------
def demo_controlled():
    body = ['        <!-- Psicotrópicos de la lista IVA (receta retenida) -->']
    for pid, *_rest, extra in PRODUCTS:
        if extra.get('control'):
            body += record(ref(pid), 'product.template', [f('pharmacy_control_list', extra['control'])])
    body.append('        <!-- Estupefaciente de la lista IIA (receta especial) -->')
    body += record('ingredient_morphine', 'pharmacy.ingredient', [f('name', 'Morfina')])
    body += record('product_morphine', 'product.template', [
        f('name', 'Morfina 10 mg/mL solución inyectable ampolla 1 mL'), f('list_price', 9.5),
        f('standard_price', 5.2), f('type', 'consu'), f('is_storable', eval='True'), f('tracking', 'lot'),
        f('use_expiration_date', eval='True'), f('expiration_time', 730), f('pharmacy_ok', eval='True'),
        f('pharmacy_product_type', 'generic_dci'), f('pharmacy_sale_condition', 'controlled'),
        f('pharmacy_control_list', 'IIA'), f('pharmacy_sanitary_registry', 'EN-02211'),
        f('pharmacy_dosage_form_id', ref='al_pharmacy_base.dosage_form_injection'),
        f('pharmacy_route_id', ref='al_pharmacy_base.route_im'),
        f('pharmacy_ingredient_line_ids', eval="[Command.create({'ingredient_id': ref('ingredient_morphine'), "
                                               "'strength': 10, 'strength_unit': 'mg'})]")])
    body += record('product_morphine_lot', 'stock.lot', [
        f('name', 'MOR2611'), fe('product_id', variant('al_l10n_pe_pharmacy_controlled.product_morphine')),
        fe('expiration_date', days(600)), f('company_id', ref='base.main_company')])
    body += record('product_morphine_quant', 'stock.quant', [
        fe('product_id', variant('al_l10n_pe_pharmacy_controlled.product_morphine')),
        f('lot_id', ref='product_morphine_lot'), f('inventory_quantity', 20), fe('location_id', stock_location())])
    body += ['        <function model="stock.quant" name="action_apply_inventory">',
             "            <function eval=\"[[('id', '=', ref('product_morphine_quant'))]]\" "
             'model="stock.quant" name="search"/>', '        </function>']
    body.append('        <!-- Documento de identidad de los pacientes (lo exige la receta especial) -->')
    for patient, vat in (('patient_mendoza', '41235678'), ('patient_castro', '45879632')):
        body += record(f'al_pharmacy_prescription.{patient}', 'res.partner', [
            f('l10n_latam_identification_type_id', ref='l10n_pe.it_DNI'), f('vat', vat)])
    body.append('        <!-- Receta especial vigente (3 días) y receta retenida con su folio -->')
    body += record('prescription_special', 'pharmacy.prescription', [
        f('prescription_number', 'RE-000045'), f('prescription_type', 'special'), f('validity_days', 3),
        f('prescriber_id', ref='al_pharmacy_prescription.prescriber_torres'),
        f('patient_id', ref='al_pharmacy_prescription.patient_castro'), fe('date', days(0, 'date')),
        f('health_facility', 'Clínica San Gabriel'), f('diagnosis', 'Dolor posoperatorio'),
        f('warehouse_id', ref='stock.warehouse0'), f('manual_state', 'valid'),
        f('line_ids', eval="[Command.create({'product_id': obj().env.ref('al_l10n_pe_pharmacy_controlled."
                           "product_morphine').product_variant_id.id, 'quantity': 3, "
                           "'posology': '1 ampolla cada 8 horas', 'duration': '1 día'})]")])
    body += record('prescription_retained', 'pharmacy.prescription', [
        f('prescription_number', '000110'),
        f('prescriber_id', ref='al_pharmacy_prescription.prescriber_torres'),
        f('patient_id', ref='al_pharmacy_prescription.patient_mendoza'), fe('date', days(-1, 'date')),
        f('diagnosis', 'Trastorno de ansiedad'), f('warehouse_id', ref='stock.warehouse0'),
        f('manual_state', 'valid'), f('retained', eval='True'), f('retention_folio', 'RET-2026-0001'),
        f('line_ids', eval="[Command.create({'product_id': obj().env.ref('al_pharmacy_base.product_clonazepam')"
                           ".product_variant_id.id, 'quantity': 20, 'posology': '1 tableta en la noche', "
                           "'duration': '20 días'})]")])
    body += record('dispensation_retained', 'pharmacy.dispensation', [
        f('prescription_id', ref='prescription_retained'),
        f('prescription_line_id', eval="obj().env.ref('al_l10n_pe_pharmacy_controlled.prescription_retained')"
                                       ".line_ids[:1].id", model='pharmacy.prescription'),
        fe('product_id', variant('product_clonazepam')), f('quantity', 20),
        f('lot_id', ref='al_pharmacy_stock.product_clonazepam_lot_1'), fe('date', days(-1)),
        f('pharmacist_id', ref='al_pharmacy_base.employee_director'),
        f('purchaser_name', 'Rosa Mendoza Vargas'), f('purchaser_vat', '41235678'), f('source', 'Mostrador')])
    return document('Productos controlados de la botica de demostración.', body)


# ----------------------------------------------------------------------
# al_l10n_pe_pharmacy_digemid: códigos, IGV, genéricos, reacciones adversas
# ----------------------------------------------------------------------
def demo_digemid():
    body = ['        <!-- Códigos del Observatorio y régimen del IGV -->']
    for pid, *_rest, code, extra in [(p[0], p[11], p[12]) for p in PRODUCTS]:
        fields = [f('pharmacy_digemid_code', code)]
        if extra.get('igv'):
            fields.append(f('pharmacy_igv_regime', extra['igv']))
        body += record(ref(pid), 'product.template', fields)
    # Al guardar el código, cada producto deja su precio pendiente de informar.
    body.append('        <!-- Establecimiento y listado de genéricos esenciales -->')
    body += record('base.main_company', 'res.company', [
        f('pharmacy_establishment_category', 'drugstore'),
        f('pharmacy_authorization_number', 'RD 0456-2026-DIRIS-LC'),
        fe('pharmacy_authorization_date', days(-400, 'date'))])
    for index, (ingredient, strength, form) in enumerate(ESSENTIAL, 1):
        body += record(f'essential_{index:02d}', 'pharmacy.essential.medicine', [
            f('ingredient_id', ref=ref(ingredient)), f('strength', strength),
            f('dosage_form_id', ref=f'al_pharmacy_base.dosage_form_{form}'),
            f('list_reference', 'RM 220-2024/MINSA')])
    body.append('        <!-- Reacciones adversas: una por notificar y una notificada -->')
    body += record('adverse_event_draft', 'pharmacy.adverse.event', [
        f('patient_initials', 'P.C.Ñ.'), f('patient_age', 38), f('patient_sex', 'm'), f('patient_weight', 78),
        fe('product_id', variant('product_metformin')), f('lot_id', ref='al_pharmacy_stock.product_metformin_lot_1'),
        f('dose', '850 mg cada 12 horas'), f('route_id', ref='al_pharmacy_base.route_oral'),
        fe('therapy_start', days(-10, 'date')), fe('reaction_start', days(-2, 'date')),
        f('reaction', 'Náuseas y diarrea desde el octavo día de tratamiento.'),
        f('severity', 'non_serious'), f('outcome', 'recovering'), fe('date_detected', days(-1))])
    body += record('adverse_event_notified', 'pharmacy.adverse.event', [
        f('patient_initials', 'R.M.V.'), f('patient_age', 54), f('patient_sex', 'f'),
        fe('product_id', variant('product_losartan')), f('dose', '50 mg al día'),
        f('route_id', ref='al_pharmacy_base.route_oral'), fe('therapy_start', days(-60, 'date')),
        fe('reaction_start', days(-20, 'date')), f('reaction', 'Mareos al levantarse.'),
        f('severity', 'non_serious'), f('outcome', 'recovered'), fe('date_detected', days(-20)),
        f('state', 'notified'), fe('notified_date', days(-18)), f('notimed_reference', 'NOTI-2026-004512')])
    return document('Obligaciones con DIGEMID de la botica de demostración.', body)


# ----------------------------------------------------------------------
# al_industry_pharmacy: categorías del rubro y productos no farmacéuticos
# ----------------------------------------------------------------------
def demo_industry():
    category = {'otc': 'product_category_medicines_otc', 'rx': 'product_category_medicines_rx',
                'controlled': 'product_category_medicines_controlled'}
    body = ['        <!-- Los medicamentos de la suite en las categorías del rubro -->']
    for pid, *_rest, extra in PRODUCTS:
        body += record(ref(pid), 'product.template', [
            f('categ_id', ref=category[extra['categ']]),
            f('pos_categ_ids', eval="[Command.set([ref('pos_category_01')])]")])
    body += record('al_l10n_pe_pharmacy_controlled.product_morphine', 'product.template', [
        f('categ_id', ref='product_category_medicines_controlled')])
    body.append('        <!-- Productos no farmacéuticos de la botica -->')
    body += record('product_sunscreen', 'product.template', [
        f('name', 'Protector solar FPS 50 x 50 mL'), f('categ_id', ref='product_category_dermo'),
        f('list_price', 69.9), f('standard_price', 38.0), f('type', 'consu'), f('is_storable', eval='True'),
        f('available_in_pos', eval='True'), f('pos_categ_ids', eval="[Command.set([ref('pos_category_02')])]")])
    body += record('product_thermometer', 'product.template', [
        f('name', 'Termómetro digital'), f('categ_id', ref='product_category_medical_devices'),
        f('list_price', 25.0), f('standard_price', 12.0), f('type', 'consu'), f('is_storable', eval='True'),
        f('available_in_pos', eval='True'), f('pos_categ_ids', eval="[Command.set([ref('pos_category_06')])]")])
    return document('Botica de demostración del paquete de industria.', body)


FILES = {
    'OL-HEALTH/al_pharmacy_base/demo/pharmacy_demo.xml': demo_base,
    'OL-HEALTH/al_pharmacy_stock/demo/pharmacy_stock_demo.xml': demo_stock,
    'OL-HEALTH/al_pharmacy_prescription/demo/pharmacy_prescription_demo.xml': demo_prescription,
    'OL-HEALTH/al_pharmacy_pos/demo/pharmacy_pos_demo.xml': demo_pos,
    'OL-HEALTH/al_l10n_pe_pharmacy_edi/demo/pharmacy_edi_demo.xml': demo_edi,
    'OL-HEALTH/al_l10n_pe_prescriber_cmp/demo/prescriber_cmp_demo.xml': demo_cmp,
    'OL-HEALTH/al_l10n_pe_pharmacy_controlled/demo/controlled_demo.xml': demo_controlled,
    'OL-HEALTH/al_l10n_pe_pharmacy_digemid/demo/digemid_demo.xml': demo_digemid,
    'OL-INDUSTRIES/al_industry_pharmacy/demo/pharmacy_demo.xml': demo_industry,
}


def main(check=False):
    stale = []
    for path, build in FILES.items():
        target = ROOT / path
        content = build()
        if target.exists() and target.read_text(encoding='utf-8') == content:
            continue
        stale.append(path)
        if not check:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
    print('%s %s' % ('desfasados:' if check else 'escritos:', ', '.join(stale) or 'ninguno'))
    return 1 if check and stale else 0


if __name__ == '__main__':
    sys.exit(main('--check' in sys.argv))
