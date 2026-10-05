# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged("post_install", "-at_install")
class TestAlPosProductView(TestPointOfSaleHttpCommon):
    """Cobertura end-to-end del conmutador cuadrícula/lista.

    Reutiliza `TestPointOfSaleHttpCommon` de Odoo, que prepara una config
    de TPV funcional, un cajero (`pos_user`) y un helper de apertura de
    sesión. El tour hace el trabajo pesado (ver el archivo JS del mismo
    nombre).
    """

    def test_al_pos_product_view_tour(self):
        # Asegura que el usuario parte sin preferencia guardada para que el
        # tour haga sus asserts contra un estado limpio.
        self.pos_user.pos_product_view_mode = False
        self.main_pos_config.default_product_view = "grid"

        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("al_pos_product_view_tour")

        # Tras el tour el cajero cambió de vista al menos una vez, así que
        # la ruta de persistencia debe haber escrito el valor de vuelta.
        self.assertIn(
            self.pos_user.pos_product_view_mode,
            ("grid", "list"),
            "El conmutador debe persistir la vista elegida en el registro de usuario del cajero.",
        )
