from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestMcpRecordRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login="mcp_rule_user", groups="base.group_user")
        cls.other = new_test_user(cls.env, login="mcp_rule_other", groups="base.group_user")

    def test_session_log_only_own_and_readonly(self):
        Log = self.env["mcp.session.log"].sudo()
        own = Log.create({"tool_name": "odoo_search_read", "user_id": self.user.id})
        foreign = Log.create({"tool_name": "odoo_search_read", "user_id": self.other.id,
                              "request_payload": '{"email": "privado@example.com"}'})
        visible = self.env["mcp.session.log"].with_user(self.user).search([])
        self.assertIn(own, visible)
        self.assertNotIn(foreign, visible)
        with self.assertRaises(AccessError):
            own.with_user(self.user).write({"tool_name": "falsificado"})
        with self.assertRaises(AccessError):
            self.env["mcp.session.log"].with_user(self.user).create({"tool_name": "x"})

    def test_html_artifact_is_private_to_owner(self):
        foreign = self.env["mcp.html.artifact"].with_user(self.other).create({"name": "Ajeno"})
        Artifact = self.env["mcp.html.artifact"].with_user(self.user)
        self.assertNotIn(foreign, Artifact.search([]))
        with self.assertRaises(AccessError):
            foreign.with_user(self.user).write({"html": "<script>alert(1)</script>"})
        own = Artifact.create({"name": "Propio"})
        self.assertEqual(own.created_by, self.user)
        with self.assertRaises(AccessError):
            own.write({"created_by": self.other.id})

    def test_portal_page_owner_is_readonly(self):
        page = self.env["mcp.portal.page"].with_user(self.user).create({"name": "Mi tablero"})
        admin = self.env.ref("base.user_admin")
        with self.assertRaises(AccessError):
            page.write({"created_by": admin.id})
        self.assertEqual(page.created_by, self.user)
        # Un administrador sí puede reasignarlo
        page.with_user(admin).write({"created_by": self.other.id})
        self.assertEqual(page.created_by, self.other)
