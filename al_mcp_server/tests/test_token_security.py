import json

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from ..models.mcp_token import _hash_token


@tagged("post_install", "-at_install")
class TestMcpTokenSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login="mcp_tok_user", groups="base.group_user")
        cls.Token = cls.env["mcp.token"]

    def _issue(self):
        raw = self.Token.sudo().issue(self.user.id, client_name="test", token_type="pat")
        return self.Token.sudo().search([("token", "=", _hash_token(raw))])

    def test_owner_cannot_escalate_governance(self):
        token = self._issue()
        token.sudo().scope = "read"
        token_as_user = token.with_user(self.user)
        forbidden = [
            {"scope": "admin"},
            {"field_restrictions": False},
            {"expires_at": False},
            {"ip_allowlist": False},
            {"denied_model_ids": [(5, 0, 0)]},
            {"token": _hash_token("elegido-por-el-usuario")},
            {"user_id": self.env.ref("base.user_admin").id},
        ]
        for vals in forbidden:
            with self.subTest(vals=vals), self.assertRaises(AccessError):
                token_as_user.write(vals)
        self.assertEqual(token.scope, "read")
        # Renombrar sí está permitido
        token_as_user.write({"name": "Mi cliente"})
        self.assertEqual(token.name, "Mi cliente")

    def test_owner_can_revoke_but_not_reactivate(self):
        token = self._issue()
        token.with_user(self.user).action_revoke()
        self.assertEqual(token.state, "revoked")
        with self.assertRaises(AccessError):
            token.with_user(self.user).write({"state": "active"})

    def test_owner_cannot_mint_token(self):
        with self.assertRaises(AccessError):
            self.Token.with_user(self.user).create({
                "name": "fabricado",
                "token": _hash_token("abc"),
                "user_id": self.user.id,
            })

    def test_pat_button_still_works(self):
        action = self.Token.with_user(self.user).action_generate_pat()
        self.assertEqual(action["res_model"], "mcp.pat.wizard")
        wizard = self.env["mcp.pat.wizard"].browse(action["res_id"])
        self.assertEqual(wizard.token_id.user_id, self.user)
        self.assertEqual(wizard.token_id.token, _hash_token(wizard.raw_token))

    def test_refresh_keeps_scope_and_restrictions(self):
        _raw_access, raw_refresh = self.Token.sudo().issue_oauth(self.user.id, "cli")
        token = self.Token.sudo().search([("refresh_token", "=", _hash_token(raw_refresh))])
        partner_model = self.env["ir.model"]._get("res.partner")
        company_model = self.env["ir.model"]._get("res.company")
        restrictions = json.dumps({"res.partner": ["name"]})
        token.write({
            "scope": "read",
            "allowed_model_ids": [(6, 0, partner_model.ids)],
            "denied_model_ids": [(6, 0, company_model.ids)],
            "field_restrictions": restrictions,
            "ip_allowlist": "10.0.0.0/8",
            "ip_denylist": "10.0.0.1",
            "capture_payloads": True,
        })

        new_access, _new_refresh = self.Token.sudo().refresh(raw_refresh)
        new_token = self.Token.sudo().search([("token", "=", _hash_token(new_access))])

        self.assertEqual(token.state, "expired")
        self.assertEqual(new_token.scope, "read")
        self.assertEqual(new_token.allowed_model_ids, partner_model)
        self.assertEqual(new_token.denied_model_ids, company_model)
        self.assertEqual(new_token.field_restrictions, restrictions)
        self.assertEqual(new_token.ip_allowlist, "10.0.0.0/8")
        self.assertEqual(new_token.ip_denylist, "10.0.0.1")
        self.assertTrue(new_token.capture_payloads)
        self.assertEqual(new_token.user_id, self.user)
