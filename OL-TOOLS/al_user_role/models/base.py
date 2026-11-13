# -*- coding: utf-8 -*-
from odoo import api, models

# Atributos de fields_get que usan el filtro personalizado (searchable),
# Agrupar por (groupable), el orden de las columnas (sortable) y el diálogo
# de Exportar (exportable).
HIDDEN_FIELD_ATTRS = ('searchable', 'sortable', 'groupable', 'exportable')


class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Campos ocultos por rol: fuera de filtros y agrupaciones
        personalizados y de Exportar.

        Ocultarlos en la vista no basta: el usuario podría filtrar, agrupar o
        exportar por ellos. Siguen en la descripción (las vistas los usan como
        invisibles), solo se marcan como no buscables ni exportables.
        """
        res = super().fields_get(allfields, attributes)
        if self.env.su or 'al.user.role' not in self.env:
            return res
        restrictions = self.env['al.user.role']._al_ui_restrictions()
        spec = restrictions['models'].get(self._name) if restrictions else None
        hidden = spec['hidden_fields'] & res.keys() if spec else ()
        for fname in hidden:
            description = res[fname]
            for attr in HIDDEN_FIELD_ATTRS:
                if attributes is None or attr in attributes:
                    description[attr] = False
        return res
