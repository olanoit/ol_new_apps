# -*- coding: utf-8 -*-
from odoo import api, models

# Etiquetas del resumen de inventario que Odoo deja en inglés en español
# (stock no las traduce en es/es_419). mrp y repair agregan las suyas a la
# misma tarjeta; las que ya vienen traducidas no pasan por aquí.
OVERVIEW_LABELS_ES = {
    'Late': 'Con demora',
    'Waiting': 'En espera',
    'Back Orders': 'Órdenes parciales',
    'Operations': 'Movimientos',
    'To Receive': 'Por recibir',
    'To Deliver': 'Por entregar',
    'To Process': 'Por procesar',
    'To Manufacture': 'Por fabricar',
    'In Progress': 'En progreso',
    'To Close': 'Por cerrar',
    'To Repair': 'Por reparar',
    'Confirmed': 'Confirmadas',
    'Under Repair': 'En reparación',
    # mrp traduce el botón «Open» como adjetivo; en el resto de tarjetas es «Abrir».
    'Abierto': 'Abrir',
}


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type='form', **options):
        # La vista depende del estilo del usuario y de la compañía (M111-19 A).
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + (self.env.user._al_stock_overview_options(),)

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Resumen de inventario en español y, en el estilo «Compacta», sin
        gráficos (salvo que la compañía los muestre) y con el ancho elegido.

        Se hace aquí y no con xpath porque stock, mrp y repair ponen cada uno
        su gráfico en la tarjeta (un xpath solo alcanza el primero) y porque
        las etiquetas sin traducir están en las vistas de esos módulos.
        """
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type != 'kanban' or arch.get('js_class') != 'stock_dashboard_kanban':
            return arch, view
        style, graph, width = self.env.user._al_stock_overview_options()
        if style == 'compact':
            arch.set('class', ' '.join(filter(None, [
                arch.get('class'), 'o_al_overview_compact', 'o_al_overview_w_%s' % width])))
            if not graph:
                for node in arch.xpath("//templates//field[@name='kanban_dashboard_graph']"):
                    node.getparent().remove(node)
                # El renderer de stock (stock_dashboard_kanban) lee el campo de
                # cada registro: se carga, pero fuera de la tarjeta y sin widget.
                if not arch.xpath("./field[@name='kanban_dashboard_graph']"):
                    arch.insert(0, arch.makeelement('field', {'name': 'kanban_dashboard_graph'}))
        if (self.env.lang or '').startswith('es'):
            for node in arch.iter():
                for attr in ('text', 'tail'):
                    value = getattr(node, attr)
                    label = value and value.strip()
                    if label in OVERVIEW_LABELS_ES:
                        setattr(node, attr, value.replace(label, OVERVIEW_LABELS_ES[label]))
        return arch, view
