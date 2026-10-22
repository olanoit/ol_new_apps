"""Genera los datos de demostración de la suite de farmacia.

Cada módulo lleva los registros que necesita para probarse solo (con sus
dependencias): instalar uno con datos de demostración basta para recorrer
sus pantallas, sus reportes y su guion de prueba. El catálogo es el de una
botica peruana (unos 55 medicamentos y 14 productos de tocador, bebé,
nutrición y dispositivos) con marcas y laboratorios inventados, precios en
soles y fotos de estudio de sus envases (``generar_empaques.py``).

Uso (desde la raíz del repositorio)::

    ~/odoo/ce19/.venv/bin/python docs/farmacia/generar_empaques.py  # fotos de los envases
    python3 docs/farmacia/generar_demo.py             # escribe los demo/*.xml
    python3 docs/farmacia/generar_demo.py --check     # ¿están al día?

En una base sin demo (farmacia-dev) los mismos datos se cargan o actualizan
con ``docs/farmacia/cargar_demo.py`` (odoo shell).
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]

LABS = {
    'lab_andino': 'Laboratorios Andinos S.A.C.',
    'lab_rimac': 'Laboratorio Rímac S.A.C.',
    'lab_sol': 'Laboratorios Sol del Sur S.A.C.',
    'lab_huascaran': 'Laboratorios Huascarán S.A.C.',
    'lab_chavin': 'Biofarma Chavín S.A.C.',
}
INGREDIENTS = {
    'ingredient_paracetamol': 'Paracetamol', 'ingredient_ibuprofeno': 'Ibuprofeno',
    'ingredient_amoxicilina': 'Amoxicilina', 'ingredient_insulina_humana': 'Insulina humana',
    'ingredient_azitromicina': 'Azitromicina', 'ingredient_losartan': 'Losartán',
    'ingredient_metformina': 'Metformina', 'ingredient_clonazepam': 'Clonazepam',
    'ingredient_alprazolam': 'Alprazolam', 'ingredient_loratadina': 'Loratadina',
    'ingredient_omeprazol': 'Omeprazol',
    'ingredient_naproxeno': 'Naproxeno', 'ingredient_diclofenaco': 'Diclofenaco',
    'ingredient_acido_acetilsalicilico': 'Ácido acetilsalicílico', 'ingredient_cetirizina': 'Cetirizina',
    'ingredient_clorfenamina': 'Clorfenamina', 'ingredient_fenilefrina': 'Fenilefrina',
    'ingredient_ambroxol': 'Ambroxol', 'ingredient_dextrometorfano': 'Dextrometorfano',
    'ingredient_sales_rehidratacion': 'Sales de rehidratación oral', 'ingredient_simeticona': 'Simeticona',
    'ingredient_loperamida': 'Loperamida', 'ingredient_hidroxido_aluminio': 'Hidróxido de aluminio',
    'ingredient_hidroxido_magnesio': 'Hidróxido de magnesio', 'ingredient_clotrimazol': 'Clotrimazol',
    'ingredient_acido_ascorbico': 'Ácido ascórbico', 'ingredient_sulfato_ferroso': 'Sulfato ferroso',
    'ingredient_hipromelosa': 'Hipromelosa', 'ingredient_cloruro_sodio': 'Cloruro de sodio',
    'ingredient_mebendazol': 'Mebendazol', 'ingredient_albendazol': 'Albendazol',
    'ingredient_cefalexina': 'Cefalexina', 'ingredient_ciprofloxacino': 'Ciprofloxacino',
    'ingredient_acido_clavulanico': 'Ácido clavulánico', 'ingredient_enalapril': 'Enalapril',
    'ingredient_amlodipino': 'Amlodipino', 'ingredient_atorvastatina': 'Atorvastatina',
    'ingredient_levotiroxina': 'Levotiroxina', 'ingredient_glibenclamida': 'Glibenclamida',
    'ingredient_insulina_glargina': 'Insulina glargina', 'ingredient_salbutamol': 'Salbutamol',
    'ingredient_prednisona': 'Prednisona', 'ingredient_dexametasona': 'Dexametasona',
    'ingredient_sertralina': 'Sertralina', 'ingredient_diazepam': 'Diazepam',
    'ingredient_metronidazol': 'Metronidazol', 'ingredient_tamoxifeno': 'Tamoxifeno',
}


def P(pid, name, ptype, cond, ingredients, form, route, price, cost, presentations, registry, code,
      categ, lab=None, ind=None, **extra):
    """Medicamento de la demo (ver la tupla de PRODUCTS)."""
    extra.update(categ=categ)
    if lab:
        extra['lab'] = lab
    if ind:
        extra['ind'] = ind
    return (pid, name, ptype, cond, ingredients, form, route, price, cost, presentations, registry, code, extra)


BLISTER = 'Blíster'
# (xmlid, nombre, tipo, condición, [(ingrediente, concentración, unidad)], forma, vía,
#  precio por unidad, costo, [(presentación, unidades, precio)], registro sanitario,
#  código DIGEMID, extra). Marcas y laboratorios inventados.
PRODUCTS = [
    # --- Analgésicos, antiinflamatorios y antigripales (venta libre)
    P('product_paracetamol', 'Paracetamol 500 mg tableta', 'generic_dci', 'otc',
      [('ingredient_paracetamol', 500, 'mg')], 'tablet', 'oral', 0.20, 0.08,
      [(BLISTER, 10, 1.50), ('Caja', 100, 12.00)], 'EN-04512', '05463', 'otc',
      ind='Dolor leve a moderado y fiebre.'),
    P('product_dolofen', 'Dolofen 500 mg tableta', 'innovator', 'otc',
      [('ingredient_paracetamol', 500, 'mg')], 'tablet', 'oral', 0.60, 0.30,
      [(BLISTER, 10, 5.50), ('Caja', 100, 50.00)], 'E-21876', '05464', 'otc', 'lab_rimac',
      ind='Dolor leve a moderado y fiebre.'),
    P('product_paracetamol_syrup', 'Paracetamol 120 mg/5 mL jarabe frasco 60 mL', 'generic_dci', 'otc',
      [('ingredient_paracetamol', 120, 'mg_5ml')], 'syrup', 'oral', 4.50, 1.80, [], 'EN-04630', '05470',
      'otc', ind='Fiebre y dolor en niños, según peso.'),
    P('product_ibuprofen', 'Ibuprofeno 400 mg tableta', 'generic_dci', 'otc',
      [('ingredient_ibuprofeno', 400, 'mg')], 'tablet', 'oral', 0.25, 0.10,
      [(BLISTER, 10, 2.00), ('Caja', 100, 15.00)], 'EN-03891', '04120', 'otc',
      ind='Dolor, inflamación y fiebre.'),
    P('product_ibuflam', 'Ibuflam 400 mg tableta', 'generic_brand', 'otc',
      [('ingredient_ibuprofeno', 400, 'mg')], 'tablet', 'oral', 0.45, 0.20,
      [(BLISTER, 10, 4.00)], 'EG-07722', '04121', 'otc', 'lab_sol', ind='Dolor, inflamación y fiebre.'),
    P('product_ibuprofen_suspension', 'Ibuprofeno 100 mg/5 mL suspensión frasco 60 mL', 'generic_dci', 'otc',
      [('ingredient_ibuprofeno', 100, 'mg_5ml')], 'suspension', 'oral', 6.50, 2.60, [], 'EN-04015', '04125',
      'otc', ind='Fiebre y dolor en niños mayores de 6 meses.'),
    P('product_naproxen', 'Naproxeno sódico 550 mg tableta', 'generic_dci', 'otc',
      [('ingredient_naproxeno', 550, 'mg')], 'coated_tablet', 'oral', 0.50, 0.18,
      [(BLISTER, 10, 4.50), ('Caja', 100, 40.00)], 'EN-05210', '04310', 'otc', ind='Dolor e inflamación.'),
    P('product_diclofenac_gel', 'Diclofenaco 1 % gel tubo 50 g', 'generic_dci', 'otc',
      [('ingredient_diclofenaco', 1, 'percent')], 'gel', 'topical', 9.90, 3.90, [], 'EN-04772', '04420',
      'otc', ind='Dolor muscular y articular localizado.'),
    P('product_aspirin', 'Ácido acetilsalicílico 100 mg tableta', 'generic_dci', 'otc',
      [('ingredient_acido_acetilsalicilico', 100, 'mg')], 'tablet', 'oral', 0.15, 0.05,
      [(BLISTER, 10, 1.20), ('Caja', 100, 10.00)], 'EN-02987', '00125', 'otc',
      ind='Prevención cardiovascular, por indicación médica.'),
    P('product_antiflu', 'Antigripal Andino tableta', 'generic_brand', 'otc',
      [('ingredient_paracetamol', 500, 'mg'), ('ingredient_fenilefrina', 10, 'mg'),
       ('ingredient_clorfenamina', 4, 'mg')], 'tablet', 'oral', 0.70, 0.28,
      [(BLISTER, 4, 2.50), ('Caja', 100, 60.00)], 'EG-08120', '05480', 'otc', 'lab_andino',
      ind='Síntomas del resfrío común y la gripe.'),
    # --- Alergias y vías respiratorias
    P('product_loratadine', 'Loratadina 10 mg tableta', 'generic_dci', 'otc',
      [('ingredient_loratadina', 10, 'mg')], 'tablet', 'oral', 0.30, 0.10,
      [(BLISTER, 10, 2.50)], 'EN-06102', '06210', 'otc', ind='Rinitis alérgica y urticaria.'),
    P('product_cetirizine', 'Cetirizina 10 mg tableta', 'generic_dci', 'otc',
      [('ingredient_cetirizina', 10, 'mg')], 'coated_tablet', 'oral', 0.35, 0.12,
      [(BLISTER, 10, 3.00)], 'EN-06155', '06230', 'otc', ind='Rinitis alérgica y urticaria.'),
    P('product_chlorphenamine', 'Clorfenamina 4 mg tableta', 'generic_dci', 'otc',
      [('ingredient_clorfenamina', 4, 'mg')], 'tablet', 'oral', 0.10, 0.03,
      [(BLISTER, 10, 0.80)], 'EN-01988', '06190', 'otc', ind='Alergias y picaduras.'),
    P('product_ambroxol_syrup', 'Ambroxol 30 mg/5 mL jarabe frasco 120 mL', 'generic_dci', 'otc',
      [('ingredient_ambroxol', 30, 'mg_5ml')], 'syrup', 'oral', 7.90, 3.10, [], 'EN-03344', '07010',
      'otc', ind='Tos con flema.'),
    P('product_dextromethorphan_syrup', 'Dextrometorfano 15 mg/5 mL jarabe frasco 120 mL', 'generic_dci', 'otc',
      [('ingredient_dextrometorfano', 15, 'mg_5ml')], 'syrup', 'oral', 8.50, 3.40, [], 'EN-03410', '07025',
      'otc', ind='Tos seca.'),
    P('product_saline_nasal', 'Cloruro de sodio 0,9 % gotas nasales frasco 30 mL', 'generic_dci', 'otc',
      [('ingredient_cloruro_sodio', 0.9, 'percent')], 'drops', 'nasal', 5.50, 1.90, [], 'EN-02190', '07110',
      'otc', ind='Limpieza y descongestión nasal.'),
    # --- Aparato digestivo y antiparasitarios
    P('product_omeprazole', 'Omeprazol 20 mg cápsula', 'generic_dci', 'otc',
      [('ingredient_omeprazol', 20, 'mg')], 'capsule', 'oral', 0.30, 0.12,
      [(BLISTER, 10, 2.50), ('Caja', 100, 22.00)], 'EN-05988', '06015', 'otc', ind='Acidez y gastritis.'),
    P('product_antacid', 'Hidróxido de aluminio + magnesio suspensión frasco 150 mL', 'generic_dci', 'otc',
      [('ingredient_hidroxido_aluminio', 200, 'mg_5ml'), ('ingredient_hidroxido_magnesio', 200, 'mg_5ml')],
      'suspension', 'oral', 9.50, 3.60, [], 'EN-02455', '06040', 'otc', ind='Acidez estomacal.'),
    P('product_simethicone', 'Simeticona 80 mg tableta masticable', 'generic_dci', 'otc',
      [('ingredient_simeticona', 80, 'mg')], 'tablet', 'oral', 0.40, 0.14,
      [(BLISTER, 10, 3.50)], 'EN-03780', '06070', 'otc', ind='Gases y distensión abdominal.'),
    P('product_loperamide', 'Loperamida 2 mg tableta', 'generic_dci', 'otc',
      [('ingredient_loperamida', 2, 'mg')], 'tablet', 'oral', 0.30, 0.10,
      [(BLISTER, 10, 2.50)], 'EN-03812', '06090', 'otc', ind='Diarrea aguda en adultos.'),
    P('product_ors', 'Sales de rehidratación oral sobre 27,9 g', 'generic_dci', 'otc',
      [('ingredient_sales_rehidratacion', 27.9, 'g')], 'powder', 'oral', 1.50, 0.55, [('Caja', 20, 26.00)],
      'EN-01540', '06120', 'otc', ind='Deshidratación por diarrea.'),
    P('product_mebendazole', 'Mebendazol 100 mg/5 mL suspensión frasco 30 mL', 'generic_dci', 'otc',
      [('ingredient_mebendazol', 100, 'mg_5ml')], 'suspension', 'oral', 5.00, 1.80, [], 'EN-02670', '08010',
      'otc', ind='Parásitos intestinales.'),
    P('product_albendazole', 'Albendazol 400 mg tableta', 'generic_dci', 'otc',
      [('ingredient_albendazol', 400, 'mg')], 'tablet', 'oral', 1.50, 0.50, [(BLISTER, 2, 2.80)],
      'EN-02710', '08020', 'otc', ind='Parásitos intestinales.'),
    # --- Piel, ojos y vitaminas
    P('product_clotrimazole_cream', 'Clotrimazol 1 % crema tubo 20 g', 'generic_dci', 'otc',
      [('ingredient_clotrimazol', 1, 'percent')], 'cream', 'topical', 4.90, 1.70, [], 'EN-03050', '09010',
      'otc', ind='Infecciones de la piel por hongos.'),
    P('product_artificial_tears', 'Hipromelosa 0,3 % lágrimas artificiales frasco 15 mL', 'generic_dci', 'otc',
      [('ingredient_hipromelosa', 0.3, 'percent')], 'drops', 'ophthalmic', 12.90, 5.10, [], 'EN-04880',
      '09110', 'otc', ind='Sequedad e irritación ocular.'),
    P('product_vitamin_c', 'Vitamina C 1 g tableta efervescente', 'generic_dci', 'otc',
      [('ingredient_acido_ascorbico', 1, 'g')], 'tablet', 'oral', 1.20, 0.45, [('Tubo', 10, 11.00)],
      'EN-02330', '10010', 'otc', ind='Suplemento de vitamina C.'),
    P('product_ferrous_sulfate', 'Sulfato ferroso 300 mg tableta', 'generic_dci', 'otc',
      [('ingredient_sulfato_ferroso', 300, 'mg')], 'coated_tablet', 'oral', 0.20, 0.06,
      [(BLISTER, 10, 1.50), ('Caja', 100, 12.00)], 'EN-02390', '10030', 'otc', ind='Anemia por falta de hierro.'),
    # --- Antibióticos (con receta)
    P('product_amoxicillin', 'Amoxicilina 500 mg cápsula', 'generic_dci', 'prescription',
      [('ingredient_amoxicilina', 500, 'mg')], 'capsule', 'oral', 0.50, 0.22,
      [(BLISTER, 10, 4.50), ('Caja', 100, 40.00)], 'EN-05127', '01287', 'rx', bioeq=True, ind='Infecciones bacterianas.'),
    P('product_amoxival', 'Amoxival 500 mg cápsula', 'innovator', 'prescription',
      [('ingredient_amoxicilina', 500, 'mg')], 'capsule', 'oral', 1.40, 0.70,
      [(BLISTER, 10, 13.00)], 'E-18350', '01288', 'rx', 'lab_andino', ind='Infecciones bacterianas.'),
    P('product_amoxicillin_suspension', 'Amoxicilina 250 mg/5 mL polvo para suspensión frasco 60 mL',
      'generic_dci', 'prescription', [('ingredient_amoxicilina', 250, 'mg_5ml')], 'powder', 'oral', 7.50, 2.90,
      [], 'EN-05140', '01290', 'rx', ind='Infecciones bacterianas en niños.'),
    P('product_amoxicillin_clavulanate', 'Amoxicilina + ácido clavulánico 875/125 mg tableta', 'generic_dci',
      'prescription', [('ingredient_amoxicilina', 875, 'mg'), ('ingredient_acido_clavulanico', 125, 'mg')],
      'coated_tablet', 'oral', 2.20, 0.95, [('Caja', 14, 28.00)], 'EN-05188', '01295', 'rx',
      ind='Infecciones bacterianas resistentes.'),
    P('product_azithromycin', 'Azitromicina 500 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_azitromicina', 500, 'mg')], 'coated_tablet', 'oral', 3.00, 1.20,
      [('Caja', 3, 8.00)], 'EN-04410', '02954', 'rx', ind='Infecciones respiratorias.'),
    P('product_cephalexin', 'Cefalexina 500 mg cápsula', 'generic_dci', 'prescription',
      [('ingredient_cefalexina', 500, 'mg')], 'capsule', 'oral', 0.70, 0.28, [(BLISTER, 10, 6.50)],
      'EN-03960', '01410', 'rx', ind='Infecciones de piel y vías urinarias.'),
    P('product_ciprofloxacin', 'Ciprofloxacino 500 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_ciprofloxacino', 500, 'mg')], 'coated_tablet', 'oral', 0.60, 0.22, [(BLISTER, 10, 5.50)],
      'EN-04120', '01520', 'rx', ind='Infecciones urinarias.'),
    P('product_metronidazole', 'Metronidazol 500 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_metronidazol', 500, 'mg')], 'tablet', 'oral', 0.35, 0.12, [(BLISTER, 10, 3.00)],
      'EN-02810', '01610', 'rx', ind='Infecciones por parásitos y bacterias anaerobias.'),
    # --- Crónicos: presión, colesterol, diabetes, tiroides
    P('product_losartan', 'Losartán 50 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_losartan', 50, 'mg')], 'coated_tablet', 'oral', 0.30, 0.10,
      [(BLISTER, 10, 2.50), ('Caja', 100, 20.00)], 'EN-05341', '03322', 'rx', bioeq=True, ind='Hipertensión arterial.'),
    P('product_tensiloz', 'Tensiloz 50 mg tableta', 'generic_brand', 'prescription',
      [('ingredient_losartan', 50, 'mg')], 'coated_tablet', 'oral', 0.90, 0.40, [(BLISTER, 10, 8.50)],
      'EG-09012', '03323', 'rx', 'lab_huascaran', bioeq=True, ind='Hipertensión arterial.'),
    P('product_enalapril', 'Enalapril 10 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_enalapril', 10, 'mg')], 'tablet', 'oral', 0.15, 0.05,
      [(BLISTER, 10, 1.20), ('Caja', 100, 10.00)], 'EN-03250', '03310', 'rx', ind='Hipertensión arterial.'),
    P('product_amlodipine', 'Amlodipino 5 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_amlodipino', 5, 'mg')], 'tablet', 'oral', 0.20, 0.07,
      [(BLISTER, 10, 1.80), ('Caja', 100, 15.00)], 'EN-04510', '03340', 'rx', ind='Hipertensión arterial.'),
    P('product_atorvastatin', 'Atorvastatina 20 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_atorvastatina', 20, 'mg')], 'coated_tablet', 'oral', 0.45, 0.16,
      [(BLISTER, 10, 4.00), ('Caja', 30, 11.00)], 'EN-05010', '03410', 'rx', bioeq=True, ind='Colesterol alto.'),
    P('product_colestrina', 'Colestrina 20 mg tableta', 'innovator', 'prescription',
      [('ingredient_atorvastatina', 20, 'mg')], 'coated_tablet', 'oral', 2.80, 1.30, [('Caja', 30, 79.00)],
      'E-23015', '03411', 'rx', 'lab_chavin', ind='Colesterol alto.'),
    P('product_metformin', 'Metformina 850 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_metformina', 850, 'mg')], 'tablet', 'oral', 0.25, 0.09,
      [(BLISTER, 10, 2.00), ('Caja', 100, 18.00)], 'EN-04987', '03510', 'rx', igv='diabetes',
      ind='Diabetes tipo 2.'),
    P('product_glibenclamide', 'Glibenclamida 5 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_glibenclamida', 5, 'mg')], 'tablet', 'oral', 0.15, 0.05, [(BLISTER, 10, 1.20)],
      'EN-03020', '03520', 'rx', igv='diabetes', ind='Diabetes tipo 2.'),
    P('product_insulin', 'Insulina humana NPH 100 UI/mL frasco 10 mL', 'generic_dci', 'prescription',
      [('ingredient_insulina_humana', 100, 'ui')], 'injection', 'sc', 58.00, 41.00,
      [], 'BE-01046', '03601', 'rx', igv='diabetes', cold=True, ind='Diabetes que requiere insulina.'),
    P('product_insulin_glargine', 'Insulina glargina 100 UI/mL lapicero 3 mL', 'innovator', 'prescription',
      [('ingredient_insulina_glargina', 100, 'ui')], 'injection', 'sc', 69.00, 48.00, [('Caja', 5, 330.00)],
      'BE-01210', '03610', 'rx', 'lab_rimac', igv='diabetes', cold=True, ind='Diabetes tipo 1 y 2.'),
    P('product_levothyroxine', 'Levotiroxina 100 mcg tableta', 'generic_dci', 'prescription',
      [('ingredient_levotiroxina', 100, 'mcg')], 'tablet', 'oral', 0.30, 0.11, [('Caja', 100, 25.00)],
      'EN-04260', '03710', 'rx', ind='Hipotiroidismo.'),
    # --- Otros con receta
    P('product_salbutamol', 'Salbutamol 100 mcg/dosis inhalador 200 dosis', 'generic_dci', 'prescription',
      [('ingredient_salbutamol', 100, 'mcg')], 'inhaler', 'inhalation', 14.50, 6.20, [], 'EN-03590',
      '07210', 'rx', ind='Asma y broncoespasmo.'),
    P('product_prednisone', 'Prednisona 20 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_prednisona', 20, 'mg')], 'tablet', 'oral', 0.40, 0.14, [(BLISTER, 10, 3.50)],
      'EN-02940', '07310', 'rx', ind='Procesos inflamatorios y alérgicos.'),
    P('product_dexamethasone', 'Dexametasona 4 mg/mL solución inyectable ampolla 2 mL', 'generic_dci',
      'prescription', [('ingredient_dexametasona', 4, 'mg_ml')], 'injection', 'im', 3.50, 1.20,
      [('Caja', 25, 75.00)], 'EN-03120', '07320', 'rx', ind='Inflamación y alergias graves.'),
    P('product_sertraline', 'Sertralina 50 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_sertralina', 50, 'mg')], 'coated_tablet', 'oral', 0.80, 0.30, [(BLISTER, 10, 7.50)],
      'EN-05420', '02310', 'rx', ind='Depresión y ansiedad.'),
    P('product_tamoxifen', 'Tamoxifeno 20 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_tamoxifeno', 20, 'mg')], 'tablet', 'oral', 1.10, 0.62, [('Caja', 30, 30.00)],
      'EN-04710', '04810', 'rx', igv='oncology_hiv', ind='Tratamiento del cáncer de mama.'),
    # --- Controlados (receta retenida)
    P('product_clonazepam', 'Clonazepam 2 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_clonazepam', 2, 'mg')], 'tablet', 'oral', 0.80, 0.30,
      [(BLISTER, 10, 7.50)], 'EN-03117', '02210', 'controlled', control='IVA', ind='Trastornos de ansiedad.'),
    P('product_alprazolam', 'Alprazolam 0,5 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_alprazolam', 0.5, 'mg')], 'tablet', 'oral', 0.60, 0.25,
      [(BLISTER, 10, 5.50)], 'EN-03205', '02215', 'controlled', control='IVA', ind='Trastornos de ansiedad.'),
    P('product_diazepam', 'Diazepam 10 mg tableta', 'generic_dci', 'prescription',
      [('ingredient_diazepam', 10, 'mg')], 'tablet', 'oral', 0.40, 0.14, [(BLISTER, 10, 3.50)],
      'EN-02105', '02220', 'controlled', control='IVA', ind='Ansiedad y espasmos musculares.'),
]
TRACKED = [p[0] for p in PRODUCTS]
ESSENTIAL = [('ingredient_paracetamol', '500 mg', 'tablet'), ('ingredient_ibuprofeno', '400 mg', 'tablet'),
             ('ingredient_amoxicilina', '500 mg', 'capsule'), ('ingredient_losartan', '50 mg', 'coated_tablet'),
             ('ingredient_metformina', '850 mg', 'tablet'), ('ingredient_omeprazol', '20 mg', 'capsule'),
             ('ingredient_enalapril', '10 mg', 'tablet'), ('ingredient_atorvastatina', '20 mg', 'coated_tablet'),
             ('ingredient_salbutamol', '100 mcg', 'inhaler'), ('ingredient_sales_rehidratacion', '27,9 g', 'powder'),
             ('ingredient_sulfato_ferroso', '300 mg', 'coated_tablet'), ('ingredient_cefalexina', '500 mg', 'capsule')]
# Productos que no son medicamentos (al_industry_pharmacy):
# (xmlid, nombre, categoría, categoría del TPV, precio, costo)
NON_PHARMA = [
    ('product_sunscreen', 'Protector solar FPS 50 x 50 mL', 'dermo', '02', 69.9, 38.0),
    ('product_moisturizer', 'Crema hidratante corporal x 400 mL', 'dermo', '02', 32.9, 16.0),
    ('product_toothpaste', 'Pasta dental con flúor x 90 g', 'personal_care', '03', 6.5, 3.2),
    ('product_hand_gel', 'Alcohol en gel antibacterial x 500 mL', 'personal_care', '03', 12.9, 5.8),
    ('product_alcohol', 'Alcohol medicinal 70° x 250 mL', 'personal_care', '03', 5.9, 2.4),
    ('product_diapers', 'Pañales para bebé talla M x 30', 'baby', '04', 39.9, 26.0),
    ('product_baby_wipes', 'Toallitas húmedas para bebé x 80', 'baby', '04', 9.9, 4.9),
    ('product_multivitamin', 'Multivitamínico adultos x 30 tabletas', 'nutrition', '05', 34.9, 17.0),
    ('product_nutritional_shake', 'Suplemento nutricional en polvo sabor vainilla x 400 g', 'nutrition', '05',
     59.9, 36.0),
    ('product_thermometer', 'Termómetro digital', 'medical_devices', '06', 25.0, 12.0),
    ('product_bp_monitor', 'Tensiómetro digital de brazo', 'medical_devices', '06', 149.0, 88.0),
    ('product_glucose_strips', 'Tiras reactivas para glucómetro x 50', 'medical_devices', '06', 79.0, 48.0),
    ('product_face_masks', 'Mascarillas quirúrgicas descartables x 50', 'medical_devices', '06', 15.0, 6.0),
    ('product_gauze', 'Gasa estéril 10 x 10 cm x 10 unidades', 'medical_devices', '06', 4.5, 1.8),
]
PRESCRIBERS = [
    ('prescriber_torres', 'Dra. Ana Torres Quispe', '067890', 'Medicina interna', 'enabled'),
    ('prescriber_salazar', 'Dr. Jorge Salazar Pérez', '045678', 'Pediatría', False),
    ('prescriber_rojas', 'Dr. Martín Rojas León', '031245', 'Psiquiatría', 'disabled'),
    ('prescriber_vargas', 'Dr. Raúl Vargas Chávez', '052310', 'Cardiología', 'enabled'),
    ('prescriber_huaman', 'Dra. Elena Huamán Ccori', '061870', 'Endocrinología', 'enabled'),
    ('prescriber_paz', 'Dra. Sofía Paz Medina', '073415', 'Medicina general', 'enabled'),
    ('prescriber_chang', 'Dr. Víctor Chang Lozano', '058902', 'Neumología', 'enabled'),
]
# Pacientes: (xmlid, nombre, teléfono, dirección, edad, alergias, condiciones crónicas)
PATIENTS = [
    ('patient_mendoza', 'Rosa Mendoza Vargas', '987 654 321', 'Jr. Huallaga 345', 54,
     ['ingredient_amoxicilina'], 'Hipertensión arterial'),
    ('patient_castro', 'Pedro Castro Ñahui', '956 123 478', 'Av. Brasil 1820', 38, [], 'Diabetes tipo 2'),
    ('patient_quispe', 'Julia Quispe Mamani', '945 778 120', 'Av. Arequipa 2870', 67, [],
     'Hipertensión arterial, colesterol alto'),
    ('patient_ramos', 'Carlos Ramos Gutiérrez', '991 230 556', 'Calle Las Begonias 415', 45,
     ['ingredient_acido_acetilsalicilico'], 'Asma'),
    ('patient_salinas', 'Mariela Salinas Cruz', '938 410 772', 'Jr. Junín 1120', 31, [], 'Hipotiroidismo'),
    ('patient_benites', 'Óscar Benites Laura', '962 905 314', 'Av. Tacna 650', 72, [],
     'Diabetes tipo 2, hipertensión arterial'),
    ('patient_ccahuana', 'Valeria Ccahuana Ríos', '974 682 019', 'Av. La Marina 2310', 6, [], ''),
    ('patient_lopez', 'Andrea López Tello', '983 117 640', 'Calle Schell 280', 49, ['ingredient_ibuprofeno'],
     'Cáncer de mama en tratamiento'),
]
# Recetas: (xmlid, número, prescriptor, paciente, día, estado, diagnóstico,
#           [(producto, ingrediente, cantidad, posología, duración)])
PRESCRIPTIONS = [
    ('prescription_draft', '000101', 'prescriber_salazar', 'patient_castro', 0, 'draft',
     'Faringitis aguda', [('product_azithromycin', None, 3, '1 tableta al día', '3 días')]),
    ('prescription_valid', '000102', 'prescriber_torres', 'patient_mendoza', -1, 'valid',
     'Hipertensión arterial', [('product_losartan', None, 30, '1 tableta al día', '30 días')]),
    ('prescription_partial', '000103', 'prescriber_torres', 'patient_castro', -2, 'valid',
     'Diabetes tipo 2', [('product_metformin', None, 60, '1 tableta cada 12 horas', '30 días'),
                         (None, 'ingredient_ibuprofeno', 10, '1 tableta cada 8 horas', '3 días')]),
    ('prescription_expired', '000090', 'prescriber_torres', 'patient_mendoza', -45, 'valid',
     'Gastritis', [('product_omeprazole', None, 14, '1 cápsula en ayunas', '14 días')]),
    ('prescription_quispe', '000104', 'prescriber_vargas', 'patient_quispe', -3, 'valid',
     'Hipertensión arterial y dislipidemia',
     [('product_enalapril', None, 60, '1 tableta cada 12 horas', '30 días'),
      ('product_atorvastatin', None, 30, '1 tableta en la noche', '30 días'),
      ('product_aspirin', None, 30, '1 tableta después del almuerzo', '30 días')]),
    ('prescription_ramos', '000105', 'prescriber_chang', 'patient_ramos', -1, 'valid', 'Asma bronquial',
     [('product_salbutamol', None, 1, '2 inhalaciones cada 6 horas si hay falta de aire', '30 días'),
      ('product_prednisone', None, 10, '1 tableta al día en el desayuno', '10 días')]),
    ('prescription_salinas', '000106', 'prescriber_huaman', 'patient_salinas', -5, 'valid', 'Hipotiroidismo',
     [('product_levothyroxine', None, 30, '1 tableta en ayunas', '30 días')]),
    ('prescription_benites', '000107', 'prescriber_huaman', 'patient_benites', -2, 'valid',
     'Diabetes tipo 2 insulinorrequiriente',
     [('product_insulin_glargine', None, 2, '20 UI en la noche', '30 días'),
      ('product_metformin', None, 60, '1 tableta cada 12 horas', '30 días'),
      ('product_amlodipine', None, 30, '1 tableta al día', '30 días')]),
    ('prescription_ccahuana', '000108', 'prescriber_salazar', 'patient_ccahuana', 0, 'valid',
     'Otitis media aguda (20 kg)',
     [('product_amoxicillin_suspension', None, 2, '8 mL cada 8 horas', '7 días'),
      ('product_paracetamol_syrup', None, 1, '10 mL cada 6 horas si hay fiebre', '3 días')]),
    ('prescription_lopez', '000109', 'prescriber_paz', 'patient_lopez', -4, 'valid',
     'Cáncer de mama hormonodependiente', [('product_tamoxifen', None, 30, '1 tableta al día', '30 días')]),
    ('prescription_cystitis', '000111', 'prescriber_paz', 'patient_salinas', -1, 'valid', 'Infección urinaria',
     [('product_ciprofloxacin', None, 10, '1 tableta cada 12 horas', '5 días')]),
    ('prescription_cancelled', '000112', 'prescriber_paz', 'patient_quispe', -6, 'cancelled',
     'Faringitis (anulada: error en la dosis)',
     [('product_amoxicillin_clavulanate', None, 14, '1 tableta cada 12 horas', '7 días')]),
]
# Dispensaciones: (xmlid, receta, línea (orden), producto, cantidad, día)
DISPENSATIONS = [
    ('dispensation_partial', 'prescription_partial', 0, 'product_metformin', 30, -1),
    ('dispensation_quispe_enalapril', 'prescription_quispe', 0, 'product_enalapril', 60, -3),
    ('dispensation_quispe_atorvastatin', 'prescription_quispe', 1, 'product_atorvastatin', 30, -3),
    ('dispensation_quispe_aspirin', 'prescription_quispe', 2, 'product_aspirin', 30, -3),
    ('dispensation_salinas', 'prescription_salinas', 0, 'product_levothyroxine', 30, -5),
    ('dispensation_benites_metformin', 'prescription_benites', 1, 'product_metformin', 60, -2),
]
# Tratamientos crónicos: (xmlid, paciente, producto, unidades por día, posología, inicio, nota)
TREATMENTS = [
    ('treatment_mendoza_losartan', 'patient_mendoza', 'product_losartan', 1, '1 tableta cada 24 horas', -120,
     'Hipertensión arterial. Prefiere que la llamen por la tarde.'),
    ('treatment_castro_metformin', 'patient_castro', 'product_metformin', 2,
     '1 tableta cada 12 horas con las comidas', -90, ''),
    ('treatment_quispe_enalapril', 'patient_quispe', 'product_enalapril', 2, '1 tableta cada 12 horas', -200,
     'Vive sola: avisar también a su hija.'),
    ('treatment_quispe_atorvastatin', 'patient_quispe', 'product_atorvastatin', 1, '1 tableta en la noche',
     -200, ''),
    ('treatment_salinas_levothyroxine', 'patient_salinas', 'product_levothyroxine', 1, '1 tableta en ayunas',
     -60, ''),
    ('treatment_benites_metformin', 'patient_benites', 'product_metformin', 2, '1 tableta cada 12 horas', -365,
     'Control de glucosa cada mes.'),
    ('treatment_ramos_salbutamol', 'patient_ramos', 'product_salbutamol', 0.2,
     '2 inhalaciones cada 6 horas si hay falta de aire', -30, 'Un inhalador le dura unos 5 días de crisis.'),
]

PRODUCTS_BY_ID = {p[0]: p for p in PRODUCTS}
# Segundo lote por vencer: días que le quedan y cantidad.
NEAR_EXPIRY = {'product_amoxicillin': (45, 120), 'product_naproxen': (75, 60), 'product_vitamin_c': (25, 30),
               'product_loratadine': (60, 40), 'product_ambroxol_syrup': (80, 12)}
FACILITIES = ['Clínica San Gabriel', 'Hospital Nacional Dos de Mayo', 'Centro Médico Miraflores',
              'Policlínico Santa Rosa']
DNIS = ['41235678', '45879632', '08765412', '42319876', '47652013', '06543219', '78123456', '40987123']
# Faltantes: (xmlid, producto o descripción, cantidad, motivo, nota)
SHORTAGES = [
    ('shortage_losartan', 'product_losartan', 30, 'no_stock', 'Cliente crónico: volverá el lunes.'),
    ('shortage_not_carried', 'Colirio antialérgico 10 mL', 2, 'not_carried', ''),
    ('shortage_insulin_glargine', 'product_insulin_glargine', 2, 'no_stock', 'Paciente con receta del endocrinólogo.'),
    ('shortage_probiotic', 'Probiótico en sobres x 10', 1, 'not_carried', 'Lo piden varias madres.'),
]
# Aseguradoras: (xmlid, nombre, dirección, correo, convenio, plan, % cubierto, copago, tope por venta,
#               tope mensual)
INSURERS = [
    ('partner_salud_andina', 'Salud Andina EPS S.A.', 'Av. Javier Prado Oeste 1450',
     'convenios@saludandina.example.com', 'agreement_salud_andina', 'Salud Andina EPS · Plan regular',
     80, 5, 300, 1000),
    ('partner_vida_plena', 'Vida Plena EPS S.A.', 'Av. Camino Real 390', 'farmacias@vidaplena.example.com',
     'agreement_vida_plena', 'Vida Plena EPS · Plan crónicos', 90, 0, 500, 1500),
]
AFFILIATES = [
    ('partner_affiliate_maria', 'María Torres Quispe', '987 123 456'),
    ('partner_affiliate_jose', 'José Ugarte Paredes', '981 450 237'),
    ('partner_affiliate_luz', 'Luz Ccopa Ramírez', '952 813 640'),
]
AFFILIATIONS = [
    ('affiliate_maria', 'agreement_salud_andina', 'partner_affiliate_maria', 'SA-0012345'),
    ('affiliate_jose', 'agreement_salud_andina', 'partner_affiliate_jose', 'SA-0012388'),
    ('affiliate_luz', 'agreement_vida_plena', 'partner_affiliate_luz', 'VP-2026-00871'),
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


def image(module, xmlid):
    """Foto del envase (docs/farmacia/generar_empaques.py), si ya se generó."""
    path = f'static/img/demo/{xmlid}.jpg'
    folder = 'OL-INDUSTRIES' if module.startswith('al_industry') else 'OL-HEALTH'
    if not (ROOT / folder / module / path).exists():
        return []
    return [f('image_1920', type='base64', file=f'{module}/{path}')]


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
        if extra.get('ind'):
            fields.append(f('pharmacy_indications', extra['ind']))
        if extra.get('bioeq'):
            fields.append(f('pharmacy_bioequivalent', eval='True'))
        fields += image(BASE, pid)
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
    body.append('        <!-- Lotes y existencias: uno por medicamento y, en algunos, un segundo lote\n'
                '             por vencer (aviso «Por vencer» y precio rebajado) -->')
    quants = []
    for pid, _name, *_rest, code, extra in PRODUCTS:
        if extra.get('control'):
            quantity = 30
        elif extra.get('cold'):
            quantity = 40
        elif not PRODUCTS_BY_ID[pid][9]:  # sin presentaciones: frascos, tubos, inhaladores
            quantity = 60
        else:
            quantity = 500
        lots = [(f'{pid}_lot_1', f'{code}2610', 540, quantity)]
        if pid in NEAR_EXPIRY:
            days_left, near_quantity = NEAR_EXPIRY[pid]
            lots.append((f'{pid}_lot_2', f'{code}2604', days_left, near_quantity))
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
    body.append('        <!-- Precio por vencer: -20 % hasta 90 días y -40 % hasta 30 días -->')
    for days_left, discount in ((90, 20), (30, 40)):
        body += record(f'expiry_discount_{days_left}', 'pharmacy.expiry.discount', [
            f('days', days_left), f('discount', discount), f('company_id', ref='base.main_company')])
    body.append('        <!-- Canje en borrador del lote de amoxicilina que vence en 45 días -->')
    body += record('supplier_return_amoxicillin', 'pharmacy.supplier.return', [
        f('partner_id', ref='supplier_pacifico'), f('warehouse_id', ref='stock.warehouse0'),
        f('company_id', ref='base.main_company'),
        f('note', 'La droguería canjea por lotes con vencimiento mayor a un año.'),
        f('line_ids', eval="[Command.create({'product_id': obj().env.ref('al_pharmacy_base.product_amoxicillin')"
                           ".product_variant_id.id, 'lot_id': ref('product_amoxicillin_lot_2'), "
                           "'location_id': obj().env.ref('stock.warehouse0').lot_stock_id.id, "
                           "'quantity': 20, 'reason': 'near_expiry', 'price_unit': 0.35})]")])
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
    body = ['        <!-- Prescriptores: hábiles, sin verificar e inhábil -->', *prescriber_records()]
    body.append('        <!-- Pacientes -->')
    for key, name, phone, street, age, allergies, conditions in PATIENTS:
        fields = [f('name', name), f('phone', phone), f('street', street), f('city', 'Lima'),
                  f('country_id', ref='base.pe'), fe('pharmacy_birthdate', days(-365 * age - 40, 'date'))]
        if allergies:
            ids = ', '.join(f"ref('{ref(i)}')" for i in allergies)
            fields.append(f('pharmacy_allergy_ids', eval=f'[Command.set([{ids}])]'))
        if conditions:
            fields.append(f('pharmacy_chronic_conditions', conditions))
        body += record(key, 'res.partner', fields)
    body.append('        <!-- Recetas: por validar, vigentes, dispensadas en parte o del todo, vencida y anulada -->')
    for key, number, prescriber, patient, day, state, diagnosis, lines in PRESCRIPTIONS:
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
            fe('date', days(day, 'date')), f('health_facility', FACILITIES[int(number) % len(FACILITIES)]),
            f('diagnosis', diagnosis), f('warehouse_id', ref='stock.warehouse0'),
            f('manual_state', state), f('line_ids', eval='[%s]' % ', '.join(commands))])
    body.append('        <!-- Dispensaciones (la receta pasa a «dispensada en parte» o «dispensada») -->')
    for key, prescription, line, product, quantity, day in DISPENSATIONS:
        body += record(key, 'pharmacy.dispensation', [
            f('prescription_id', ref=prescription),
            f('prescription_line_id', eval=f"obj().env.ref('al_pharmacy_prescription.{prescription}')"
                                           f".line_ids.sorted('sequence')[{line}].id", model='pharmacy.prescription'),
            fe('product_id', variant(product)), f('quantity', quantity), fe('date', days(day)),
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
                                               "'strength': 10, 'strength_unit': 'mg'})]"),
        *image('al_l10n_pe_pharmacy_controlled', 'product_morphine')])
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
    for index, (patient, *_rest) in enumerate(PATIENTS):
        vat = DNIS[index]
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
    for pid, name, categ, pos_categ, price, cost in NON_PHARMA:
        body += record(pid, 'product.template', [
            f('name', name), f('categ_id', ref=f'product_category_{categ}'), f('list_price', price),
            f('standard_price', cost), f('type', 'consu'), f('is_storable', eval='True'),
            f('available_in_pos', eval='True'),
            f('pos_categ_ids', eval=f"[Command.set([ref('pos_category_{pos_categ}')])]"),
            *image('al_industry_pharmacy', pid)])
    body.append('        <!-- Existencias de los productos no farmacéuticos -->')
    quants = []
    for pid, *_rest in NON_PHARMA:
        body += record(f'{pid}_quant', 'stock.quant', [
            fe('product_id', variant(f'al_industry_pharmacy.{pid}')), f('inventory_quantity', 40),
            fe('location_id', stock_location())])
        quants.append(f'{pid}_quant')
    ids = ', '.join(f"ref('{q}')" for q in quants)
    body += ['        <function model="stock.quant" name="action_apply_inventory">',
             f'            <function eval="[[(\'id\', \'in\', [{ids}])]]" model="stock.quant" name="search"/>',
             '        </function>']
    return document('Botica de demostración del paquete de industria.', body)


# ----------------------------------------------------------------------
# al_pharmacy_care: tratamientos crónicos
# ----------------------------------------------------------------------
def demo_care():
    body = []
    for key, patient, product, units, posology, start, note in TREATMENTS:
        fields = [f('patient_id', ref=f'al_pharmacy_prescription.{patient}'),
                  f'<field name="product_id" search="[(\'product_tmpl_id\', \'=\', ref(\'{ref(product)}\'))]"/>',
                  f('daily_units', units), f('posology', posology), fe('date_start', days(start, 'date')),
                  f('user_id', ref='base.user_admin')]
        if note:
            fields.append(f('note', note))
        body += record(key, 'pharmacy.treatment', fields)
    return document('Tratamientos crónicos de los pacientes de la botica de demostración.', body)


# ----------------------------------------------------------------------
# al_pharmacy_replenishment: faltantes registrados en la caja
# ----------------------------------------------------------------------
def demo_replenishment():
    body = []
    for key, product, quantity, reason, note in SHORTAGES:
        fields = [f('quantity', quantity), f('reason', reason), f('warehouse_id', ref='stock.warehouse0')]
        if product.startswith('product_'):
            fields.insert(0, fe('product_id', variant(product)))
        else:
            fields.insert(0, f('description', product))
        if note:
            fields.append(f('note', note))
        body += record(key, 'pharmacy.shortage', fields)
    return document('Faltantes de la botica de demostración.', body)


# ----------------------------------------------------------------------
# al_pharmacy_website: catálogo publicado en la tienda
# ----------------------------------------------------------------------
def demo_website():
    body = ['        <!-- Medicamentos publicados: genéricos y marcas, de venta libre y con receta\n'
            '             (validada por el Q.F.); los controlados no se venden en línea -->']
    for pid, *_rest, extra in PRODUCTS:
        if extra['categ'] != 'controlled':
            body += record(ref(pid), 'product.template', [f('is_published', eval='True')])
    return document('Tienda en línea de la botica de demostración.', body)


# ----------------------------------------------------------------------
# al_pharmacy_insurance: convenios con aseguradoras
# ----------------------------------------------------------------------
def demo_insurance():
    body = []
    for key, name, street, email, *_rest in INSURERS:
        body += record(key, 'res.partner', [
            f('name', name), f('is_company', eval='True'), f('street', street), f('city', 'Lima'),
            f('country_id', ref='base.pe'), f('email', email)])
    for key, name, phone in AFFILIATES:
        body += record(key, 'res.partner', [f('name', name), f('city', 'Lima'), f('country_id', ref='base.pe'),
                                            f('phone', phone)])
    for partner, _name, _street, _email, agreement, plan, coverage, copay, per_sale, per_month in INSURERS:
        body += record(agreement, 'pharmacy.insurance.agreement', [
            f('name', plan), f('partner_id', ref=partner), f('coverage_percent', coverage),
            f('copay_amount', copay), f('max_per_sale', per_sale), f('max_per_month', per_month),
            fe('date_start', days(-180, 'date'))])
    for key, agreement, partner, number in AFFILIATIONS:
        body += record(key, 'pharmacy.insurance.affiliate', [
            f('agreement_id', ref=agreement), f('partner_id', ref=partner), f('number', number),
            fe('date_start', days(-180, 'date'))])
    for insurer in INSURERS:
        agreement = insurer[4]
        body.append('        <function model="pharmacy.insurance.agreement" name="action_create_pos_payment_method"'
                    f' eval="[[ref(\'{agreement}\')]]"/>')
    return document('Convenios con aseguradoras de la botica de demostración.', body)


FILES = {
    'OL-HEALTH/al_pharmacy_base/demo/pharmacy_demo.xml': demo_base,
    'OL-HEALTH/al_pharmacy_stock/demo/pharmacy_stock_demo.xml': demo_stock,
    'OL-HEALTH/al_pharmacy_prescription/demo/pharmacy_prescription_demo.xml': demo_prescription,
    'OL-HEALTH/al_pharmacy_pos/demo/pharmacy_pos_demo.xml': demo_pos,
    'OL-HEALTH/al_l10n_pe_pharmacy_edi/demo/pharmacy_edi_demo.xml': demo_edi,
    'OL-HEALTH/al_l10n_pe_prescriber_cmp/demo/prescriber_cmp_demo.xml': demo_cmp,
    'OL-HEALTH/al_l10n_pe_pharmacy_controlled/demo/controlled_demo.xml': demo_controlled,
    'OL-HEALTH/al_l10n_pe_pharmacy_digemid/demo/digemid_demo.xml': demo_digemid,
    'OL-HEALTH/al_pharmacy_care/demo/pharmacy_care_demo.xml': demo_care,
    'OL-HEALTH/al_pharmacy_replenishment/demo/pharmacy_replenishment_demo.xml': demo_replenishment,
    'OL-HEALTH/al_pharmacy_website/demo/website_demo.xml': demo_website,
    'OL-HEALTH/al_pharmacy_insurance/demo/pharmacy_insurance_demo.xml': demo_insurance,
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
