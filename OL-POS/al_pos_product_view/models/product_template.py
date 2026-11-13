from odoo import api, models
from odoo.fields import Domain


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # --- Ámbito del stock de la caja -----------------------------------------
    @api.model
    def _alpv_stock_context(self, config):
        """Contexto de stock de la caja: la ubicación de origen de su tipo de
        operación (de donde realmente vende) y, si no tiene, su almacén.

        Lo comparten la carga inicial, el stock en vivo de las filas y
        tarjetas y el filtro de stock del catálogo, para que las tres cifras
        hablen de lo mismo.
        """
        location = config.picking_type_id.default_location_src_id
        if location:
            return {"location": location.id}
        warehouse = config.picking_type_id.warehouse_id
        if warehouse:
            return {"warehouse_id": warehouse.id}
        return {}

    # --- Exposición de datos al frontend -----------------------------------
    @api.model
    def _load_pos_data_fields(self, config_id):
        # `qty_available` es un compute no almacenado (de `stock`, siempre
        # instalado transitivamente vía `point_of_sale -> stock_account`).
        # Cargarlo de forma anticipada da a filas y tarjetas una cifra que
        # pintar antes de que llegue el stock en vivo (`get_pos_location_stock`).
        return super()._load_pos_data_fields(config_id) + ["qty_available"]

    @api.model
    def _load_pos_data_read(self, records, config):
        # Stock de la caja (su ubicación de origen o su almacén), no la suma
        # de todos los almacenes de la compañía.
        context = self._alpv_stock_context(config)
        if context:
            records = records.with_context(**context)
        return super()._load_pos_data_read(records, config)

    # --- Llamadas desde el TPV -----------------------------------------------
    @api.model
    def get_pos_location_stock(self, product_tmpl_ids, pos_config_id):
        """Stock actual de `product_tmpl_ids` en la caja.

        El `qty_available` cargado al abrir la sesión es una foto: el TPV no
        lo vuelve a pedir. El catálogo llama a este método cada vez que
        cambia lo que se ve (búsqueda, categoría, vista) y al añadir un
        producto, para que el badge de stock no quede desfasado por las
        ventas de otras cajas.

        Devuelve ``{"location_name": str|False, "stock": {id: cantidad}}``.
        """
        config = self.env["pos.config"].browse(pos_config_id)
        context = self._alpv_stock_context(config)
        templates = self.browse(product_tmpl_ids).exists().with_context(**context)
        location = config.picking_type_id.default_location_src_id
        name = location.display_name if location else config.picking_type_id.warehouse_id.display_name
        return {
            "location_name": name or False,
            "stock": {template.id: template.qty_available for template in templates},
        }

    @api.model
    def get_pos_in_stock_template_ids(self, pos_config_id):
        """Ids de los productos almacenables de la caja con stock, para el
        filtro de stock del catálogo. Se resuelve en el servidor porque el
        TPV no carga todo el catálogo (`limited_product_count`).
        """
        config = self.env["pos.config"].browse(pos_config_id)
        templates = self.with_context(**self._alpv_stock_context(config))
        return templates.search(
            Domain(self._load_pos_data_domain({}, config))
            & Domain("is_storable", "=", True)
            & Domain("qty_available", ">", 0),
            order="id",
        ).ids

    @api.model
    def get_pos_tag_template_ids(self, tag_ids, pos_config_id):
        """Ids de los productos de la caja con alguna de las etiquetas.

        El filtro por etiquetas trabaja sobre lo cargado en el navegador;
        con esto el TPV trae también los productos de esas etiquetas que aún
        no había cargado.
        """
        config = self.env["pos.config"].browse(pos_config_id)
        return self.search(
            Domain(self._load_pos_data_domain({}, config))
            & Domain("product_tag_ids", "in", tag_ids),
            order="id",
        ).ids
