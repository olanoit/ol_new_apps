# -*- coding: utf-8 -*-
"""v1.8, M18-14: secuencia de etapas de mobiliario con sub etapas.

Las etapas padre «1 Producción» y «2 Instalación» y la sub etapa «2.3
Limpieza» las crea la carga de datos (registros nuevos). Aquí las cuatro
etapas de siempre pasan a ser sus sub etapas: Producción a 1.1 Producción de
piezas, Armado a 1.2, Instalación a 2.1 y Acabado y entrega a 2.2 Acabado.
Conservan su código, así que ninguna línea, avance ni etapa del cronograma
cambia de monto. Una etapa que el cliente ya puso bajo otra no se toca."""
import logging

from odoo import SUPERUSER_ID, Command, api

_logger = logging.getLogger(__name__)

REF = 'al_construction_planner.'
CHANGES = [
    ('stage_production', 'stage_group_production', '1.1', 'Producción de piezas',
     'Producción, Produccion'),
    ('stage_assembly', 'stage_group_production', '1.2', 'Armado', False),
    ('stage_installation', 'stage_group_installation', '2.1', 'Instalación', False),
    ('stage_finishing', 'stage_group_installation', '2.2', 'Acabado',
     'Acabado y entrega, Entrega'),
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    moved = []
    langs = [code for code, _name in env['res.lang'].get_installed()]
    for xmlid, parent_xmlid, number, name, aliases in CHANGES:
        stage = env.ref(REF + xmlid, raise_if_not_found=False)
        parent = env.ref(REF + parent_xmlid, raise_if_not_found=False)
        if not stage or not parent or stage.parent_id:
            continue
        vals = {'parent_id': parent.id, 'number': number}
        if aliases and not stage.alias_names:
            vals['alias_names'] = aliases
        stage.write(vals)
        # El nombre es traducible: el mismo en todos los idiomas instalados.
        for lang in set(langs) | {'en_US'}:
            stage.with_context(lang=lang).name = name
        moved.append(stage.code)
    if moved:
        # La etapa padre de las líneas se calculó al crear la columna, antes
        # de que las etapas tuvieran padre.
        env['construction.stage'].search([('code', 'in', moved)])._recompute_stage_parent()
    profile = env.ref(REF + 'profile_furniture', raise_if_not_found=False)
    if profile:
        extra = [env.ref(REF + xmlid, raise_if_not_found=False)
                 for xmlid in ('stage_group_production', 'stage_group_installation',
                               'stage_cleaning')]
        profile.stage_ids = [Command.link(stage.id) for stage in extra if stage]
    _logger.info('Planificador v1.8: etapas de mobiliario como sub etapas: %s',
                 ', '.join(moved) or '-')

