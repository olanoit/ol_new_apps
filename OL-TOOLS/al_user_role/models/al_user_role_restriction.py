# -*- coding: utf-8 -*-
from lxml import etree

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval

# Tipos de vista donde se buscan botones, pestañas y filtros.
ELEMENT_VIEW_TYPES = ('form', 'list', 'kanban', 'search')
# Elemento de vista -> (etiqueta XML, xpath). Solo los que tienen ``name``:
# la etiqueta visible (``string``) se traduce y no sirve para identificarlos.
ELEMENT_XPATHS = {
    'button': '//button[@name]',
    'page': '//page[@name]',
    'filter': '//filter[@name]',
}


class AlUserRoleViewElement(models.Model):
    """Botón, pestaña o filtro de las vistas de un modelo, para ocultarlo por rol.

    Se llenan al elegir el modelo en una restricción (``_al_sync``), leyendo
    las vistas de ese modelo; se identifican por su nombre técnico.
    """
    _name = 'al.user.role.view.element'
    _description = 'Elemento de vista ocultable por rol'
    _order = 'model_id, kind, label, name, id'
    _rec_names_search = ['label', 'technical_name']

    model_id = fields.Many2one(
        'ir.model', string='Modelo', required=True, ondelete='cascade', index=True,
    )
    kind = fields.Selection(
        [('button', 'Botón'), ('page', 'Pestaña'), ('filter', 'Filtro / agrupar por')],
        string='Tipo', required=True,
    )
    name = fields.Char(string='Nombre en la vista', required=True)
    technical_name = fields.Char(
        string='Nombre técnico', compute='_compute_technical_name', store=True,
        help='El nombre en la vista; en un botón que abre una acción, el XML ID de '
             'esa acción (en la vista su nombre es el id numérico).',
    )
    label = fields.Char(string='Etiqueta')

    _model_kind_name_uniq = models.Constraint(
        'unique(model_id, kind, name)',
        'El elemento ya está registrado para este modelo.',
    )

    @api.depends('kind', 'name')
    def _compute_technical_name(self):
        numeric = self.filtered(lambda e: e.kind == 'button' and (e.name or '').isdigit())
        xmlid_by_id = {}
        # sudo: solo se leen los XML ID de acciones. El XML ID está registrado
        # con el modelo concreto (p. ej. ir.actions.act_window), no con
        # ir.actions.actions: se busca por el tipo de cada acción.
        actions_sudo = self.env['ir.actions.actions'].sudo().browse(
            [int(e.name) for e in numeric]).exists()
        for action_type in set(actions_sudo.mapped('type')):
            typed = actions_sudo.filtered(lambda a: a.type == action_type)
            if action_type in self.env:
                typed_sudo = self.env[action_type].sudo().browse(typed.ids)
                xmlid_by_id.update(typed_sudo.get_external_id())
        for element in self:
            element.technical_name = (
                xmlid_by_id.get(int(element.name)) if element in numeric else None
            ) or element.name

    @api.depends('label', 'name', 'technical_name')
    @api.depends_context('al_element_label_only')
    def _compute_display_name(self):
        """"Etiqueta (nombre técnico)" para los selectores de Restricciones.

        Con ``al_element_label_only`` (pantallas del propio elemento, donde
        el nombre técnico tiene su columna) solo la etiqueta.
        """
        label_only = self.env.context.get('al_element_label_only')
        for element in self:
            technical = element.technical_name or element.name or ''
            # Sin string/title la etiqueta es el nombre en la vista (en un
            # botón de acción, su id numérico): se muestra solo el técnico.
            label = element.label if element.label and element.label != element.name else technical
            element.display_name = (
                label if label_only or label == technical else f'{label} ({technical})'
            )

    def action_al_resync(self):
        """Vuelve a leer las vistas de los modelos de los elementos elegidos."""
        self._al_sync(self.model_id)

    @api.model
    def _al_sync(self, ir_models):
        """Registra los botones, pestañas y filtros de las vistas de ``ir_models``.

        Lee el arch de todas las vistas del modelo (también las heredadas). No
        borra elementos: una restricción puede seguir apuntando a uno que ya no
        está en las vistas, y entonces simplemente no oculta nada.
        """
        # sudo: registro técnico; lo llama la pantalla de restricciones.
        self_sudo = self.sudo()
        for ir_model in ir_models:
            existing = {
                (e.kind, e.name)
                for e in self_sudo.search([('model_id', '=', ir_model.id)])
            }
            views_sudo = self.env['ir.ui.view'].sudo().search([
                ('model', '=', ir_model.model), ('type', 'in', ELEMENT_VIEW_TYPES),
            ])
            to_create = {}
            for view in views_sudo:
                try:
                    arch = etree.fromstring(view.arch)
                except (etree.XMLSyntaxError, ValueError):
                    continue
                for kind, xpath in ELEMENT_XPATHS.items():
                    for node in arch.xpath(xpath):
                        key = (kind, node.get('name'))
                        if key in existing or key in to_create:
                            continue
                        to_create[key] = node.get('string') or node.get('title') or node.get('name')
            if to_create:
                self_sudo.create([
                    {'model_id': ir_model.id, 'kind': kind, 'name': name, 'label': label}
                    for (kind, name), label in to_create.items()
                ])


class AlUserRoleRestriction(models.Model):
    """Restricciones de interfaz y de registros de un rol sobre un modelo.

    Salvo el dominio, son visuales: ocultan o bloquean elementos de las
    vistas, pero no cambian los permisos de acceso (eso lo dan los grupos).
    Con varios roles, una restricción aplica solo si todos los roles del
    usuario la tienen.
    """
    _name = 'al.user.role.restriction'
    _description = 'Restricción de rol por modelo'
    _order = 'role_id, model_id, id'

    role_id = fields.Many2one(
        'al.user.role', string='Rol', required=True, ondelete='cascade', index=True,
    )
    model_id = fields.Many2one(
        'ir.model', string='Modelo', required=True, ondelete='cascade', index=True,
        domain=[('transient', '=', False)],
        help='Modelo al que se aplican las restricciones (p. ej. Contacto, Orden de venta).',
    )
    model = fields.Char(related='model_id.model', string='Modelo técnico')

    # Acciones sobre el modelo
    is_readonly = fields.Boolean(
        string='Solo lectura',
        help='No se puede crear, editar, borrar ni archivar: ni desde las vistas ni por otros '
             'caminos (botones, importación, API). Tampoco registrar notas en el chatter.',
    )
    hide_create = fields.Boolean(
        string='Ocultar crear',
        help='Oculta Nuevo y la opción Crear en los campos que apuntan a este modelo.',
    )
    hide_delete = fields.Boolean(string='Ocultar borrar', help='Oculta la acción Eliminar.')
    hide_duplicate = fields.Boolean(string='Ocultar duplicar', help='Oculta la acción Duplicar.')
    hide_archive = fields.Boolean(
        string='Ocultar archivar', help='Oculta Archivar / Desarchivar en lista y formulario.',
    )
    hide_export = fields.Boolean(string='Ocultar exportar', help='Oculta Exportar en la lista.')

    # Campos
    hidden_field_ids = fields.Many2many(
        'ir.model.fields', 'al_role_restriction_hidden_field_rel', 'restriction_id', 'field_id',
        string='Campos ocultos', domain="[('model_id', '=', model_id)]",
        help='Campos que no se muestran en las vistas del modelo, ni en los filtros y '
             'agrupaciones personalizados, ni en Exportar.',
    )
    readonly_field_ids = fields.Many2many(
        'ir.model.fields', 'al_role_restriction_readonly_field_rel', 'restriction_id', 'field_id',
        string='Campos de solo lectura', domain="[('model_id', '=', model_id)]",
        help='Campos que se ven pero no se pueden editar.',
    )
    required_field_ids = fields.Many2many(
        'ir.model.fields', 'al_role_restriction_required_field_rel', 'restriction_id', 'field_id',
        string='Campos obligatorios', domain="[('model_id', '=', model_id)]",
        help='Campos que el usuario debe completar al guardar.',
    )
    no_open_field_ids = fields.Many2many(
        'ir.model.fields', 'al_role_restriction_no_open_field_rel', 'restriction_id', 'field_id',
        string='Campos sin enlace', domain="[('model_id', '=', model_id), ('ttype', '=', 'many2one')]",
        help='Campos relacionados (many2one) que no muestran el enlace para abrir el registro.',
    )

    # Elementos de vista
    hidden_button_ids = fields.Many2many(
        'al.user.role.view.element', 'al_role_restriction_button_rel', 'restriction_id', 'element_id',
        string='Botones ocultos', domain="[('model_id', '=', model_id), ('kind', '=', 'button')]",
        help='Botones de las vistas del modelo que no se muestran.',
    )
    hidden_page_ids = fields.Many2many(
        'al.user.role.view.element', 'al_role_restriction_page_rel', 'restriction_id', 'element_id',
        string='Pestañas ocultas', domain="[('model_id', '=', model_id), ('kind', '=', 'page')]",
        help='Pestañas del formulario que no se muestran.',
    )
    hidden_filter_ids = fields.Many2many(
        'al.user.role.view.element', 'al_role_restriction_filter_rel', 'restriction_id', 'element_id',
        string='Filtros ocultos', domain="[('model_id', '=', model_id), ('kind', '=', 'filter')]",
        help='Filtros y agrupaciones de la búsqueda que no se muestran.',
    )

    # Acciones del menú Imprimir / Acciones
    hidden_report_ids = fields.Many2many(
        'ir.actions.report', 'al_role_restriction_report_rel', 'restriction_id', 'report_id',
        string='Informes ocultos', domain="[('model', '=', model)]",
        help='Informes que no aparecen en el menú Imprimir.',
    )
    hidden_server_action_ids = fields.Many2many(
        'ir.actions.server', 'al_role_restriction_server_action_rel', 'restriction_id', 'action_id',
        string='Acciones ocultas', domain="[('binding_model_id', '=', model_id)]",
        help='Acciones de servidor que no aparecen en el menú Acciones.',
    )

    # Registros
    domain = fields.Char(
        string='Dominio de registros',
        help='El usuario solo ve y modifica los registros que cumplen este dominio, '
             'además de sus reglas de registro. Esto sí es seguridad, no solo visual. '
             'Puede usar user (usuario), company_id y company_ids. Vacío: sin límite.',
    )

    _role_model_uniq = models.Constraint(
        'unique(role_id, model_id)',
        'El rol ya tiene restricciones para este modelo: edite la línea existente.',
    )

    @api.depends('model_id')
    def _compute_display_name(self):
        for restriction in self:
            restriction.display_name = restriction.model_id.name or ''

    @api.onchange('model_id')
    def _onchange_model_id(self):
        """Limpia lo elegido del modelo anterior y registra los elementos del nuevo."""
        if self.model_id:
            self.env['al.user.role.view.element']._al_sync(self.model_id)
        for name in ('hidden_field_ids', 'readonly_field_ids', 'required_field_ids',
                     'no_open_field_ids', 'hidden_button_ids', 'hidden_page_ids',
                     'hidden_filter_ids'):
            self[name] = self[name].filtered(lambda r: r.model_id == self.model_id)
        self.hidden_report_ids = self.hidden_report_ids.filtered(
            lambda r: r.model == self.model_id.model)
        self.hidden_server_action_ids = self.hidden_server_action_ids.filtered(
            lambda r: r.binding_model_id == self.model_id)

    @api.constrains('model_id', 'hidden_field_ids', 'readonly_field_ids', 'required_field_ids',
                    'no_open_field_ids', 'hidden_button_ids', 'hidden_page_ids', 'hidden_filter_ids')
    def _check_same_model(self):
        for restriction in self:
            records = (
                restriction.hidden_field_ids | restriction.readonly_field_ids
                | restriction.required_field_ids | restriction.no_open_field_ids
            ).model_id | (
                restriction.hidden_button_ids | restriction.hidden_page_ids
                | restriction.hidden_filter_ids
            ).model_id
            if records - restriction.model_id:
                raise ValidationError(self.env._(
                    'Rol "%(role)s": los campos y elementos de vista deben ser del modelo %(model)s.',
                    role=restriction.role_id.name, model=restriction.model_id.name,
                ))

    @api.constrains('domain', 'model_id')
    def _check_domain(self):
        for restriction in self.filtered('domain'):
            try:
                restriction._al_eval_domain(self.env['ir.rule']._eval_context())
            except Exception as e:  # noqa: BLE001 - se informa cualquier error del dominio
                raise ValidationError(self.env._(
                    'Rol "%(role)s", modelo %(model)s: el dominio no es válido (%(error)s).',
                    role=restriction.role_id.name, model=restriction.model_id.name, error=e,
                )) from e

    def _al_eval_domain(self, eval_context):
        self.ensure_one()
        domain = Domain(safe_eval(self.domain, eval_context))
        # Valida los nombres de campo contra el modelo.
        domain.validate(self.env[self.model_id.model])
        return domain

    def action_al_sync_elements(self):
        """Vuelve a leer las vistas (p. ej. tras instalar un módulo)."""
        self.env['al.user.role.view.element']._al_sync(self.model_id)

    @api.model_create_multi
    def create(self, vals_list):
        restrictions = super().create(vals_list)
        self.env.registry.clear_cache()
        return restrictions

    def write(self, vals):
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res
