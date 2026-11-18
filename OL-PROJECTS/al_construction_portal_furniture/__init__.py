# -*- coding: utf-8 -*-
from . import controllers
from . import models


def post_init_hook(env):
    """Las cinco funciones nacen apagadas y se encienden solo en el perfil
    Mobiliario (paquete 1.22, etapa 2)."""
    env['construction.vertical.profile']._portal_furniture_enable_defaults()
