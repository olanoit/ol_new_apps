# -*- coding: utf-8 -*-
from datetime import datetime
from unittest.mock import patch

import pytz

from odoo.tests import tagged

from .common import AlUserRoleCommon


@tagged('post_install', '-at_install')
class TestAlUserRoleCronAndNames(AlUserRoleCommon):

    def test_cron_daily_at_0005_local(self):
        cron = self.env.ref('al_user_role.ir_cron_al_user_role_update_users')
        cron.write({'interval_number': 3, 'interval_type': 'hours', 'active': False})
        # La zona del admin no influye: manda la de la compañía (vacía = Lima).
        self.env.ref('base.user_admin').tz = 'Europe/London'
        self.company.partner_id.tz = False
        self.Role._al_reset_cron_schedule()
        self.assertEqual((cron.interval_number, cron.interval_type), (1, 'days'))
        self.assertTrue(cron.active)
        tz = pytz.timezone('America/Lima')
        local = pytz.utc.localize(cron.nextcall).astimezone(tz)
        self.assertEqual((local.hour, local.minute), (0, 5))
        self.assertGreater(local, datetime.now(tz))

    def test_cron_uses_company_timezone_for_today(self):
        tz_seen = []
        Line = type(self.Line)
        original = Line._compute_is_enabled

        def spy(lines):
            tz_seen.append(lines.env.context.get('tz'))
            return original(lines)

        self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        # Una zona distinta de la por defecto (Lima), para ver que manda la compañía.
        self.company.partner_id.tz = 'America/Bogota'
        self.env.invalidate_all()
        with patch.object(Line, '_compute_is_enabled', spy):
            self.Role._cron_update_users()
        self.assertIn('America/Bogota', tz_seen)

    def test_line_display_name(self):
        line = self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        self.assertEqual(line.display_name, 'Rol interno → Usuario roles')
        line.company_id = self.company
        self.assertEqual(
            line.display_name, f'Rol interno → Usuario roles ({self.company.name})',
        )

    def test_history_display_name(self):
        line = self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        line.unlink()
        History = self.env['al.user.role.history']
        names = History.search([('user_id', '=', self.user.id)], order='id').mapped('display_name')
        self.assertEqual(names, [
            'Alta: Rol interno → Usuario roles',
            'Baja: Rol interno → Usuario roles',
        ])
