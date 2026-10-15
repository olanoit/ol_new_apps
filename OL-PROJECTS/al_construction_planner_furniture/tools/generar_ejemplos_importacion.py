# -*- coding: utf-8 -*-
"""Genera los libros de ejemplo de «Importar maestro y ETO» (W-15).

    static/examples/maestro_planificacion_ejemplo.xlsx
        Obra genérica de 3 pisos con 4 departamentos por piso y, en cada
        departamento, cocina (tipología C01 o C02), closet (CL01) y baño
        (B01): catálogo de actividades, tipologías, módulos con ancho,
        actividades por ambiente, BOM con etapa y árbol.
    static/examples/eto_ejemplo.xlsx
        Módulos reales (código y ancho) de las cocinas del piso 01.

Todos los datos son ficticios (prefijo EJ- en códigos de actividad y de
producto). Los libros traen a propósito, documentado en su hoja LEEME, lo
que el asistente debe avisar: una fila de BOM sin etapa, un producto
repetido en una BOM, un producto sin costo, una cantidad con cuatro
decimales y, en el ETO, un ambiente que no existe.

Python puro y reproducible (mismos datos en cada ejecución):
  .venv/bin/python tools/generar_ejemplos_importacion.py
El test ``tests/test_import.py`` importa estos mismos libros y usa las
constantes de este archivo para calcular las cifras esperadas.
"""
import importlib.util
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = MODULE_DIR / 'static' / 'examples'
MASTER_FILE = 'maestro_planificacion_ejemplo.xlsx'
ETO_FILE = 'eto_ejemplo.xlsx'

# código, nombre, etapa, unidad, se mide por, grupo ML, tarifa base
CATALOG = [
    ('EJ-ARM-TOR', 'Armado módulo con tornillo', 'Armado', 'UND', 'Módulo', '', 6.00),
    ('EJ-ARM-TAR', 'Armado módulo con tarugo', 'Armado', 'UND', 'Módulo', '', 8.00),
    ('EJ-ARM-CAM', 'Armado módulo de campana', 'Armado', 'UND', 'Módulo', '', 7.00),
    ('EJ-ARM-CAJ', 'Armado cajonera', 'Armado', 'UND', 'Módulo', '', 7.00),
    ('EJ-ARM-CLO', 'Armado módulo de closet', 'Armado', 'UND', 'Módulo', '', 9.00),
    ('EJ-ARM-VAN', 'Armado mueble de baño', 'Armado', 'UND', 'Módulo', '', 8.00),
    ('EJ-COL-PUE', 'Colocación de puertas', 'Armado', 'UND', 'Ambiente', '', 3.00),
    ('EJ-INS-BAJ', 'Instalación mueble bajo', 'Instalación', 'ML', 'ML', 'Mueble bajo', 18.00),
    ('EJ-INS-ALT', 'Instalación mueble alto', 'Instalación', 'ML', 'ML', 'Mueble alto', 18.00),
    ('EJ-INS-CLO', 'Instalación de closet', 'Instalación', 'UND', 'Ambiente', '', 25.00),
    ('EJ-LIM-BAJ', 'Limpieza mueble bajo', 'Acabado y entrega', 'ML', 'ML', 'Mueble bajo', 6.00),
    ('EJ-LIM-ALT', 'Limpieza mueble alto', 'Acabado y entrega', 'ML', 'ML', 'Mueble alto', 6.00),
    ('EJ-ENT', 'Entrega y protección', 'Acabado y entrega', 'UND', 'Ambiente', '', 5.00),
]

# código, nombre, familia
TYPOLOGIES = [
    ('C01', 'Cocina tipo 01', 'Cocina'),
    ('C02', 'Cocina tipo 02', 'Cocina'),
    ('CL01', 'Closet dormitorio', 'Closet'),
    ('B01', 'Mueble de baño', 'Baño'),
]

# tipología → [(código, tipo, ancho mm, grupo ML, actividad de armado)]
MODULES = {
    'C01': [('MB01', 'Bajo', 600, 'Mueble bajo', 'EJ-ARM-TOR'),
            ('MB02', 'Bajo', 800, 'Mueble bajo', 'EJ-ARM-TAR'),
            ('MB03', 'Cajonera', 450, 'Mueble bajo', 'EJ-ARM-CAJ'),
            ('MA01', 'Alto', 600, 'Mueble alto', 'EJ-ARM-TAR'),
            ('MA02', 'Alto', 800, 'Mueble alto', 'EJ-ARM-TAR'),
            ('CAMPANA', 'Campana', 600, 'Mueble alto', 'EJ-ARM-CAM')],
    'C02': [('MB01', 'Bajo', 600, 'Mueble bajo', 'EJ-ARM-TOR'),
            ('MB02', 'Bajo', 900, 'Mueble bajo', 'EJ-ARM-TAR'),
            ('MB03', 'Cajonera', 450, 'Mueble bajo', 'EJ-ARM-CAJ'),
            ('MB04', 'Bajo', 400, 'Mueble bajo', 'EJ-ARM-TOR'),
            ('MA01', 'Alto', 600, 'Mueble alto', 'EJ-ARM-TAR'),
            ('MA02', 'Alto', 900, 'Mueble alto', 'EJ-ARM-TAR'),
            ('CAMPANA', 'Campana', 600, 'Mueble alto', 'EJ-ARM-CAM')],
    'CL01': [('CL01', 'Otro', 1000, 'Sin ML', 'EJ-ARM-CLO'),
             ('CL02', 'Otro', 1000, 'Sin ML', 'EJ-ARM-CLO'),
             ('CL03', 'Repisero', 600, 'Sin ML', 'EJ-ARM-CLO')],
    'B01': [('VAN01', 'Bajo', 800, 'Mueble bajo', 'EJ-ARM-VAN')],
}

# tipología → [(actividad, cantidad por ambiente)]. Las actividades por ML
# llevan los ML de la tipología: con anchos, el plan las baja a los módulos.
ACTIVITIES = {
    'C01': [('EJ-COL-PUE', 6), ('EJ-INS-BAJ', 1.85), ('EJ-INS-ALT', 2.0),
            ('EJ-LIM-BAJ', 1.85), ('EJ-LIM-ALT', 2.0), ('EJ-ENT', 1)],
    'C02': [('EJ-COL-PUE', 7), ('EJ-INS-BAJ', 2.35), ('EJ-INS-ALT', 2.1),
            ('EJ-LIM-BAJ', 2.35), ('EJ-LIM-ALT', 2.1), ('EJ-ENT', 1)],
    'CL01': [('EJ-COL-PUE', 4), ('EJ-INS-CLO', 1), ('EJ-ENT', 1)],
    'B01': [('EJ-COL-PUE', 1), ('EJ-INS-BAJ', 0.8), ('EJ-LIM-BAJ', 0.8), ('EJ-ENT', 1)],
}

# código → (nombre, unidad, costo unitario). EJ-PIN va sin costo a propósito.
PRODUCTS = {
    'EJ-MEL-BLA': ('Melamina blanca 18 mm (plancha)', 'UND', 160.00),
    'EJ-MEL-MAD': ('Melamina color madera 18 mm (plancha)', 'UND', 185.00),
    'EJ-MEL-RH': ('Melamina hidrófuga 18 mm (plancha)', 'UND', 195.00),
    'EJ-TAP-CAN': ('Tapacanto PVC 22 mm', 'ML', 0.95),
    'EJ-BIS': ('Bisagra cierre lento', 'UND', 3.50),
    'EJ-COR': ('Corredera telescópica (par)', 'UND', 12.00),
    'EJ-TOR-450': ('Tornillo 4×50', 'UND', 0.05),
    'EJ-JAL': ('Jalador de aluminio', 'UND', 4.50),
    'EJ-SIL': ('Silicona transparente', 'UND', 14.00),
    'EJ-PIN': ('Pin de repisa', 'UND', None),
}

# tipología → [(producto, cantidad, etapa)]. A propósito: EJ-MEL-RH sin etapa
# en C01, EJ-TOR-450 en dos filas en C02 y 2.4375 planchas (cuatro decimales).
BOM = {
    'C01': [('EJ-MEL-BLA', 2.4375, 'Producción'), ('EJ-MEL-MAD', 1.0, 'Producción'),
            ('EJ-MEL-RH', 0.5, ''), ('EJ-TAP-CAN', 28, 'Producción'),
            ('EJ-BIS', 12, 'Armado'), ('EJ-COR', 3, 'Armado'),
            ('EJ-TOR-450', 80, 'Instalación'), ('EJ-JAL', 9, 'Instalación'),
            ('EJ-SIL', 1, 'Acabado y entrega')],
    'C02': [('EJ-MEL-BLA', 2.8, 'Producción'), ('EJ-MEL-MAD', 1.2, 'Producción'),
            ('EJ-MEL-RH', 0.5, 'Producción'), ('EJ-TAP-CAN', 34, 'Producción'),
            ('EJ-BIS', 14, 'Armado'), ('EJ-COR', 4, 'Armado'),
            ('EJ-TOR-450', 60, 'Instalación'), ('EJ-TOR-450', 40, 'Instalación'),
            ('EJ-JAL', 11, 'Instalación'), ('EJ-SIL', 1, 'Acabado y entrega')],
    'CL01': [('EJ-MEL-MAD', 3.5, 'Producción'), ('EJ-TAP-CAN', 30, 'Producción'),
             ('EJ-BIS', 6, 'Armado'), ('EJ-COR', 2, 'Armado'),
             ('EJ-PIN', 16, 'Instalación'), ('EJ-JAL', 6, 'Instalación')],
    'B01': [('EJ-MEL-RH', 0.9, 'Producción'), ('EJ-TAP-CAN', 8, 'Producción'),
            ('EJ-BIS', 2, 'Armado'), ('EJ-JAL', 2, 'Instalación'),
            ('EJ-SIL', 1, 'Acabado y entrega')],
}

FLOORS = ['Piso 01', 'Piso 02', 'Piso 03']
APARTMENTS_PER_FLOOR = 4
# Ambientes de cada departamento: los impares con la cocina C01, los pares con la C02.
SPACES = [('Cocina', ('C01', 'C02')), ('Closet dormitorio', ('CL01', 'CL01')),
          ('Baño', ('B01', 'B01'))]


def tree():
    """[(piso, departamento, ambiente, tipología)] de la obra de ejemplo."""
    rows = []
    for floor_index, floor in enumerate(FLOORS, start=1):
        for number in range(1, APARTMENTS_PER_FLOOR + 1):
            apartment = 'Dpto %d%02d' % (floor_index, number)
            for space, (odd, even) in SPACES:
                rows.append((floor, apartment, space, odd if number % 2 else even))
    return rows


# ETO de las cocinas del piso 01: anchos reales (difieren de la plantilla).
# El Dpto 105 no existe en la obra: lo avisa el asistente (a propósito).
ETO = {
    ('Piso 01', 'Dpto 101', 'Cocina'): [('MB01', 600), ('MB02', 750), ('MB03', 450),
                                        ('MA01', 600), ('MA02', 750), ('CAMPANA', 600)],
    ('Piso 01', 'Dpto 102', 'Cocina'): [('MB01', 600), ('MB02', 900), ('MB03', 450),
                                        ('MB04', 350), ('MA01', 600), ('MA02', 900),
                                        ('CAMPANA', 600)],
    ('Piso 01', 'Dpto 103', 'Cocina'): [('MB01', 550), ('MB02', 800), ('MB03', 450),
                                        ('MA01', 550), ('MA02', 800), ('CAMPANA', 600)],
    ('Piso 01', 'Dpto 104', 'Cocina'): [('MB01', 600), ('MB02', 950), ('MB03', 450),
                                        ('MB04', 400), ('MA01', 600), ('MA02', 950),
                                        ('CAMPANA', 600)],
    ('Piso 01', 'Dpto 105', 'Cocina'): [('MB01', 600)],
}

MASTER_README = [
    'Ejemplo: obra genérica de 3 pisos, 4 departamentos por piso y, en cada departamento, '
    'cocina, closet y baño (36 ambientes, 126 módulos). Datos ficticios con códigos EJ-.',
    'Para probarlo: en el planificador, Configuración › Importar maestro y ETO; elija una obra '
    'vacía, suba este libro, marque «Crear los productos que no existen» e importe. Después, en '
    'el plan de la obra, «Generar plan».',
    'La hoja CATALOGO crea las actividades de obra: la aplica un administrador del '
    'planificador. Sin ese permiso, cárguelas antes en Configuración › Actividades de obra.',
    'Advertencias que el ejemplo trae a propósito, para conocerlas:',
    '  - BOM de C01: la melamina hidrófuga (EJ-MEL-RH) no tiene etapa de consumo. Se importa, '
    'pero el plan no se aprueba hasta indicar su etapa en la BOM de la tipología.',
    '  - BOM de C02: el tornillo EJ-TOR-450 está en dos filas. Se suman (100 unidades).',
    '  - EJ-PIN (pin de repisa) no tiene costo: el planificador lo escribe con «Aplicar costo».',
    '  - BOM de C01: 2.4375 planchas de melamina blanca. Si la precisión de las cantidades de '
    'la base tiene menos de cuatro decimales, se redondea al guardar (se avisa).',
]
ETO_README = [
    'Ejemplo de ETO: código y ancho real de los módulos de las cocinas del piso 01 de la obra '
    'del maestro de ejemplo. Impórtelo después del maestro, en la misma obra.',
    'Con el ETO, al generar el plan la instalación y la limpieza por ML de esas cocinas se '
    'calculan con el ancho real de cada módulo, no con el de la plantilla.',
    'A propósito: la fila del Dpto 105 no existe en la obra y el asistente la avisa (se omite).',
]


def _layout():
    path = MODULE_DIR / 'wizards' / 'master_import_layout.py'
    spec = importlib.util.spec_from_file_location('master_import_layout', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def master_rows():
    catalog = [dict(code=c, name=n, stage=s, uom=u, measure=m, ml_group=g, price=p)
               for c, n, s, u, m, g, p in CATALOG]
    typologies = [dict(code=c, name=n, family=f) for c, n, f in TYPOLOGIES]
    modules = [dict(typology=t, sequence=i * 10, code=c, type=k, width=w, ml_group=g, activity=a)
               for t, rows in MODULES.items() for i, (c, k, w, g, a) in enumerate(rows, start=1)]
    activities = [dict(typology=t, activity=a, qty=q)
                  for t, rows in ACTIVITIES.items() for a, q in rows]
    bom = [dict(typology=t, product_code=p, product_name=PRODUCTS[p][0], qty=q,
                uom=PRODUCTS[p][1], stage=s, cost=PRODUCTS[p][2])
           for t, rows in BOM.items() for p, q, s in rows]
    arbol = [dict(floor=f, apartment=a, space=s, typology=t) for f, a, s, t in tree()]
    return {'CATALOGO': catalog, 'TIPOLOGIAS': typologies, 'MODULOS': modules,
            'ACTIVIDADES': activities, 'BOM': bom, 'ARBOL': arbol}


def eto_rows():
    types = {code: (kind, group) for rows in MODULES.values() for code, kind, _w, group, _a in rows}
    return {'ETO': [dict(floor=f, apartment=a, space=s, code=c, type=types[c][0], width=w,
                         ml_group=types[c][1])
                    for (f, a, s), rows in ETO.items() for c, w in rows]}


def build():
    layout = _layout()
    return (layout.build_workbook(master_rows(), MASTER_README),
            layout.build_workbook(eto_rows(), ETO_README))


def main():
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    master, eto = build()
    (EXAMPLES_DIR / MASTER_FILE).write_bytes(master)
    (EXAMPLES_DIR / ETO_FILE).write_bytes(eto)
    print('Generados', EXAMPLES_DIR / MASTER_FILE, 'y', EXAMPLES_DIR / ETO_FILE)


if __name__ == '__main__':
    main()
