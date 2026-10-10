# -*- coding: utf-8 -*-
"""Valores compartidos del planificador (especificación v1.4, «Modelo de datos»)."""

# Niveles de la jerarquía de la obra en project.task (la obra es el proyecto).
LEVELS = [
    ('floor', 'Piso'),
    ('apartment', 'Departamento'),
    ('space', 'Ambiente'),
    ('module', 'Módulo'),
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
    ('other', 'Otro'),
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
