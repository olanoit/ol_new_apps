# -*- coding: utf-8 -*-

from . import models
from . import wizards


def post_init_hook(env):
    """Deja configuradas las cuentas de letras del PCGE (1232, 1233, 1234 y 423)."""
    env['l10n_pe.letter.account.config']._l10n_pe_create_default_configs()
