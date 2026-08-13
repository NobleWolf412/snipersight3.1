import io
import json
import unittest
import urllib.error
from unittest import mock

from engine import credentials, stocks


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class StockFoundationStatusTest(unittest.TestCase):
    def test_missing_connections_are_loud_and_isolated(self):
        stored = {
            "alpaca-paper": {"api_key": False, "api_secret": False},
            "massive-stocks": {"api_key": False},
        }
        with mock.patch.object(stocks.credentials, "status", return_value=stored):
            out = stocks.status()
        self.assertEqual(out["state"], "SETUP_REQUIRED")
        self.assertFalse(out["scanner_enabled"])
        self.assertFalse(out["live_enabled"])
        self.assertTrue(out["data_store"]["isolated"])
        self.assertEqual(out["data_store"]["name"], "stocks.db")
        self.assertTrue(any("Alpaca" in reason for reason in out["blockers"]))
        self.assertTrue(any("Massive" in reason for reason in out["blockers"]))

    def test_stored_is_configured_not_falsely_verified(self):
        stored = {
            "alpaca-paper": {"api_key": True, "api_secret": True},
            "massive-stocks": {"api_key": True},
        }
        with mock.patch.object(stocks.credentials, "status", return_value=stored):
            out = stocks.status()
        self.assertEqual(out["state"], "CONNECTIONS_CONFIGURED")
        self.assertEqual(out["providers"]["alpaca-paper"]["verification"], "NOT_RUN")
        self.assertTrue(any(reason.startswith("Verify both connections")
                            for reason in out["blockers"]))


class StockProviderConnectionTest(unittest.TestCase):
    @staticmethod
    def _secrets(target, field):
        return {("alpaca-paper", "api_key"): "paper-key",
                ("alpaca-paper", "api_secret"): "paper-secret",
                ("massive-stocks", "api_key"): "massive-key"}.get((target, field))

    def test_alpaca_verifies_paper_account_and_sip_without_writes(self):
        requests = []
        replies = iter([
            _Response({"id": "account-1", "status": "ACTIVE"}),
            _Response({"bar": {"t": "2026-08-13T15:00:00Z", "c": 1}}),
        ])

        def opener(request, timeout):
            requests.append(request)
            return next(replies)

        with mock.patch.object(stocks.credentials, "read_secret",
                               side_effect=self._secrets):
            out = stocks.test_connection("alpaca-paper", opener=opener)
        self.assertTrue(out["ok"])
        self.assertEqual([r.get_method() for r in requests], ["GET", "GET"])
        self.assertIn("paper-api.alpaca.markets/v2/account", requests[0].full_url)
        self.assertIn("feed=sip", requests[1].full_url)
        self.assertEqual(requests[0].get_header("Apca-api-key-id"), "paper-key")

    def test_alpaca_account_can_pass_while_sip_remains_blocked(self):
        calls = 0

        def opener(request, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                return _Response({"id": "account-1", "status": "ACTIVE"})
            raise urllib.error.HTTPError(
                request.full_url, 403, "forbidden", {},
                io.BytesIO(json.dumps({"message": "subscription does not permit SIP"}).encode()))

        with mock.patch.object(stocks.credentials, "read_secret",
                               side_effect=self._secrets):
            out = stocks.test_connection("alpaca-paper", opener=opener)
        self.assertFalse(out["ok"])
        self.assertTrue(out["paper_account"])
        self.assertFalse(out["sip_data"])
        self.assertIn("SIP", out["detail"])
        self.assertNotIn("paper-key", out["detail"])

    def test_massive_uses_bearer_header_not_query_string_secret(self):
        seen = []

        def opener(request, timeout):
            seen.append(request)
            return _Response({"status": "OK", "results": [{"ticker": "A"}]})

        with mock.patch.object(stocks.credentials, "read_secret",
                               side_effect=self._secrets):
            out = stocks.test_connection("massive-stocks", opener=opener)
        self.assertTrue(out["ok"])
        self.assertNotIn("massive-key", seen[0].full_url)
        self.assertEqual(seen[0].get_header("Authorization"), "Bearer massive-key")

    def test_unknown_provider_is_refused_before_network(self):
        opener = mock.Mock()
        with self.assertRaises(stocks.StockProviderError):
            stocks.test_connection("nyse", opener=opener)
        opener.assert_not_called()


class StockCredentialShapeTest(unittest.TestCase):
    def test_stock_targets_accept_only_the_fields_the_provider_uses(self):
        self.assertEqual(credentials.TARGET_FIELDS["alpaca-paper"],
                         ("api_key", "api_secret"))
        self.assertEqual(credentials.TARGET_FIELDS["massive-stocks"], ("api_key",))
        with self.assertRaises(ValueError):
            credentials.store_secret("massive-stocks", "api_secret", "do-not-store")


if __name__ == "__main__":
    unittest.main()
