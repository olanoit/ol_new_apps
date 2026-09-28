import csv
import io
import json
import os
import tempfile
import zipfile

from lxml import etree

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from ..controllers.portal_controller import charts_json
from ..services import module_generator, schema_cache, tool_executor

_EVIL = (
    '</field></record><function model="res.users" name="write"/>'
    '<record id="x" model="res.groups"><field name="name">'
)


@tagged("post_install", "-at_install")
class TestMcpToolsHardening(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "MCP partner"})
        cls.user = new_test_user(cls.env, login="mcp_tools_user", groups="base.group_user")

    # ------------------------------------------------------------------
    # Escapado
    # ------------------------------------------------------------------

    def test_message_post_plain_text_is_escaped(self):
        result = tool_executor.execute_tool(self.env, "odoo_message_post", {
            "model": "res.partner",
            "id": self.partner.id,
            "body": 'hola <img src=x onerror="alert(1)">',
        })
        body = str(self.env["mail.message"].browse(result["message_id"]).body)
        self.assertNotIn("<img", body)
        self.assertIn("&lt;img", body)

    def test_charts_json_cannot_close_script(self):
        data = [{"index": 0, "option": {"name": "</script><script>alert(1)</script>"}}]
        out = str(charts_json(data))
        self.assertNotIn("</script>", out)
        self.assertNotIn("<", out)
        self.assertEqual(json.loads(out), data)

    def test_generator_escapes_xml(self):
        spec = {
            "technical_name": "x_mcp_test",
            "name": "X",
            "version": "19.0.1.0.0",
            "models": [{
                "name": "x.mcp.thing",
                "description": _EVIL,
                "fields": [{"name": "state", "type": "selection",
                            "selection": [["a", "A"]], "string": _EVIL}],
            }],
            "security": {
                "groups": [{"name": _EVIL}],
                "access_rights": [{"model": "x.mcp.thing", "group": "base.group_user",
                                   "name": "a,b\nfila,inyectada"}],
            },
            "menus": [{"name": _EVIL, "sequence": '1" x="',
                       "children": [{"name": _EVIL, "action_model": "x.mcp.thing"}]}],
        }
        zip_bytes, _warnings = module_generator.build_zip(spec)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    root = etree.fromstring(zf.read(name))
                    self.assertFalse(root.xpath("//function"), name)
            csv_text = zf.read("x_mcp_test/security/ir.model.access.csv").decode()
        rows = list(csv.reader(io.StringIO(csv_text)))
        # Cabecera + una sola regla: el salto de línea del nombre no crea filas nuevas
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][1], "a,b\nfila,inyectada")

    def test_generator_rejects_bad_references(self):
        errors = module_generator.validate_spec({
            "technical_name": "x_mcp_test",
            "name": "X",
            "security": {
                "groups": [{"name": "g", "implied_by": "base.group_user'))]\"/><x"}],
                "access_rights": [{"model": "x.mcp.thing", "group": "base.group_system,1,1,1,1"}],
            },
        })
        self.assertEqual(len(errors), 2)

    # ------------------------------------------------------------------
    # Módulos generados
    # ------------------------------------------------------------------

    def test_generated_module_technical_name_is_safe(self):
        Module = self.env["mcp.generated.module"]
        for bad in ("../odoo", "a/b", "", "Mayus"):
            with self.subTest(name=bad), self.assertRaises(ValidationError):
                Module.create({"name": "x", "technical_name": bad, "spec": "{}"})
        rec = Module.create({"name": "x", "technical_name": "x_mcp_ok", "spec": "{}"})
        with tempfile.TemporaryDirectory() as base:
            target = rec._safe_target_dir(base)
            self.assertEqual(target, os.path.join(os.path.realpath(base), "x_mcp_ok"))

    def test_generated_module_spec_must_match_record(self):
        rec = self.env["mcp.generated.module"].create({
            "name": "x", "technical_name": "x_mcp_ok",
            "spec": json.dumps({"technical_name": "otro_nombre", "name": "X"}),
        })
        with self.assertRaises(UserError):
            rec.action_generate()

    def test_module_tools_require_system_group(self):
        self.env["ir.config_parameter"].sudo().set_param("mcp_server.enable_module_generator", "True")
        env = self.env(user=self.user.id, context=dict(self.env.context, mcp_scope="admin"))
        with self.assertRaises(PermissionError):
            tool_executor.execute_tool(env, "odoo_install_generated_module", {"module_id": 1, "confirm": True})

    # ------------------------------------------------------------------
    # Herramientas ORM
    # ------------------------------------------------------------------

    def test_read_group_with_order(self):
        result = tool_executor.execute_tool(self.env, "odoo_read_group", {
            "model": "res.partner",
            "groupby": ["is_company"],
            "fields": ["__count"],
            "orderby": "is_company",
        })
        self.assertTrue(result["rows"])

    def test_onchange_uses_odoo19_spec(self):
        result = tool_executor.execute_tool(self.env, "odoo_onchange", {
            "model": "res.partner",
            "values": {"name": "Nuevo"},
            "field_onchange": ["name"],
        })
        self.assertIn("computed_values", result)

    def test_call_method_rejects_api_private(self):
        env = self.env(context=dict(self.env.context, mcp_scope="admin"))
        with self.assertRaises(AccessError):
            tool_executor.execute_tool(env, "odoo_call_method", {
                "model": "res.partner", "method": "check_access", "args": ["read"],
            })

    def test_field_restrictions_apply_to_domain(self):
        env = self.env(context=dict(
            self.env.context,
            mcp_restrictions={"field_restrictions": {"res.partner": ["name"]}},
        ))
        with self.assertRaises(PermissionError):
            tool_executor.execute_tool(env, "odoo_search_read", {
                "model": "res.partner", "domain": [["email", "=", "x@y.z"]],
            })
        with self.assertRaises(PermissionError):
            tool_executor.execute_tool(env, "odoo_count", {
                "model": "res.partner", "domain": [["email", "!=", False]],
            })

    def test_resource_read_respects_denied_models(self):
        from ..services import resource_service
        env = self.env(context=dict(
            self.env.context, mcp_restrictions={"denied_models": {"res.partner"}},
        ))
        with self.assertRaises(PermissionError):
            resource_service.read_resource("odoo://model/res.partner", env)

    def test_schema_cache_key_is_per_user(self):
        key_admin = schema_cache.scoped_key(self.env, "fields_get:res.partner")
        key_user = schema_cache.scoped_key(self.env(user=self.user.id), "fields_get:res.partner")
        self.assertNotEqual(key_admin, key_user)
