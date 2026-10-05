from . import controllers
from . import models


def _bump_pos_data_change(env):
    """Fuerza a todas las cajas a descartar su caché IndexedDB.

    El PdV 19 sólo recarga todo desde cero cuando cambia
    `pos.config.last_data_change`; al instalar/desinstalar el tema cambia la
    forma del payload de `pos.config` (campos nuevos / quitados).
    """
    env["pos.config"].search([])._compute_local_data_integrity()


def post_init_hook(env):
    _bump_pos_data_change(env)


def uninstall_hook(env):
    _bump_pos_data_change(env)
