from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # --- Exposición de datos al frontend -----------------------------------
    @api.model
    def _load_pos_data_fields(self, config_id):
        # `qty_available` es un compute no almacenado (de `stock`, siempre
        # instalado transitivamente vía `point_of_sale -> stock_account`).
        # Cargarlo de forma anticipada permite que la vista de lista muestre
        # el stock por fila sin un round-trip por producto; el dominio de
        # búsqueda/carga limitada del TPV base ya acota cuántos productos
        # se computan a la vez.
        return super()._load_pos_data_fields(config_id) + ["qty_available"]

    @api.model
    def _load_pos_data_read(self, records, config):
        # Stock del almacén del TPV (el de su tipo de operación), no la suma
        # de todos los almacenes de la compañía.
        warehouse = config.picking_type_id.warehouse_id
        if warehouse:
            records = records.with_context(warehouse_id=warehouse.id)
        return super()._load_pos_data_read(records, config)
