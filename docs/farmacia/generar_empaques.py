"""Fotos de estudio de los productos de la demo de farmacia.

Cada producto se dibuja como su envase real (caja, frasco, gotero, tubo,
ampolla, frasco ampolla, lapicero, inhalador, sobre, pote, paquete…) con la
marca inventada de la demo, la concentración, el contenido, el laboratorio y
la condición de venta, sobre fondo blanco y con el mismo encuadre: el
catálogo se ve uniforme, como el de una cadena grande, sin usar fotos ni
marcas ajenas. Es HTML y CSS que Chromium (Playwright) convierte en JPEG de
800 × 800 en ``static/img/demo/<xmlid>.jpg`` del módulo que declara el
producto; ``generar_demo.py`` las incluye en la demo.

Uso (desde la raíz del repositorio)::

    ~/odoo/ce19/.venv/bin/python docs/farmacia/generar_empaques.py [xmlid …]
"""
import html
import io
import re
import sys
import zlib
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import generar_demo as demo  # noqa: E402

ROOT = demo.ROOT
SIZE = 800

# Colores por grupo terapéutico (franja, marca y detalles del envase).
GROUPS = {
    '#E4572E': ['product_paracetamol', 'product_dolofen', 'product_paracetamol_syrup', 'product_ibuprofen',
                'product_ibuflam', 'product_ibuprofen_suspension', 'product_naproxen', 'product_diclofenac_gel',
                'product_aspirin', 'product_antiflu'],
    '#16A3A3': ['product_loratadine', 'product_cetirizine', 'product_chlorphenamine', 'product_ambroxol_syrup',
                'product_dextromethorphan_syrup', 'product_saline_nasal', 'product_salbutamol'],
    '#2E9E4F': ['product_omeprazole', 'product_antacid', 'product_simethicone', 'product_loperamide',
                'product_ors', 'product_mebendazole', 'product_albendazole'],
    '#7B5EA7': ['product_clotrimazole_cream', 'product_artificial_tears', 'product_prednisone',
                'product_dexamethasone', 'product_sertraline'],
    '#F29E1F': ['product_vitamin_c', 'product_ferrous_sulfate'],
    '#1F6FB2': ['product_amoxicillin', 'product_amoxival', 'product_amoxicillin_suspension',
                'product_amoxicillin_clavulanate', 'product_azithromycin', 'product_cephalexin',
                'product_ciprofloxacin', 'product_metronidazole'],
    '#C2185B': ['product_losartan', 'product_tensiloz', 'product_enalapril', 'product_amlodipine',
                'product_atorvastatin', 'product_colestrina'],
    '#0B8DCF': ['product_metformin', 'product_glibenclamide', 'product_insulin', 'product_insulin_glargine',
                'product_levothyroxine'],
    '#5D6D7E': ['product_tamoxifen'],
    '#B71C1C': ['product_clonazepam', 'product_alprazolam', 'product_diazepam', 'product_morphine'],
}
COLOR = {pid: color for color, pids in GROUPS.items() for pid in pids}
BRANDS = {'product_dolofen': 'Dolofen', 'product_ibuflam': 'Ibuflam', 'product_amoxival': 'Amoxival',
          'product_antiflu': 'Antigripal Andino', 'product_tensiloz': 'Tensiloz',
          'product_colestrina': 'Colestrina'}
# Nombre de mostrador (con el principio activo debajo) para envases más legibles.
DISPLAY = {'product_antacid': ('Antiácido', 'Hidróxido de aluminio + magnesio'),
           'product_vitamin_c': ('Vitamina C', 'Ácido ascórbico'),
           'product_artificial_tears': ('Lágrimas artificiales', 'Hipromelosa'),
           'product_ors': ('Suero oral', 'Sales de rehidratación oral'),
           'product_saline_nasal': ('Suero nasal', 'Cloruro de sodio'),
           'product_amoxicillin_clavulanate': ('Amoxicilina + Ác. clavulánico', '')}
FORMS = {'tablet': 'tabletas', 'coated_tablet': 'tabletas recubiertas', 'capsule': 'cápsulas',
         'syrup': 'jarabe', 'suspension': 'suspensión oral', 'drops': 'gotas', 'gel': 'gel', 'cream': 'crema',
         'injection': 'solución inyectable', 'inhaler': 'suspensión para inhalación', 'powder': 'polvo'}
UNITS = {'mg': 'mg', 'g': 'g', 'mcg': 'mcg', 'ui': 'UI/mL', 'ml': 'mL', 'percent': '%', 'mg_ml': 'mg/mL',
         'mg_5ml': 'mg/5 mL'}
# Envase por producto (el resto sale de la forma farmacéutica).
PACKAGES = {
    'product_vitamin_c': 'efftube', 'product_ors': 'sachet', 'product_insulin': 'vial',
    'product_insulin_glargine': 'pen', 'product_dexamethasone': 'ampoule', 'product_morphine': 'ampoule',
    'product_amoxicillin_suspension': 'bottle',
}
# Productos no farmacéuticos: (envase, color, título, subtítulo, contenido, línea).
NON_PHARMA = {
    'product_sunscreen': ('pump', '#F29E1F', 'SolarPro', 'Protector solar FPS 50', '50 mL', 'Dermocosmética'),
    'product_moisturizer': ('pump', '#4FA3D9', 'Hidra+', 'Crema hidratante corporal', '400 mL', 'Dermocosmética'),
    'product_toothpaste': ('tube', '#1F6FB2', 'Dentaclar', 'Pasta dental con flúor', '90 g', 'Cuidado personal'),
    'product_hand_gel': ('pump', '#16A3A3', 'Manos Limpias', 'Alcohol en gel antibacterial', '500 mL',
                         'Cuidado personal'),
    'product_alcohol': ('bottle_clear', '#1F6FB2', 'Alcohol medicinal', '70°', '250 mL', 'Uso externo'),
    'product_diapers': ('bag', '#4FA3D9', 'Pequeñín', 'Pañales talla M', '30 unidades', 'Bebés'),
    'product_baby_wipes': ('wipes', '#E78FB3', 'Pequeñín', 'Toallitas húmedas', '80 unidades', 'Bebés'),
    'product_multivitamin': ('jar', '#F29E1F', 'Vitalfull', 'Multivitamínico adultos', '30 tabletas',
                             'Suplemento'),
    'product_nutritional_shake': ('jar', '#7B5EA7', 'NutriAndes', 'Suplemento nutricional · vainilla', '400 g',
                                  'Nutrición'),
    'product_thermometer': ('box', '#16A3A3', 'TermoDigital', 'Termómetro digital', '1 unidad',
                            'Dispositivo médico'),
    'product_bp_monitor': ('box', '#C2185B', 'PresiónCheck', 'Tensiómetro digital de brazo', '1 unidad',
                           'Dispositivo médico'),
    'product_glucose_strips': ('jar', '#0B8DCF', 'GlucoTest', 'Tiras reactivas para glucómetro', '50 tiras',
                               'Dispositivo médico'),
    'product_face_masks': ('box', '#4FA3D9', 'ProtecMed', 'Mascarillas quirúrgicas descartables',
                           '50 unidades', 'Dispositivo médico'),
    'product_gauze': ('box', '#2E9E4F', 'CuraPlus', 'Gasa estéril 10 x 10 cm', '10 unidades',
                      'Dispositivo médico'),
}
GENERIC_LABS = list(demo.LABS.values())


def esc(text):
    return html.escape(str(text))


def number(value):
    return ('%g' % value).replace('.', ',')


def strength(ingredients):
    units = {unit for _key, _value, unit in ingredients}
    if len(units) == 1:  # combinación con la misma unidad: «500 + 10 + 4 mg»
        return ' + '.join(number(value) for _key, value, _unit in ingredients) + f' {UNITS[units.pop()]}'
    return ' / '.join(f'{number(value)} {UNITS[unit]}' for _key, value, unit in ingredients)


def medicine(product):
    pid, name, ptype, cond, ingredients, form, route, *_rest, registry, _code, extra = product
    dci = ' + '.join(demo.INGREDIENTS[key] for key, _value, _unit in ingredients)
    package = PACKAGES.get(pid) or {
        'tablet': 'box', 'coated_tablet': 'box', 'capsule': 'box', 'syrup': 'bottle', 'suspension': 'bottle',
        'drops': 'dropper', 'gel': 'tube', 'cream': 'tube', 'inhaler': 'inhaler', 'powder': 'bottle',
        'injection': 'ampoule'}[form]
    form_label = FORMS[form]
    if form == 'drops':
        form_label = {'nasal': 'gotas nasales', 'ophthalmic': 'solución oftálmica'}.get(route, 'gotas')
    if pid == 'product_amoxicillin_suspension':
        form_label = 'polvo para suspensión oral'
    if pid == 'product_ors':
        form_label = 'polvo para solución oral'
    if pid == 'product_vitamin_c':
        form_label = 'tabletas efervescentes'
    presentations = product[9]
    match = re.search(r'(\d+(?:,\d+)?) ?(mL|g)\b(?!.*\d)', name)
    if package == 'box':
        units = max([factor for _p, factor, _price in presentations] or [10])
        content = f'Caja x {units} {form_label}'
    elif package == 'efftube':
        content = 'Tubo x 10 tabletas'
    elif package == 'inhaler':
        content = '200 dosis'
    elif match:
        content = f'{match.group(1)} {match.group(2)}'
    else:
        content = ''
    lab = demo.LABS.get(extra.get('lab')) or GENERIC_LABS[zlib.crc32(pid.encode()) % len(GENERIC_LABS)]
    badges = []
    if ptype == 'generic_dci':
        badges.append(('generic', 'Medicamento genérico'))
    if extra.get('categ') == 'controlled':
        badges.append(('controlled', 'Receta especial'))
    elif cond == 'prescription':
        badges.append(('rx', 'Venta bajo receta médica'))
    else:
        badges.append(('otc', 'Venta libre'))
    if extra.get('cold'):
        badges.append(('cold', 'Conservar entre 2 °C y 8 °C'))
    title, subtitle = DISPLAY.get(pid, (BRANDS.get(pid, dci), dci if pid in BRANDS else ''))
    return {
        'package': package, 'color': COLOR.get(pid, '#1F6FB2'), 'title': title, 'dci': subtitle, 'strength': strength(ingredients), 'form': form_label,
        'content': content, 'lab': lab, 'badges': badges, 'registry': f'Reg. San. {registry}',
        'pill': 'capsule' if form == 'capsule' else 'tablet',
    }


def other(pid):
    package, color, title, subtitle, content, line = NON_PHARMA[pid]
    return {'package': package, 'color': color, 'title': title, 'dci': '', 'strength': subtitle, 'form': '',
            'content': content, 'lab': line, 'badges': [], 'registry': '', 'pill': ''}


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { width: 800px; height: 800px; background: #fff; font-family: 'Liberation Sans', Arial, sans-serif;
       color: #1d2733; overflow: hidden; }
.stage { position: relative; width: 800px; height: 800px; display: flex; flex-direction: column;
         align-items: center; justify-content: center; perspective: 1900px; }
.obj { position: relative; z-index: 1; display: flex; justify-content: center; align-items: flex-end; }
.floor { width: 600px; height: 70px; margin-top: -48px;
         background: radial-gradient(ellipse at center, rgba(0,0,0,.26) 0%, rgba(0,0,0,.09) 42%, rgba(0,0,0,0) 70%); }
.badge { display: inline-block; border-radius: 6px; padding: 5px 10px; font-size: 15px; font-weight: 700;
         letter-spacing: .2px; }
.badge.generic { background: #fff; color: var(--c); border: 2px solid var(--c); }
.badge.otc { background: #2E9E4F; color: #fff; }
.badge.rx { background: #1d2733; color: #fff; }
.badge.controlled { background: #B71C1C; color: #fff; }
.badge.cold { background: #0B8DCF; color: #fff; }
.title { font-weight: 800; line-height: 1.02; color: var(--c); letter-spacing: -.5px; }
.strength { font-weight: 700; color: #1d2733; }
.muted { color: #5b6672; }

/* --- Caja --- */
.box { position: relative; width: var(--w); height: var(--h); transform-style: preserve-3d;
       transform: rotateX(-14deg) rotateY(28deg); margin-bottom: 30px; }
.box .face { position: absolute; top: 0; left: 0; overflow: hidden; }
.box .front { width: var(--w); height: var(--h); transform: translateZ(calc(var(--d) / 2)); background: #fff;
              padding: 28px 30px 22px 34px; display: flex; flex-direction: column;
              box-shadow: inset 0 0 0 1px rgba(0,0,0,.06); }
.box .front::before { content: ''; position: absolute; right: -60px; top: -40px; width: 260px; height: 520px;
                      background: var(--c); transform: rotate(24deg); opacity: .95; }
.box .front::after { content: ''; position: absolute; right: 10px; top: -40px; width: 30px; height: 520px;
                     background: var(--c); transform: rotate(24deg); opacity: .35; }
.box .front > * { position: relative; z-index: 1; }
.box .side { width: var(--d); height: var(--h); left: calc((var(--w) - var(--d)) / 2);
             transform: rotateY(-90deg) translateZ(calc(var(--w) / 2)); background: #f3f5f7;
             border-left: 10px solid var(--c); filter: brightness(.86); display: flex; align-items: center;
             justify-content: center; }
.box .side span { transform: rotate(-90deg); white-space: nowrap; font-weight: 800; font-size: 26px;
                  color: var(--c); }
.box .top { width: var(--w); height: var(--d); top: calc((var(--h) - var(--d)) / 2);
            transform: rotateX(90deg) translateZ(calc(var(--h) / 2)); background: linear-gradient(#ffffff, #eef1f4);
            border-bottom: 6px solid var(--c); }
.box .title { font-size: 46px; max-width: 64%; }
.box .strength { font-size: 34px; margin-top: 6px; max-width: 62%; line-height: 1.1; }
.box .form { font-size: 19px; margin-top: 10px; max-width: 56%; }
.box .spacer { flex: 1; }
.box .lab { font-size: 14px; font-weight: 700; color: #5b6672; margin-top: 8px; max-width: 58%; line-height: 1.3; }
.box .badges { display: flex; flex-wrap: wrap; gap: 8px; max-width: 60%; }
.box .pill { position: absolute; right: 44px; bottom: 34px; z-index: 2; }

/* --- Cilindros (frascos, potes, tubos efervescentes) --- */
.cyl { position: relative; display: flex; flex-direction: column; align-items: center; margin-bottom: 30px; }
.cap { border-radius: 10px 10px 4px 4px;
       background: repeating-linear-gradient(90deg, rgba(255,255,255,.18) 0 3px, rgba(0,0,0,.12) 3px 6px),
                   linear-gradient(90deg, #2b2f33, #6b7076 45%, #2b2f33); }
.cap.white { background: repeating-linear-gradient(90deg, rgba(0,0,0,.05) 0 3px, rgba(0,0,0,.12) 3px 6px),
                         linear-gradient(90deg, #cfd5db, #ffffff 45%, #c3c9cf); }
.cap.color { background: repeating-linear-gradient(90deg, rgba(255,255,255,.12) 0 3px, rgba(0,0,0,.15) 3px 6px),
                         var(--c); }
.neck { background: inherit; }
.glass-amber { background: linear-gradient(90deg, #3d1d06, #8a4512 18%, #c06a1f 38%, #9a4f15 62%, #4a2408); }
.glass-clear { background: linear-gradient(90deg, rgba(160,175,185,.55), rgba(240,246,250,.9) 30%,
               rgba(255,255,255,.95) 45%, rgba(190,205,215,.7) 75%, rgba(140,155,165,.6)); }
.plastic { background: linear-gradient(90deg, #c9cfd5, #ffffff 35%, #f4f6f8 60%, #b8bfc6); }
.plastic-color { background: linear-gradient(90deg, rgba(0,0,0,.25), rgba(255,255,255,.25) 35%, rgba(0,0,0,0) 60%,
                 rgba(0,0,0,.28)), var(--c); }
.label { position: absolute; background: #fff; display: flex; flex-direction: column; padding: 16px 18px;
         box-shadow: inset 14px 0 18px -10px rgba(0,0,0,.25), inset -14px 0 18px -10px rgba(0,0,0,.3); }
.label .band { position: absolute; left: 0; right: 0; top: 0; height: 12px; background: var(--c); }
.label .title { font-size: 34px; margin-top: 10px; }
.label .strength { font-size: 24px; margin-top: 4px; }
.label .form { font-size: 16px; margin-top: 4px; }
.label .content { font-size: 18px; font-weight: 700; margin-top: 6px; }
.label .lab { font-size: 13px; font-weight: 700; color: #5b6672; margin-top: auto; }
.label .badges { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.label .badge { font-size: 12px; padding: 4px 7px; }
.label.compact .title { font-size: 26px; }
.label.compact .strength { font-size: 18px; }
.label.compact .content { font-size: 15px; }
.shine { position: absolute; top: 0; bottom: 0; left: 22%; width: 7%;
         background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,.55), rgba(255,255,255,0)); }

/* --- Tubo de crema --- */
.tube { position: relative; width: 600px; height: 190px; margin-bottom: 40px; transform: rotate(-8deg); }
.tube .body { position: absolute; left: 0; top: 0; width: 520px; height: 190px;
              clip-path: polygon(0 4%, 6% 0, 100% 10%, 100% 90%, 6% 100%, 0 96%);
              background: linear-gradient(180deg, #c8ced4, #ffffff 30%, #f7f9fa 55%, #b7bec5); }
.tube .crimp { position: absolute; left: 0; top: 6px; width: 30px; height: 178px;
               background: repeating-linear-gradient(90deg, #d5dade 0 3px, #9aa3ab 3px 5px); }
.tube .cap2 { position: absolute; left: 518px; top: 34px; width: 82px; height: 122px; border-radius: 6px 22px 22px 6px;
              background: linear-gradient(180deg, rgba(0,0,0,.25), rgba(255,255,255,.3) 35%, rgba(0,0,0,0) 60%,
              rgba(0,0,0,.3)), var(--c); }
.tube .print { position: absolute; left: 60px; top: 30px; width: 420px; height: 130px; display: flex;
               flex-direction: column; justify-content: center; }
.tube .print .title { font-size: 40px; }
.tube .print .strength { font-size: 22px; margin-top: 4px; }
.tube .print .meta { font-size: 15px; margin-top: 6px; color: #5b6672; font-weight: 700; }
.tube .stripe { position: absolute; left: 30px; right: 90px; bottom: 22px; height: 14px; background: var(--c);
                opacity: .9; }

/* --- Ampolla y frasco ampolla --- */
.ampoule { position: relative; width: 150px; height: 520px; margin-bottom: 60px; }
.ampoule .tip { position: absolute; left: 52px; top: 0; width: 46px; height: 110px; border-radius: 23px 23px 6px 6px; }
.ampoule .neck2 { position: absolute; left: 62px; top: 104px; width: 26px; height: 46px; }
.ampoule .ring { position: absolute; left: 58px; top: 112px; width: 34px; height: 9px; background: var(--c); }
.ampoule .shoulder { position: absolute; left: 20px; top: 146px; width: 110px; height: 60px;
                     border-radius: 50% 50% 0 0 / 100% 100% 0 0; }
.ampoule .body2 { position: absolute; left: 20px; top: 200px; width: 110px; height: 300px; border-radius: 0 0 26px 26px; }
.ampoule .liquid { position: absolute; left: 20px; top: 250px; width: 110px; height: 250px; border-radius: 0 0 26px 26px;
                   background: linear-gradient(90deg, rgba(200,170,90,.25), rgba(255,240,200,.35), rgba(200,170,90,.3)); }
.ampoule .label { left: 20px; top: 300px; width: 110px; height: 150px; padding: 8px 8px; }
.ampoule .label .title { font-size: 17px; margin-top: 10px; }
.ampoule .label .strength { font-size: 13px; }
.ampoule .label .form, .ampoule .label .content { font-size: 11px; }
.ampoule-box { position: absolute; }

/* --- Lapicero de insulina --- */
.pen { position: relative; width: 640px; height: 120px; transform: rotate(-12deg); margin-bottom: 30px; }
.pen .barrel { position: absolute; left: 0; top: 0; width: 470px; height: 120px; border-radius: 20px 10px 10px 20px;
               background: linear-gradient(180deg, #8d969e, #e9edf0 30%, #ffffff 45%, #a9b1b8); }
.pen .capp { position: absolute; left: 462px; top: 4px; width: 178px; height: 112px; border-radius: 8px 40px 40px 8px;
             background: linear-gradient(180deg, rgba(0,0,0,.3), rgba(255,255,255,.3) 35%, rgba(0,0,0,0) 60%,
             rgba(0,0,0,.3)), var(--c); }
.pen .clip { position: absolute; left: 500px; top: -10px; width: 120px; height: 18px; border-radius: 9px;
             background: linear-gradient(180deg, #9aa3ab, #eef1f3, #8a939b); }
.pen .dial { position: absolute; left: -26px; top: 18px; width: 40px; height: 84px; border-radius: 12px;
             background: repeating-linear-gradient(180deg, #555 0 4px, #999 4px 7px); }
.pen .window { position: absolute; left: 330px; top: 30px; width: 110px; height: 60px; border-radius: 8px;
               background: linear-gradient(180deg, #b9e3f7, #eaf7fd, #a5d6ee); box-shadow: inset 0 0 0 2px rgba(0,0,0,.2); }
.pen .print { position: absolute; left: 40px; top: 18px; width: 280px; height: 84px; display: flex;
              flex-direction: column; justify-content: center; }
.pen .print .title { font-size: 28px; }
.pen .print .strength { font-size: 18px; }
.pen .print .meta { font-size: 13px; color: #5b6672; font-weight: 700; }

/* --- Inhalador --- */
.inhaler { position: relative; width: 330px; height: 470px; margin-bottom: 40px; transform: rotate(-6deg); }
.inhaler .can { position: absolute; left: 60px; top: 0; width: 150px; height: 230px; border-radius: 30px 30px 6px 6px;
                background: linear-gradient(90deg, #8d969e, #f2f4f6 35%, #ffffff 45%, #a9b1b8); }
.inhaler .act { position: absolute; left: 40px; top: 150px; width: 190px; height: 300px; border-radius: 26px 26px 34px 34px; }
.inhaler .mouth { position: absolute; left: 200px; top: 360px; width: 120px; height: 86px; border-radius: 0 24px 30px 0; }
.inhaler .label { left: 52px; top: 190px; width: 166px; height: 200px; padding: 10px 12px; border-radius: 6px; }
.inhaler .label .title { font-size: 24px; }
.inhaler .label .strength { font-size: 15px; }
.inhaler .label .form, .inhaler .label .content { font-size: 12px; }

/* --- Sobre --- */
.sachet { position: relative; width: 420px; height: 560px; margin-bottom: 40px; transform: rotate(-7deg);
          filter: drop-shadow(0 18px 18px rgba(0,0,0,.18)); }
.sachet .bag { position: absolute; inset: 0; background: linear-gradient(90deg, #e9edf0, #ffffff 30%, #f5f7f8 70%, #d7dde2); }
.sachet .seal { position: absolute; left: 0; right: 0; height: 34px;
                background: repeating-linear-gradient(90deg, #c9d0d6 0 4px, #eef1f3 4px 8px); }
.sachet .print { position: absolute; left: 34px; right: 34px; top: 70px; bottom: 70px; display: flex;
                 flex-direction: column; }
.sachet .print .band { height: 70px; background: var(--c); margin: 0 -34px 24px; }
.sachet .print .title { font-size: 40px; }
.sachet .print .strength { font-size: 24px; margin-top: 8px; }
.sachet .print .form { font-size: 18px; margin-top: 8px; }
.sachet .print .lab { margin-top: auto; font-size: 15px; font-weight: 700; color: #5b6672; }
.sachet .badges { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }

/* --- Paquetes blandos --- */
.bag2 { position: relative; width: 470px; height: 580px; margin-bottom: 40px; border-radius: 60px 60px 40px 40px;
        background: linear-gradient(90deg, rgba(0,0,0,.18), rgba(255,255,255,.25) 30%, rgba(0,0,0,0) 65%,
        rgba(0,0,0,.2)), var(--c); }
.bag2 .window2 { position: absolute; left: 50px; right: 50px; top: 150px; height: 260px; border-radius: 30px;
                 background: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center;
                 text-align: center; padding: 20px; }
.bag2 .window2 .title { font-size: 50px; }
.bag2 .window2 .strength { font-size: 26px; margin-top: 10px; }
.bag2 .window2 .content { font-size: 22px; margin-top: 12px; font-weight: 700; }
.bag2 .top2 { position: absolute; left: 40px; right: 40px; top: 40px; height: 60px; color: #fff; font-size: 26px;
              font-weight: 800; text-align: center; line-height: 60px; }
.wipes { position: relative; width: 560px; height: 340px; margin-bottom: 40px; border-radius: 50px;
         background: linear-gradient(180deg, rgba(255,255,255,.4), rgba(255,255,255,0) 40%, rgba(0,0,0,.12)), #fff;
         box-shadow: inset 0 0 0 3px rgba(0,0,0,.05); transform: rotateX(18deg); }
.wipes .lid { position: absolute; left: 150px; top: 26px; width: 260px; height: 90px; border-radius: 30px;
              background: linear-gradient(180deg, #ffffff, var(--c)); box-shadow: 0 6px 12px rgba(0,0,0,.18); }
.wipes .print { position: absolute; left: 40px; right: 40px; top: 140px; bottom: 30px; display: flex;
                flex-direction: column; align-items: center; text-align: center; }
.wipes .print .title { font-size: 46px; }
.wipes .print .strength { font-size: 24px; margin-top: 6px; }
.wipes .print .content { font-size: 20px; font-weight: 700; margin-top: 6px; color: var(--c); }
"""


def fit(text, size, chars, minimum=20):
    """Tamaño de letra para que ``text`` quepa en el ancho de ``chars`` caracteres a ``size`` px."""
    longest = max((len(word) for word in str(text).split()), default=0)
    length = max(len(str(text)) / 2 if len(str(text)) > chars * 1.4 else len(str(text)), longest)
    return max(minimum, min(size, int(size * chars / max(length, 1))))


def badges_html(badges):
    return ''.join(f'<span class="badge {kind}">{esc(text)}</span>' for kind, text in badges)


def pill_svg(kind, color):
    if kind == 'capsule':
        return (f'<svg width="120" height="60" viewBox="0 0 120 60"><g transform="rotate(-18 60 30)">'
                f'<rect x="8" y="14" width="104" height="34" rx="17" fill="#fff" stroke="#c9d0d6" stroke-width="2"/>'
                f'<path d="M60 14 h35 a17 17 0 0 1 0 34 h-35z" fill="{color}"/>'
                f'<rect x="16" y="18" width="80" height="6" rx="3" fill="#fff" opacity=".6"/></g></svg>')
    if kind == 'tablet':
        return (f'<svg width="110" height="70" viewBox="0 0 110 70">'
                f'<ellipse cx="40" cy="38" rx="32" ry="26" fill="#fff" stroke="#c9d0d6" stroke-width="2"/>'
                f'<line x1="14" y1="38" x2="66" y2="38" stroke="#c9d0d6" stroke-width="3"/>'
                f'<ellipse cx="78" cy="32" rx="26" ry="21" fill="#fff" stroke="#c9d0d6" stroke-width="2"/>'
                f'<line x1="58" y1="32" x2="98" y2="32" stroke="#c9d0d6" stroke-width="3"/></svg>')
    return ''


def text_block(info, with_content=True, size=34, chars=11):
    parts = [f'<div class="title" style="font-size:{fit(info["title"], size, chars)}px">{esc(info["title"])}</div>']
    if info['dci']:
        parts.append(f'<div class="muted form">{esc(info["dci"])}</div>')
    parts.append(f'<div class="strength">{esc(info["strength"])}</div>')
    if info['form']:
        parts.append(f'<div class="form muted">{esc(info["form"])}</div>')
    if with_content and info['content']:
        parts.append(f'<div class="content">{esc(info["content"])}</div>')
    return ''.join(parts)


def render_box(info):
    width, height, depth = 460, 330, 130
    side = info['dci'] or info['title']
    return f'''
<div class="box" style="--w:{width}px;--h:{height}px;--d:{depth}px">
  <div class="face top"></div>
  <div class="face side"><span>{esc(side)}</span></div>
  <div class="face front">
    <div class="title" style="font-size:{fit(info['title'], 46, 11, 28)}px">{esc(info['title'])}</div>
    {f'<div class="muted form">{esc(info["dci"])}</div>' if info['dci'] else ''}
    <div class="strength" style="font-size:{fit(info['strength'], 34, 13, 20)}px">{esc(info['strength'])}</div>
    <div class="form muted">{esc(info['content'] or info['form'])}</div>
    <div class="spacer"></div>
    <div class="badges">{badges_html(info['badges'])}</div>
    <div class="lab">{esc(info['lab'])}{'<br/>' + esc(info['registry']) if info['registry'] else ''}</div>
    <div class="pill">{pill_svg(info['pill'], info['color'])}</div>
  </div>
</div>'''


def label(info, style, compact=False):
    if compact:
        info = {**info, 'form': '', 'dci': ''}
        badges = [b for b in info['badges'] if b[0] != 'generic'][:1]
        return (f'<div class="label compact" style="{style}"><div class="band"></div>{text_block(info, size=26, chars=9)}'
                f'<div class="badges">{badges_html(badges)}</div></div>')
    return (f'<div class="label" style="{style}"><div class="band"></div>{text_block(info, chars=10)}'
            f'<div class="badges">{badges_html(info["badges"])}</div>'
            f'<div class="lab">{esc(info["lab"])}</div></div>')


def render_bottle(info, glass='glass-amber', cap='', width=250, height=380, neck=70):
    return f'''
<div class="cyl">
  <div class="cap {cap}" style="width:{width * .52:.0f}px;height:74px"></div>
  <div class="{glass}" style="width:{width * .4:.0f}px;height:{neck * .5:.0f}px"></div>
  <div class="{glass}" style="width:{width}px;height:{height}px;border-radius:70px 70px 26px 26px;position:relative">
    <div class="shine"></div>
    {label(info, f'left:0;right:0;top:{height * .13:.0f}px;height:{height * .78:.0f}px')}
  </div>
</div>'''


def render_dropper(info):
    return f'''
<div class="cyl">
  <div class="cap color" style="width:56px;height:96px;border-radius:28px 28px 8px 8px;clip-path:polygon(32% 0,68% 0,100% 100%,0 100%)"></div>
  <div class="cap white" style="width:140px;height:60px"></div>
  <div class="plastic" style="width:220px;height:360px;border-radius:60px 60px 30px 30px;position:relative">
    <div class="shine"></div>
    {label(info, 'left:0;right:0;top:70px;height:250px', compact=True)}
  </div>
</div>'''


def render_efftube(info):
    return f'''
<div class="cyl" style="transform:rotate(-4deg)">
  <div class="cap color" style="width:200px;height:90px;border-radius:14px 14px 6px 6px"></div>
  <div class="plastic" style="width:190px;height:470px;border-radius:6px 6px 20px 20px;position:relative">
    <div class="shine"></div>
    {label(info, 'left:0;right:0;top:40px;height:380px')}
  </div>
</div>'''


def render_jar(info, height=330):
    return f'''
<div class="cyl">
  <div class="cap color" style="width:320px;height:70px;border-radius:12px 12px 4px 4px"></div>
  <div class="plastic" style="width:340px;height:{height}px;border-radius:24px 24px 30px 30px;position:relative">
    <div class="shine"></div>
    {label(info, f'left:0;right:0;top:30px;height:{height - 60}px;align-items:center;text-align:center')}
  </div>
</div>'''


def render_pump(info):
    return f'''
<div class="cyl">
  <div style="display:flex;align-items:flex-end"><div class="cap white" style="width:120px;height:26px;border-radius:6px"></div>
    <div class="cap white" style="width:60px;height:18px;border-radius:0 9px 9px 0;margin-bottom:6px"></div></div>
  <div class="cap white" style="width:36px;height:56px;border-radius:4px"></div>
  <div class="cap color" style="width:120px;height:46px;border-radius:10px 10px 4px 4px"></div>
  <div class="plastic" style="width:250px;height:400px;border-radius:40px 40px 30px 30px;position:relative">
    <div class="shine"></div>
    {label(info, 'left:0;right:0;top:50px;height:300px;align-items:center;text-align:center')}
  </div>
</div>'''


def render_tube(info):
    meta = info['content'] or ''
    badge = badges_html(info['badges'][:1])
    return f'''
<div class="tube">
  <div class="body"></div><div class="crimp"></div><div class="cap2"></div><div class="stripe"></div>
  <div class="print"><div class="title">{esc(info['title'])}</div>
    <div class="strength">{esc(info['strength'])} {esc(info['form'])}</div>
    <div class="meta">{esc(meta)} · {esc(info['lab'])}</div><div style="margin-top:8px">{badge}</div></div>
</div>'''


def render_ampoule(info):
    return f'''
<div style="display:flex;gap:26px;align-items:flex-end;margin-bottom:40px;transform:rotate(-4deg)">
  <div class="ampoule">
    <div class="tip glass-clear"></div><div class="neck2 glass-clear"></div><div class="ring"></div>
    <div class="shoulder glass-clear"></div><div class="body2 glass-clear"></div><div class="liquid"></div>
    {label(info, 'left:20px;top:300px;width:110px;height:170px;padding:8px', compact=True)}
  </div>
  {render_box({**info, 'pill': ''})}
</div>'''


def render_vial(info):
    return f'''
<div class="cyl" style="transform:rotate(-3deg)">
  <div class="cap color" style="width:150px;height:60px;border-radius:12px"></div>
  <div style="width:150px;height:22px;background:linear-gradient(90deg,#9aa3ab,#eef1f3,#8a939b)"></div>
  <div class="glass-clear" style="width:110px;height:50px"></div>
  <div class="glass-clear" style="width:230px;height:360px;border-radius:50px 50px 24px 24px;position:relative">
    <div style="position:absolute;left:0;right:0;bottom:0;height:230px;border-radius:0 0 24px 24px;background:linear-gradient(90deg,rgba(180,200,220,.35),rgba(240,248,255,.5),rgba(180,200,220,.4))"></div>
    {label(info, 'left:0;right:0;top:60px;height:270px', compact=True)}
  </div>
</div>'''


def render_pen(info):
    meta = ' · '.join(filter(None, [info['content'], info['lab']]))
    return f'''
<div class="pen"><div class="dial"></div><div class="barrel"></div><div class="window"></div>
  <div class="capp"></div><div class="clip"></div>
  <div class="print"><div class="title">{esc(info['title'])}</div>
    <div class="strength">{esc(info['strength'])}</div><div class="meta">{esc(meta)}</div></div>
</div>'''


def render_inhaler(info):
    return f'''
<div class="inhaler">
  <div class="can"></div>
  <div class="act plastic-color"></div><div class="mouth plastic-color"></div>
  {label(info, 'left:52px;top:190px;width:166px;height:220px;padding:10px 12px;border-radius:6px', compact=True)}
</div>'''


def render_sachet(info):
    return f'''
<div class="sachet"><div class="bag"></div><div class="seal" style="top:0"></div><div class="seal" style="bottom:0"></div>
  <div class="print"><div class="band"></div>{text_block(info)}
    <div class="badges">{badges_html(info['badges'])}</div><div class="lab">{esc(info['lab'])}</div></div>
</div>'''


def render_bag(info):
    return f'''
<div class="bag2"><div class="top2">{esc(info['lab'])}</div>
  <div class="window2"><div class="title">{esc(info['title'])}</div><div class="strength">{esc(info['strength'])}</div>
    <div class="content">{esc(info['content'])}</div></div></div>'''


def render_wipes(info):
    return f'''
<div class="wipes"><div class="lid"></div><div class="print"><div class="title">{esc(info['title'])}</div>
  <div class="strength">{esc(info['strength'])}</div><div class="content">{esc(info['content'])}</div></div></div>'''


RENDER = {
    'box': render_box, 'bottle': render_bottle, 'dropper': render_dropper, 'efftube': render_efftube,
    'jar': render_jar, 'pump': render_pump, 'tube': render_tube, 'ampoule': render_ampoule, 'vial': render_vial,
    'pen': render_pen, 'inhaler': render_inhaler, 'sachet': render_sachet, 'bag': render_bag,
    'wipes': render_wipes, 'bottle_clear': lambda info: render_bottle(info, 'glass-clear', 'white', 240, 400),
}


ZOOM = {'box': 1.28, 'bottle': 1.25, 'bottle_clear': 1.2, 'dropper': 1.3, 'efftube': 1.1, 'jar': 1.3,
        'pump': 1.15, 'tube': 1.15, 'ampoule': 1.05, 'vial': 1.25, 'pen': 1.1, 'inhaler': 1.3, 'sachet': 1.12,
        'bag': 1.1, 'wipes': 1.2}


def page(info):
    body = f'<div class="obj" style="zoom:{ZOOM[info["package"]]}">{RENDER[info["package"]](info)}</div>'
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>'
            f'<body style="--c:{info["color"]}"><div class="stage">{body}<div class="floor"></div></div></body></html>')


def products():
    for product in demo.PRODUCTS:
        yield product[0], 'al_pharmacy_base', medicine(product)
    morphine = demo.P('product_morphine', 'Morfina 10 mg/mL solución inyectable ampolla 1 mL', 'generic_dci',
                      'controlled', [('ingredient_morphine', 10, 'mg_ml')], 'injection', 'im', 0, 0, [],
                      'EN-02211', '', 'controlled')
    demo.INGREDIENTS.setdefault('ingredient_morphine', 'Morfina')
    info = medicine(morphine)
    info['content'] = '1 mL'
    yield 'product_morphine', 'al_l10n_pe_pharmacy_controlled', info
    for pid in NON_PHARMA:
        yield pid, 'al_industry_pharmacy', other(pid)


def main(only=()):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        tab = browser.new_page(viewport={'width': SIZE, 'height': SIZE})
        count = 0
        for pid, module, info in products():
            if only and pid not in only:
                continue
            tab.set_content(page(info))
            png = tab.screenshot(type='png')
            folder = 'OL-INDUSTRIES' if module.startswith('al_industry') else 'OL-HEALTH'
            target = ROOT / folder / module / 'static/img/demo' / f'{pid}.jpg'
            target.parent.mkdir(parents=True, exist_ok=True)
            Image.open(io.BytesIO(png)).convert('RGB').save(target, 'JPEG', quality=88, optimize=True)
            count += 1
        browser.close()
    print(f'{count} empaques')


if __name__ == '__main__':
    main(set(sys.argv[1:]))
