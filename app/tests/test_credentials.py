"""Credential vault: encrypted at rest, and unreadable through the API.

The security property under test is not "it stores a string" — it is that no
route can surface a secret and no plaintext reaches disk, the log, or git.
"""
import os
import unittest
from unittest import mock

from engine import credentials


@unittest.skipUnless(credentials.available(), "DPAPI is Windows-only")
class VaultTest(unittest.TestCase):
    def setUp(self):
        self.tmp = credentials.VAULT.parent / "credentials.test.vault"
        self._patch = mock.patch.object(credentials, "VAULT", self.tmp)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        if self.tmp.exists():
            os.remove(self.tmp)

    def test_plaintext_never_reaches_disk(self):
        secret = "SUPER-SECRET-VALUE-9f3a"
        credentials.store_secret("phemex-perp", "api_key", secret)
        raw = self.tmp.read_bytes()
        self.assertNotIn(secret.encode(), raw, "secret stored in cleartext")
        self.assertNotIn(secret.encode("utf-16-le"), raw)

    def test_roundtrip_in_process_only(self):
        credentials.store_secret("phemex-perp", "api_secret", "abc123")
        self.assertEqual(credentials.read_secret("phemex-perp", "api_secret"), "abc123")

    def test_status_reports_existence_not_values(self):
        credentials.store_secret("coinbase-spot", "api_key", "zzz")
        st = credentials.status()
        flat = repr(st)
        self.assertNotIn("zzz", flat, "status leaked a secret")
        self.assertIs(st["coinbase-spot"]["api_key"], True)
        self.assertIs(st["coinbase-spot"]["api_secret"], False)

    def test_clear_removes_the_secret(self):
        credentials.store_secret("phemex-perp", "api_key", "gone-soon")
        credentials.clear("phemex-perp", "api_key")
        self.assertIsNone(credentials.read_secret("phemex-perp", "api_key"))

    def test_testnet_and_mainnet_credentials_are_isolated(self):
        credentials.store_secret("phemex-testnet", "api_key", "test-key")
        credentials.store_secret("phemex-mainnet", "api_key", "live-key")
        self.assertEqual(credentials.read_secret(
            "phemex-testnet", "api_key"), "test-key")
        self.assertEqual(credentials.read_secret(
            "phemex-mainnet", "api_key"), "live-key")

    def test_unknown_venue_or_field_refused(self):
        """An open-ended store invites secrets nobody audits."""
        with self.assertRaises(ValueError):
            credentials.store_secret("nasdaq", "api_key", "x")
        with self.assertRaises(ValueError):
            credentials.store_secret("phemex-perp", "mothers_maiden_name", "x")

    def test_empty_value_refused(self):
        with self.assertRaises(ValueError):
            credentials.store_secret("phemex-perp", "api_key", "   ")


class NoReadRouteTest(unittest.TestCase):
    def test_no_http_route_calls_the_secret_reader(self):
        """`read_secret` must not be INVOKED anywhere the web layer can reach.

        Checks for a call, not a mention: server.py's docstring names the
        function precisely to record that it is in-process only, and a naive
        substring match would fail on that documentation.
        """
        import ast
        import pathlib
        # Resolved from THIS file, not the working directory. As a bare relative
        # path this passed from app/ and failed with FileNotFoundError from the
        # repo root — so `pytest app/tests/` reported a security assertion as
        # broken when nothing was wrong with it. A guard that cries wolf
        # depending on where you stood is a guard people learn to ignore.
        server = pathlib.Path(__file__).resolve().parent.parent / "server.py"
        with open(server, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "attr", None) or getattr(fn, "id", None)
                if name:
                    called.add(name)
        self.assertNotIn("read_secret", called,
                         "an HTTP handler can reach a decrypted secret")


if __name__ == "__main__":
    unittest.main()
