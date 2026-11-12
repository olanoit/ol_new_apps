# -*- coding: utf-8 -*-
import copy

from odoo import api, models

# Menús por momento (requerimiento CREVAL v1.0, 4.3): con «Ejecución en
# Planificación de obra», el menú se ordena según planificar, ejecutar,
# controlar y cobrar. Los menús no cambian de padre en la base (sus XMLID y
# los accesos directos de otros clientes siguen igual): se recolocan al cargar
# el menú. Con el ajuste apagado se ve el menú de siempre.
FEATURE_EXEC_PLANNER = 'al_construction_planner.group_planner_feature_exec_planner'
# Carpetas nuevas: XMLID → (padre, secuencia).
P = 'al_construction_planner.'
MOMENT_FOLDERS = {
    P + 'menu_planner_planning': (P + 'menu_planner_root', 15),
    # Paquete 1.20, M120-01: Ejecución en cuatro secciones (Avance, Control
    # semanal, Personal propio y Cambios); Contratas con su personal.
    P + 'menu_planner_exec_control': (P + 'menu_planner_execution', 20),
    P + 'menu_planner_exec_staff': (P + 'menu_planner_execution', 30),
    P + 'menu_planner_contract_staff': (P + 'menu_planner_contracts', 90),
    # M120-02: Configuración en siete secciones.
    P + 'menu_planner_config_vertical': (P + 'menu_planner_config', 10),
    P + 'menu_planner_config_recipes': (P + 'menu_planner_config', 20),
    P + 'menu_planner_config_contracts': (P + 'menu_planner_config', 30),
    P + 'menu_planner_config_sheets': (P + 'menu_planner_config', 40),
    P + 'menu_planner_config_analytic': (P + 'menu_planner_config', 50),
    P + 'menu_planner_config_portal': (P + 'menu_planner_config', 60),
}


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        """Con el planificador instalado, la aplicación «Gantt» se oculta: su
        diagrama, los colores por estado y el cronograma de la obra están en
        «Planificación de obra ▸ Obras ▸ Cronograma» y «Configuración». Se oculta
        desde el código (no se archiva el menú): al desinstalar el
        planificador, el Gantt vuelve a aparecer solo."""
        res = super()._load_menus_blacklist()
        gantt_root = self.env.ref('al_project_gantt_backend.menu_gantt_root', raise_if_not_found=False)
        if gantt_root:
            res.append(gantt_root.id)
        return res

    @api.model
    def _construction_feature_menus(self):
        """[(menú, grupo de la función)] que se ocultan con su función del
        perfil apagada (paquete 1.20, M120-07). Cada puente suma los suyos. Se
        ocultan en el código y no con el campo «Grupos» del menú: los grupos de
        un menú se suman (basta uno), y la función no debe abrirle el menú a
        quien no tiene su rol."""
        return [('al_construction_planner.menu_planner_recipes',
                 'al_construction_planner.group_planner_feature_recipes')]

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug)
        IMD = self.env['ir.model.data']
        hidden = set()
        for menu_xmlid, group_xmlid in self._construction_feature_menus():
            menu_id = IMD._xmlid_to_res_id(menu_xmlid, raise_if_not_found=False)
            if menu_id in visible and not self.env.user.has_group(group_xmlid):
                hidden.add(menu_id)
        if not hidden:
            return visible
        # También lo que cuelga de un menú oculto.
        children = self.sudo().search([('id', 'child_of', list(hidden))]).ids
        return frozenset(visible) - set(children)

    @api.model
    def _construction_moment_moves(self):
        """[(menú, nuevo padre, secuencia)] del menú por momento. Cada puente
        suma los suyos."""
        p = 'al_construction_planner.'
        return [
            (p + 'menu_planner_plans', p + 'menu_planner_planning', 10),
            (p + 'menu_planner_lines', p + 'menu_planner_planning', 20),
            (p + 'menu_planner_plan_tree', p + 'menu_planner_planning', 30),
            (p + 'menu_planner_space_stages', p + 'menu_planner_planning', 40),
            # Paquete 1.20, M120-01: la barra en ocho menús. Abastecimiento y
            # Contratas suben a la barra; Ejecución queda con lo que pasa en obra.
            (p + 'menu_planner_supply', p + 'menu_planner_root', 30),
            (p + 'menu_planner_contracts', p + 'menu_planner_root', 35),
            (p + 'menu_planner_allocations', p + 'menu_planner_supply', 25),
            (p + 'menu_planner_progress', p + 'menu_planner_execution', 10),
            (p + 'menu_planner_changes', p + 'menu_planner_execution', 40),
            # M120-02: Configuración en siete secciones.
            (p + 'menu_planner_profiles', p + 'menu_planner_config_vertical', 10),
            (p + 'menu_planner_profile_import', p + 'menu_planner_config_vertical', 20),
            (p + 'menu_planner_level_templates', p + 'menu_planner_config_vertical', 30),
            (p + 'menu_planner_stages', p + 'menu_planner_config_vertical', 40),
            (p + 'menu_planner_resource_types', p + 'menu_planner_config_vertical', 50),
            (p + 'menu_planner_uom_aliases', p + 'menu_planner_config_vertical', 60),
            (p + 'menu_planner_recipes', p + 'menu_planner_config_recipes', 10),
            (p + 'menu_planner_activities', p + 'menu_planner_config_recipes', 20),
            (p + 'menu_planner_recipe_import', p + 'menu_planner_config_recipes', 30),
            (p + 'menu_planner_rates', p + 'menu_planner_config_contracts', 10),
            (p + 'menu_planner_analytic_rules', p + 'menu_planner_config_analytic', 10),
            (p + 'menu_planner_config_other', p + 'menu_planner_config', 70),
        ]

    @api.model
    def _construction_moment_hidden(self):
        """Menús que el menú por momento no muestra; su acción y su código
        quedan (paquete 1.20, M120-01: los reemplaza «Metrados (receta real)»)."""
        p = 'al_construction_planner.'
        return [p + 'menu_planner_measurements', p + 'menu_planner_measurement_lines',
                p + 'menu_planner_measurement_generate']

    @api.model
    def _construction_moment_names(self):
        """{menú: nombre} en el menú por momento."""
        return {}

    @api.model
    def _construction_moment_actions(self):
        """{menú: acción} que cambian con el menú por momento."""
        return {
            'al_construction_planner.menu_planner_sites':
                'al_construction_planner.action_construction_site_board',
            'al_construction_planner.menu_planner_tree':
                'al_construction_planner.action_construction_site_tasks',
        }

    @api.model
    def load_menus(self, debug):
        # El resultado de super() está en caché: se trabaja sobre una copia.
        menus = copy.deepcopy(super().load_menus(debug))
        # Paquete 1.20, M120-03: «Etapa actual por partida» (o por el nivel con
        # etapas de la plantilla de la compañía), con o sin menú por momento.
        report_id = self.env['ir.model.data']._xmlid_to_res_id(
            P + 'menu_planner_space_stage_report', raise_if_not_found=False)
        if report_id in menus:
            menus[report_id]['name'] = self.env['construction.level.labels.mixin']\
                ._construction_space_stage_title()
        if not self.env.user.has_group(FEATURE_EXEC_PLANNER):
            return menus
        self._construction_apply_moments(menus)
        return menus

    def _construction_apply_moments(self, menus):
        IMD = self.env['ir.model.data']

        def ref(xmlid):
            return IMD._xmlid_to_res_id(xmlid, raise_if_not_found=False)

        def detach(menu_id):
            for entry in menus.values():
                if menu_id in entry.get('children', []):
                    entry['children'].remove(menu_id)
                    return entry
            return None

        sequences = {}

        def place(menu_id, parent_id, sequence):
            sequences[menu_id] = sequence
            children = menus[parent_id]['children']
            children.append(menu_id)
            known = self.sudo().browse(children).read(['sequence'])
            order = {row['id']: sequences.get(row['id'], row['sequence']) for row in known}
            children.sort(key=lambda mid: (order.get(mid, 0), mid))

        def set_app(menu_id, app_id):
            entry = menus.get(menu_id)
            if entry is None:
                return
            entry['app_id'] = app_id
            for child in entry.get('children', []):
                set_app(child, app_id)

        # Lo que el menú por momento ya no muestra (M120-01).
        for xmlid in self._construction_moment_hidden():
            menu_id = ref(xmlid)
            if menu_id in menus:
                detach(menu_id)
                menus.pop(menu_id, None)
        moves = [(ref(child), ref(parent), sequence)
                 for child, parent, sequence in self._construction_moment_moves()]
        moves = [(child, parent, seq) for child, parent, seq in moves if child in menus and parent]
        if not moves:
            return
        # Carpetas nuevas (sin hijos en la base): se arman aquí.
        for xmlid, (parent_xmlid, sequence) in MOMENT_FOLDERS.items():
            folder_id, parent_id = ref(xmlid), ref(parent_xmlid)
            if not folder_id or folder_id in menus or parent_id not in menus:
                continue
            if not any(parent == folder_id for _child, parent, _seq in moves):
                continue
            folder = self.sudo().browse(folder_id)
            # La carpeta respeta sus grupos (Planificación con el eje plan).
            if folder.group_ids and not (folder.group_ids & self.env.user.all_group_ids):
                continue
            menus[folder_id] = {
                'id': folder_id, 'name': folder.with_context(lang=self.env.lang).name,
                'app_id': menus[parent_id]['app_id'], 'action_model': False,
                'action_id': False, 'action_path': False, 'web_icon': False,
                'web_icon_data': False, 'web_icon_data_mimetype': False, 'xmlid': xmlid,
                'children': [],
            }
            place(folder_id, parent_id, sequence)
        sources = []
        for child, parent, sequence in moves:
            if parent not in menus:
                continue
            source = detach(child)
            if source:
                sources.append(source['id'])
            place(child, parent, sequence)
            set_app(child, menus[parent]['app_id'])
        # Las carpetas que quedaron vacías se quitan.
        for source_id in sources:
            entry = menus.get(source_id)
            if entry and not entry['children'] and not entry.get('action_id'):
                detach(source_id)
                menus.pop(source_id, None)
        for menu_xmlid, name in self._construction_moment_names().items():
            menu_id = ref(menu_xmlid)
            if menu_id in menus:
                menus[menu_id]['name'] = name
        # Las acciones de la vertical: el tablero y la tarea de obra.
        for menu_xmlid, action_xmlid in self._construction_moment_actions().items():
            menu_id = ref(menu_xmlid)
            action = self.env.ref(action_xmlid, raise_if_not_found=False)
            if menu_id in menus and action:
                menus[menu_id].update(action_model=action._name, action_id=action.id,
                                      action_path=action.sudo().path or False)
