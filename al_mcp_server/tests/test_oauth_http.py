import base64
import hashlib
from urllib.parse import parse_qs, urlencode, urlsplit

from odoo.tests import HttpCase, new_test_user, tagged

from ..models.mcp_token import _hash_token

_PASSWORD = "Mcp-Test-Pass-2026"
_REDIRECT = "http://localhost:9999/cb"


@tagged("post_install", "-at_install")
class TestMcpOAuthHttp(HttpCase):

    def setUp(self):
        super().setUp()
        self.user = new_test_user(self.env, login="mcp_oauth_user", password=_PASSWORD,
                                  groups="base.group_user")

    def _register(self, uris):
        return self.url_open("/oauth/register", json={"client_name": "Test", "redirect_uris": uris})

    def test_register_rejects_unsafe_redirect_uris(self):
        for uri in ("javascript:alert(1)", "http://evil.example/cb", "https://ok.example/cb#frag"):
            with self.subTest(uri=uri):
                self.assertEqual(self._register([uri]).status_code, 400)

    def test_authorize_rejects_unregistered_redirect(self):
        client_id = self._register([_REDIRECT]).json()["client_id"]
        for cid, uri in (("desconocido", _REDIRECT), (client_id, "https://evil.example/cb")):
            with self.subTest(client_id=cid, uri=uri):
                res = self.url_open("/oauth/authorize?" + urlencode({
                    "client_id": cid, "redirect_uri": uri,
                    "code_challenge": "abc", "code_challenge_method": "S256",
                }), allow_redirects=False)
                self.assertEqual(res.status_code, 400)
                self.assertNotIn("Location", res.headers)
                # El POST tampoco emite código hacia una URI no registrada
                res = self.url_open("/oauth/authorize", data={
                    "client_id": cid, "redirect_uri": uri, "code_challenge": "abc",
                    "login": self.user.login, "password": _PASSWORD,
                }, allow_redirects=False)
                self.assertEqual(res.status_code, 400)
                self.assertNotIn("Location", res.headers)

    def test_full_flow_and_revoke(self):
        client_id = self._register([_REDIRECT]).json()["client_id"]
        verifier = "v" * 64
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()

        res = self.url_open("/oauth/authorize", data={
            "client_id": client_id, "redirect_uri": _REDIRECT, "code_challenge": challenge,
            "state": "s1", "login": self.user.login, "password": _PASSWORD,
        }, allow_redirects=False)
        self.assertEqual(res.status_code, 302)
        location = res.headers["Location"]
        self.assertTrue(location.startswith(_REDIRECT + "?"))
        query = parse_qs(urlsplit(location).query)
        self.assertEqual(query["state"], ["s1"])
        code = query["code"][0]

        # El código queda ligado al cliente que lo pidió
        bad = self.url_open("/oauth/token", data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": _REDIRECT,
            "code_verifier": verifier, "client_id": "otro-cliente",
        })
        self.assertEqual(bad.status_code, 400)

        res = self.url_open("/oauth/token", data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": _REDIRECT,
            "code_verifier": verifier, "client_id": client_id,
        })
        self.assertEqual(res.status_code, 200)
        access_token = res.json()["access_token"]
        token = self.env["mcp.token"].sudo().search([("token", "=", _hash_token(access_token))])
        self.assertEqual(token.user_id, self.user)
        self.assertEqual(token.state, "active")

        self.url_open("/oauth/revoke", data={"token": access_token})
        token.invalidate_recordset(["state"])
        self.assertEqual(token.state, "revoked")

    def test_wrong_password_does_not_issue_code(self):
        client_id = self._register([_REDIRECT]).json()["client_id"]
        res = self.url_open("/oauth/authorize", data={
            "client_id": client_id, "redirect_uri": _REDIRECT, "code_challenge": "abc",
            "login": self.user.login, "password": "incorrecta",
        }, allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("Location", res.headers)


@tagged("post_install", "-at_install")
class TestMcpPublicPagesHttp(HttpCase):

    def setUp(self):
        super().setUp()
        self.viewer = new_test_user(self.env, login="mcp_viewer", password=_PASSWORD,
                                    groups="base.group_user")
        self.artifact = self.env["mcp.html.artifact"].create({
            "name": "Privado", "html": "<p>secreto</p>", "is_public": False,
        })

    def test_raw_artifact_is_sandboxed(self):
        self.artifact.is_public = True
        res = self.url_open(f"/mcp-artifact/{self.artifact.slug}/raw")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.headers["Content-Security-Policy"].startswith("sandbox allow-scripts"))

    def test_other_user_session_does_not_open_private_artifact(self):
        self.authenticate(self.viewer.login, _PASSWORD)
        res = self.url_open(f"/mcp-artifact/{self.artifact.slug}", allow_redirects=False)
        self.assertEqual(res.status_code, 404)
        res = self.url_open(
            f"/mcp-artifact/{self.artifact.slug}?token={self.artifact.access_token}",
            allow_redirects=False,
        )
        self.assertEqual(res.status_code, 200)
