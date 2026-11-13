# -*- coding: utf-8 -*-
from odoo import models

# Vistas donde se bloquean crear / editar / borrar / duplicar.
EDITABLE_VIEW_TAGS = ('form', 'list', 'kanban')


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    def _postprocess_access_rights(self, tree):
        """Aplica las restricciones de interfaz de los roles del usuario.

        Corre por usuario y fuera de la caché de vistas (la vista en caché es
        la misma para todos). Cada vista y subvista (p. ej. la lista de un
        one2many) recibe las restricciones de *su* modelo.
        """
        restrictions = (
            {} if self.env.su else self.env['al.user.role']._al_ui_restrictions()
        )
        if not restrictions:
            return super()._postprocess_access_rights(tree)
        # Antes de super: super quita el atributo model_access_rights.
        marked = [(node, node.get('model_access_rights'))
                  for node in tree.xpath('//*[@model_access_rights]')]
        tree = super()._postprocess_access_rights(tree)
        marked_views = {node for node, _model in marked if node.tag != 'field'}
        for node, model in marked:
            if node.tag == 'field':
                self._al_restrict_relational_field(node, model, restrictions)
            else:
                self._al_restrict_view(node, model, restrictions, marked_views)
        return tree

    def _al_restrict_relational_field(self, node, model, restrictions):
        """many2one / many2many hacia un modelo restringido: sin Crear."""
        spec = restrictions['models'].get(model, {})
        if restrictions['readonly_all'] or spec.get('is_readonly'):
            node.set('can_create', 'False')
            node.set('can_write', 'False')
        elif spec.get('hide_create'):
            node.set('can_create', 'False')

    def _al_restrict_view(self, root, model, restrictions, marked_views):
        spec = restrictions['models'].get(model, {})
        readonly = restrictions['readonly_all'] or spec.get('is_readonly')
        if root.tag in EDITABLE_VIEW_TAGS:
            for attr, active in (
                ('create', readonly or spec.get('hide_create')),
                ('edit', readonly),
                ('delete', readonly or spec.get('hide_delete')),
                ('duplicate', readonly or spec.get('hide_duplicate')),
            ):
                if active:
                    root.set(attr, 'False')
        if root.tag == 'list' and spec.get('hide_export'):
            root.set('export_xlsx', 'False')

        nodes = list(self._al_own_nodes(root, marked_views))
        if root.tag == 'form' and restrictions['hide_chatter']:
            for node in nodes:
                if node.tag == 'chatter' or 'oe_chatter' in (node.get('class') or '').split():
                    node.getparent().remove(node)
        if not spec:
            return
        # En una lista se oculta la columna completa; ``invisible`` cubre además
        # los botones del encabezado (<header>), que no son columnas.
        hide_attrs = ('invisible', 'column_invisible') if root.tag == 'list' else ('invisible',)
        for node in nodes:
            name = node.get('name')
            if node.tag == 'field':
                if name in spec['hidden_fields']:
                    for attr in hide_attrs:
                        node.set(attr, 'True')
                if name in spec['readonly_fields']:
                    node.set('readonly', 'True')
                if name in spec['required_fields']:
                    node.set('required', 'True')
                if name in spec['no_open_fields']:
                    options = (node.get('options') or '').strip()
                    inner = options[1:-1].strip() if options.startswith('{') else ''
                    node.set('options', '{%s%s}' % (inner + ', ' if inner else '', "'no_open': True"))
            elif node.tag == 'label' and node.get('for') in spec['hidden_fields']:
                node.set('invisible', 'True')
            elif node.tag == 'button' and name in spec['buttons']:
                for attr in hide_attrs:
                    node.set(attr, 'True')
            elif node.tag == 'page' and name in spec['pages']:
                node.set('invisible', 'True')
            elif node.tag == 'filter' and name in spec['filters']:
                node.set('invisible', 'True')

    def _al_own_nodes(self, root, marked_views):
        """Nodos de ``root`` sin entrar en subvistas (que son de otro modelo)."""
        stack = list(root)
        while stack:
            node = stack.pop()
            if not isinstance(node.tag, str):  # comentarios
                continue
            if node in marked_views:
                continue
            yield node
            stack.extend(node)
