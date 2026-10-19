# -*- coding: utf-8 -*-


def post_init_hook(env):
    """Paquete 1.10, M110-01: el armado de mobiliario propone sus accesorios
    desde la orden, como en el paquete 1.9."""
    env['construction.stage']._construction_mark_assembly_accessories()
