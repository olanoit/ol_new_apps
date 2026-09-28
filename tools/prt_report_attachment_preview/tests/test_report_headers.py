import json

from odoo.tests import HttpCase, tagged

REPORT = "base.report_irmodulereference"


@tagged("post_install", "-at_install")
class TestReportHeaders(HttpCase):
    """Content-Disposition of the preview route and of /report/download.

    In test mode the PDF engine returns HTML, which is enough to check the
    headers.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = cls.env["ir.module.module"].search([("name", "=", "base")])
        # The preview route is readonly like the core one. This report calls
        # fields_get(), which lazily creates properties definitions on first
        # use; test transactions roll back, so warm it up here instead of
        # letting every request replay on a read/write cursor.
        cls.env["ir.actions.report"]._render_qweb_html(REPORT, cls.module.ids)

    def _dispositions(self, response):
        return response.raw.headers.getlist("Content-Disposition")

    def test_preview_is_inline(self):
        self.authenticate("admin", "admin")
        response = self.url_open(f"/report/pdf/{REPORT}/{self.module.id}")
        self.assertEqual(response.status_code, 200)
        dispositions = self._dispositions(response)
        self.assertEqual(len(dispositions), 1)
        self.assertTrue(dispositions[0].startswith("inline"))

    def test_download_has_a_single_disposition(self):
        """The POS downloads invoices through /report/download: two different
        Content-Disposition headers make Chrome reject the response."""
        self.authenticate("admin", "admin")
        data = json.dumps([f"/report/pdf/{REPORT}/{self.module.id}", "qweb-pdf"])
        response = self.url_open(
            "/report/download", params={"data": data, "context": "{}"}
        )
        self.assertEqual(response.status_code, 200)
        dispositions = self._dispositions(response)
        self.assertEqual(len(dispositions), 1)
        self.assertTrue(dispositions[0].startswith("attachment"))

    def test_options_keep_plus_sign(self):
        """Options are JSON already decoded by werkzeug: a "+" must survive."""
        self.authenticate("admin", "admin")
        options = json.dumps({"phone": "+51 999"})
        response = self.url_open(
            f"/report/pdf/{REPORT}/{self.module.id}",
            params={"options": options, "context": json.dumps({"lang": "en_US"})},
        )
        self.assertEqual(response.status_code, 200)
