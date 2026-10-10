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
