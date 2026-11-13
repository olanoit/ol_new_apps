# -*- coding: utf-8 -*-
{
    'name': 'Roles de usuario (AL)',
    'summary': 'Administra los permisos y menús de los usuarios por roles (perfiles) con vigencia, compañía e historial',
    'description': """
        Roles (perfiles) de usuario, en Ajustes > Usuarios y compañías > Roles de
        usuario. Un rol agrupa grupos de seguridad; los grupos de cada usuario se
        calculan desde sus roles habilitados.

        Cada rol puede asignarse con vigencia (desde / hasta) y limitado a una
        compañía. Las altas, cambios y bajas de roles quedan en un historial.

        Cada rol puede ocultar menús: un menú se oculta a un usuario si todos
        sus roles lo ocultan (el Administrador del sistema ve todos).

        Cada rol puede además restringir la interfaz por modelo (campos ocultos,
        de solo lectura u obligatorios; botones, pestañas, filtros, informes y
        acciones ocultos; sin crear, borrar, duplicar, archivar ni exportar),
        limitar los registros con un dominio y bloquear el modo desarrollador,
        el chatter o todo el sistema en solo lectura. Con varios roles, una
        restricción aplica solo si todos la tienen.

        Asistentes: crear un rol desde un usuario o desde grupos, y agregar
        varios usuarios a un rol.

        Basado en los módulos OCA base_user_role, base_user_role_company y
        base_user_role_history (LGPL-3), en hide_menu_user (Cybrosys) para los
        menús ocultos y en access_roles (Cybrosys) para las restricciones, sin
        depender de ellos.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-TOOLS/Apps',
    # Amplía Ajustes ▸ Usuarios y compañías: usa el ícono nativo de Ajustes.
    'icon': '/base/static/description/settings.png',
    'version': '1.20261113',
    # LGPL-3: adapta código de base_user_role* (OCA, LGPL-3), ver scripts/areas.py.
    'license': 'LGPL-3',
    # web: se hereda ir.http.session_info, definido en web.
    # mail: "Ocultar Enviar mensaje" (chatter y /mail/message/post).
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'wizards/al_user_role_add_users_wizard_views.xml',
        'views/al_user_role_restriction_views.xml',
        'views/al_user_role_views.xml',
        'views/al_user_role_history_views.xml',
        'views/res_users_views.xml',
        'views/res_groups_views.xml',
        'views/ir_ui_menu_views.xml',
        'views/al_user_role_view_element_views.xml',
        'wizards/al_user_role_from_user_wizard_views.xml',
        'wizards/al_user_role_from_groups_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'al_user_role/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
