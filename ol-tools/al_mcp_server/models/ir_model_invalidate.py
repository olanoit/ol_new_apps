"""
Ganchos de invalidación de la caché de esquema MCP.

Cuando se crean, modifican o eliminan registros de ir.model o ir.model.fields
(p. ej., al instalar/actualizar un módulo o añadir un campo personalizado con
Studio), hay que vaciar la caché de esquema para que la siguiente solicitud MCP
refleje el estado actual.

La invalidación total (vaciar todo) es intencionada: una invalidación parcial
exigiría registrar las dependencias por modelo en la clave de caché, y los
cambios de modelos/campos son poco frecuentes frente a la ventaja de no servir
datos de esquema obsoletos.
"""

import logging

from odoo import api, models

from ..services import schema_cache

_logger = logging.getLogger(__name__)


def _invalidate_all(label: str) -> None:
    count = schema_cache.invalidate()
    if count:
        _logger.debug("Caché de esquema MCP: %d entradas vaciadas tras %s", count, label)


class IrModelInvalidate(models.Model):
    _inherit = "ir.model"

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        _invalidate_all("ir.model create")
        return result

    def write(self, vals):
        result = super().write(vals)
        _invalidate_all("ir.model write")
        return result

    def unlink(self):
        result = super().unlink()
        _invalidate_all("ir.model unlink")
        return result


class IrModelFieldsInvalidate(models.Model):
    _inherit = "ir.model.fields"

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        _invalidate_all("ir.model.fields create")
        return result

    def write(self, vals):
        result = super().write(vals)
        _invalidate_all("ir.model.fields write")
        return result

    def unlink(self):
        result = super().unlink()
        _invalidate_all("ir.model.fields unlink")
        return result
