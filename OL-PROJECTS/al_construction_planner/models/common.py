# -*- coding: utf-8 -*-
"""Valores compartidos del planificador (especificación v1.4, «Modelo de datos»)."""

# Niveles de la jerarquía de la obra en project.task (la obra es el proyecto).
# Es la *función* del nivel; su nombre visible (Torre, Etapa, Sótano…) sale
# de la plantilla de niveles de la obra (v1.5, M15-01). «Agrupador» es todo
# agrupador por encima del que agrupa unidades (piso), y «Mueble» el nivel
# opcional entre el ambiente y el módulo (M15-03).
LEVELS = [
    ('group', 'Agrupador'),
    ('floor', 'Piso'),
    ('apartment', 'Departamento'),
    ('space', 'Ambiente'),
    ('furniture', 'Mueble'),
    ('module', 'Módulo'),
]

# Función de cada nivel de la plantilla (construction.level.template.line).
LEVEL_ROLES = [
    ('group', 'Agrupador'),
    ('unit', 'Unidad'),
    ('space', 'Ambiente'),
    ('furniture', 'Mueble'),
    ('module', 'Módulo'),
]

# Tipo de unidad (M15-02): casuística de las 29 obras vendidas.
UNIT_TYPES = [
    ('apartment', 'Departamento'),
    ('duplex_level', 'Nivel de dúplex'),
    ('duct', 'Ducto'),
    ('parking', 'Estacionamiento'),
    ('common_area', 'Área común'),
    ('storage', 'Depósito'),
    ('commercial', 'Local'),
    ('pilot', 'Piloto'),
]

# Etapas de ejecución: líneas del plan, actividades y consumo de la BOM.
STAGES = [
    ('production', 'Producción'),
    ('assembly', 'Armado'),
    ('installation', 'Instalación'),
    ('finishing', 'Acabado y entrega'),
]

RESOURCE_TYPES = [
    ('material', 'Material'),
    ('service', 'Servicio'),
    ('contract', 'Contrata'),
    ('labor', 'Personal propio'),
    ('production', 'Producción'),
]

MODULE_TYPES = [
    ('low', 'Bajo'),
    ('high', 'Alto'),
    ('drawer', 'Cajonera'),
    ('hood', 'Campana'),
    ('shelf', 'Repisero'),
    ('other', 'Otro'),
]

ML_GROUPS = [
    ('low', 'Mueble bajo'),
    ('high', 'Mueble alto'),
    ('none', 'Sin ML'),
]

UNIT_STATES = [
    ('planned', 'Planificado'),
    ('production', 'En producción'),
    ('produced', 'Producido'),
    ('on_site', 'En obra'),
    ('installed', 'Instalado'),
    ('delivered', 'Entregado'),
]

TYPOLOGY_FAMILIES = [
    ('kitchen', 'Cocina'),
    ('closet', 'Closet'),
    ('bathroom', 'Baño'),
    ('laundry', 'Lavandería'),
    ('duct', 'Ducto'),
    ('common', 'Área común'),
    ('special', 'Especial'),
    ('other', 'Otro'),
]

# Documento de donde sale cada nombre de una tipología (v1.5, M15-04): una
# misma tipología se llama distinto en la cotización, la orden o el ETO.
TYPOLOGY_ALIAS_SOURCES = [
    ('quote', 'Cotización'),
    ('client_order', 'Orden del cliente'),
    ('itemized', 'Itemizado'),
    ('projection', 'Proyección'),
    ('eto', 'ETO'),
    ('other', 'Otro'),
]

FURNITURE_GROUPS = [
    ('low', 'Bajo'),
    ('high', 'Alto'),
    ('other', 'Otro'),
]

# Variantes de una unidad o ambiente (M15-04): «Navarra 605 en Rovere»,
# «once departamentos sin verdulero», un metrado distinto.
UNIT_OVERRIDE_KINDS = [
    ('color', 'Color o acabado'),
    ('exclude', 'Excluir componente'),
    ('qty', 'Metrado distinto'),
]

# Control del saldo del plan en requerimientos de obra y OF (P-11, W-10).
EXCEED_STATES = [
    ('ok', 'En plan'),
    ('exceeded', 'Excede el plan'),
    ('approved', 'Exceso aprobado'),
]

# Días de la semana (valor = date.weekday()): inicio de semana, liquidación y
# pago de contratas (fases 5 y 6).
WEEKDAYS = [
    ('0', 'Lunes'),
    ('1', 'Martes'),
    ('2', 'Miércoles'),
    ('3', 'Jueves'),
    ('4', 'Viernes'),
    ('5', 'Sábado'),
    ('6', 'Domingo'),
]
# Orden del avance físico del módulo: el avance validado solo lo hace subir.
UNIT_STATE_RANK = {state: rank for rank, (state, _label) in enumerate(UNIT_STATES)}
# Líneas que pagan por driver: su avance pondera el de los nodos del árbol.
DRIVER_TYPES = ('contract', 'labor')

# Ruta del ingreso (fase 10): frecuencia de valorización y cobro del fondo de
# garantía de la obra (P-21).
VALUATION_UNITS = [
    ('week', 'Semanas'),
    ('dates', 'Fechas fijas'),
]
GUARANTEE_RELEASES = [
    ('close', 'Al cierre de la obra'),
    ('date', 'En una fecha fija'),
]
