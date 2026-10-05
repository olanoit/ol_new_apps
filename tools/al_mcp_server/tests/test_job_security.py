import json

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from ..services import tool_executor


@tagged("post_install", "-at_install")
class TestMcpJobSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login="mcp_job_user", groups="base.group_user")
        cls.other = new_test_user(cls.env, login="mcp_job_other", groups="base.group_user")
        cls.partner = cls.env["res.partner"].create({"name": "MCP intacto"})

    def _job(self, operation, args, scope="write", restrictions=None, user=None):
        return self.env["mcp.job"].sudo().create({
            "operation": operation,
            "user_id": (user or self.user).id,
            "payload": json.dumps({"args": args}),
            "mcp_scope": scope,
            "mcp_restrictions": json.dumps(restrictions) if restrictions else False,
        })

    def _mcp_env(self, user, scope="write"):
        return self.env(user=user.id, context=dict(self.env.context, mcp_scope=scope))

    def test_job_runs_as_submitter_not_cron_user(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("mcp_test.secret", "original")
        job = self._job("bulk_update", {
            "model": "ir.config_parameter",
            "domain": [("key", "=", "mcp_test.secret")],
            "values": {"value": "pisado"},
        }, scope="admin")
        job.action_run()
        self.assertEqual(job.state, "failed")
        self.assertEqual(ICP.get_param("mcp_test.secret"), "original")

    def test_write_scope_cannot_bulk_unlink(self):
        job = self._job("bulk_unlink", {"model": "res.partner", "domain": [("id", "=", self.partner.id)]})
        job.action_run()
        self.assertEqual(job.state, "failed")
        self.assertTrue(self.partner.exists())

    def test_write_scope_cannot_call_method(self):
        job = self._job("custom", {"model": "res.partner", "method": "action_archive", "ids": [self.partner.id]})
        job.action_run()
        self.assertEqual(job.state, "failed")
        self.assertTrue(self.partner.active)

    def test_denied_model_is_enforced(self):
        job = self._job("bulk_update", {
            "model": "res.partner", "domain": [("id", "=", self.partner.id)], "values": {"name": "x"},
        }, restrictions={"denied_models": ["res.partner"]})
        job.action_run()
        self.assertEqual(job.state, "failed")
        self.assertEqual(self.partner.name, "MCP intacto")

    def test_field_restrictions_are_enforced(self):
        job = self._job("bulk_update", {
            "model": "res.partner", "domain": [("id", "=", self.partner.id)], "values": {"email": "x@y.z"},
        }, restrictions={"field_restrictions": {"res.partner": ["name"]}})
        job.action_run()
        self.assertEqual(job.state, "failed")
        self.assertFalse(self.partner.email)

    def test_submit_rejects_escalation(self):
        env = self._mcp_env(self.user, "write")
        with self.assertRaises(PermissionError):
            tool_executor.execute_tool(env, "odoo_submit_job", {
                "operation": "bulk_unlink", "args": {"model": "res.partner", "domain": []},
            })

    def test_job_status_idor(self):
        job = self._job("export_csv", {"model": "res.partner", "fields": ["name"]}, user=self.other)
        with self.assertRaises(ValueError):
            tool_executor.execute_tool(self._mcp_env(self.user), "odoo_job_status", {"job_id": job.id})
        # Un token admin de un usuario sin grupo de sistema tampoco ve trabajos ajenos
        with self.assertRaises(ValueError):
            tool_executor.execute_tool(self._mcp_env(self.user, "admin"), "odoo_job_status", {"job_id": job.id})
        own = tool_executor.execute_tool(self._mcp_env(self.other), "odoo_job_status", {"job_id": job.id})
        self.assertEqual(own["job_id"], job.id)

    def test_owner_cannot_retarget_job(self):
        job = self._job("export_csv", {"model": "res.partner", "fields": ["name"]})
        job_as_user = job.with_user(self.user)
        for vals in ({"user_id": self.env.ref("base.user_admin").id}, {"mcp_scope": "admin"},
                     {"mcp_restrictions": False}, {"payload": "{}"}):
            with self.subTest(vals=vals), self.assertRaises(AccessError):
                job_as_user.write(vals)
