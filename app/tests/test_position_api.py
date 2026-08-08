import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server
from engine import execution, positions, store


class ProtectedBroker:
    def confirm_attached_protection(self, **kwargs):
        from engine.contracts import BrokerOrder, OrderKind
        return BrokerOrder(
            broker_order_id="stop-broker-1", client_order_id=kwargs["client_order_id"],
            symbol=kwargs["symbol"], status="OPEN", order_kind=OrderKind.MARKET,
            quantity=kwargs["quantity"], filled_quantity=kwargs["quantity"],
            limit_price=kwargs["stop"], reduce_only=True, updated_at=2,
            version="test")


def test_position_custody_api_requires_explicit_acknowledgements():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "positions.db"
        con = store.connect(db)
        positions._ensure(con)
        execution._ensure(con)
        con.execute(
            "INSERT INTO execution_outbox(intent_id,idempotency_key,mode,setup_id,"
            "symbol,payload,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("i1", "key-i1", "TESTNET", "s1", "BTCUSDT", "{}",
             "SUBMITTED", 1, 1))
        con.execute(
            "INSERT INTO managed_positions(position_id,intent_id,symbol,direction,"
            "quantity,entry,stop,owner,protection_client_id,protection_status,state,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            ("p1", "i1", "BTCUSDT", "LONG", "0.01", "50000", "49000",
             "BOT", "stop-1", "CONFIRMED", "OPEN", 1))
        con.commit()
        con.close()

        original = store.connect
        with patch("server.store.connect", side_effect=lambda: original(db)), \
                patch("server.broker_factory.phemex_for_mode",
                      return_value=ProtectedBroker()):
            client = TestClient(server.app)
            custody = client.get("/api/positions/managed").json()["items"][0]
            assert custody["protection_status"] == "CONFIRMED"
            assert custody["setup_id"] == "s1"
            assert client.post(
                "/api/positions/p1/manual-override", json={}).status_code == 400
            override = client.post(
                "/api/positions/p1/manual-override", json={"acknowledgement":
                "I UNDERSTAND BOT DISCRETIONARY MANAGEMENT WILL STOP"})
            assert override.status_code == 200
            assert override.json()["owner"] == "MANUAL_OVERRIDE"
            assert client.post(
                "/api/positions/p1/return-control", json={}).status_code == 400
            returned = client.post(
                "/api/positions/p1/return-control",
                json={"acknowledgement": "RETURN CONTROL TO BOT"})
            assert returned.status_code == 200
            assert returned.json()["owner"] == "BOT"
