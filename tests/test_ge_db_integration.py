import secrets
import unittest
from unittest.mock import patch

from flask import Flask, jsonify

from sqlalchemy import delete, func, select

from src.ge_db.auth import create_admin
from src.ge_db.bridge import install, persist, persist_updates
from src.ge_db.connection import SessionLocal
from src.ge_db.models import LoginAudit, OrderRecord, UiEvent, UiState, User
from src.ge_app import app
from src.ui.app import create_detail_page, create_main_page
from src.ui.pages.statistics.page import create_statistics_page
from src.ui.settings import DEFAULTS


def ids(component):
    result = []

    def walk(node):
        identifier = getattr(node, "id", None)
        if identifier is not None:
            result.append(identifier)
        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            for child in children:
                walk(child)
        elif children is not None:
            walk(children)

    walk(component)
    return result


class GeDatabaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.username = "integration_" + secrets.token_hex(8)
        cls.user_id = create_admin(cls.username, secrets.token_urlsafe(24))
        cls.owner = f"user:{cls.user_id}"
        app._setup_server()

    @classmethod
    def tearDownClass(cls):
        with SessionLocal.begin() as session:
            owners = [cls.owner]
            session.execute(delete(OrderRecord).where(OrderRecord.owner_key.in_(owners)))
            session.execute(delete(UiEvent).where(UiEvent.owner_key.in_(owners)))
            session.execute(delete(UiState).where(UiState.owner_key.in_(owners)))
            session.execute(delete(LoginAudit).where(LoginAudit.username == cls.username))
            session.execute(delete(User).where(User.user_id == cls.user_id))

    def test_ge_features_remain_present(self):
        self.assertIn("sb-settings-open", ids(create_main_page()))
        self.assertIn("sb-settings-open", ids(create_detail_page()))
        statistics = ids(create_statistics_page())
        self.assertIn("f09-heatmap", statistics)
        self.assertIn("f10-heatmap", statistics)

    def test_database_observer_does_not_add_dash_components_or_callbacks(self):
        layout_ids = ids(app.layout)
        self.assertNotIn("ge-db-sync", layout_ids)
        self.assertIn("store-login-log", layout_ids)
        self.assertIn("store-session-started", layout_ids)
        self.assertNotIn("ge-db-sync.data", app.callback_map)

    def test_order_and_settings_are_written_to_fresh_database(self):
        persist(["13-comp2"], [{
            "machine": 13, "component": "comp2", "supplier": "supplier-a",
            "supplier_name": "공급업체 A", "qty": 2, "price": 15.5, "date": "2015-10-05",
        }], dict(DEFAULTS), owner=self.owner)
        with SessionLocal() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(OrderRecord)
                                            .where(OrderRecord.owner_key == self.owner)), 1)
            keys = set(session.scalars(select(UiState.state_key)
                                       .where(UiState.owner_key == self.owner)).all())
        self.assertEqual(keys, {"todo", "orders", "settings"})

    def test_orders_are_idempotent_and_invalid_updates_roll_back(self):
        order = {"machine": 13, "component": "comp2", "supplier": "a",
                 "qty": 2, "price": 15.5, "date": "2015-10-05"}
        persist_updates({"orders": [order, order]}, self.owner)
        self.assertEqual(persist_updates({"orders": [order, order]}, self.owner), 0)
        with self.assertRaises(ValueError):
            persist_updates({"orders": [dict(order, machine="invalid")]}, self.owner)
        with SessionLocal() as db:
            active = db.scalars(select(OrderRecord).where(
                OrderRecord.owner_key == self.owner, OrderRecord.status == "requested")).all()
            self.assertEqual(len(active), 2)
        persist_updates({"orders": []}, self.owner)
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(OrderRecord).where(
                OrderRecord.owner_key == self.owner, OrderRecord.status == "requested")), 0)

    def test_ge_settings_open_and_save_callbacks(self):
        client = app.server.test_client()
        with client.session_transaction() as browser_session:
            browser_session["user_id"] = self.user_id

        open_key = next(key for key in app.callback_map if "sb-settings-modal.is_open" in key)
        open_outputs = [{"id": output.component_id, "property": output.component_property}
                        for output in app.callback_map[open_key]["output"]]
        opened = client.post("/_dash-update-component", json={
            "output": open_key, "outputs": open_outputs,
            "inputs": [{"id": "sb-settings-open", "property": "n_clicks", "value": 1}],
            "state": [{"id": "store-settings", "property": "data", "value": dict(DEFAULTS)}],
            "changedPropIds": ["sb-settings-open.n_clicks"],
        })
        self.assertEqual(opened.status_code, 200)
        self.assertTrue(opened.get_json()["response"]["sb-settings-modal"]["is_open"])

        save_key = next(key for key in app.callback_map if "store-settings.data" in key)
        save_outputs = [{"id": output.component_id, "property": output.component_property}
                        for output in app.callback_map[save_key]["output"]]
        values = dict(DEFAULTS, main_sort="deadline", stats_horizon=14)
        saved = client.post("/_dash-update-component", json={
            "output": save_key, "outputs": save_outputs,
            "inputs": [{"id": "st-save", "property": "n_clicks", "value": 1},
                       {"id": "st-reset", "property": "n_clicks", "value": 0}],
            "state": [{"id": f"st-{key}", "property": "value", "value": value}
                      for key, value in values.items()],
            "changedPropIds": ["st-save.n_clicks"],
        })
        self.assertEqual(saved.status_code, 200)
        stored = saved.get_json()["response"]["store-settings"]["data"]
        self.assertEqual(stored["main_sort"], "deadline")
        self.assertEqual(stored["stats_horizon"], 14)


class DatabaseFailureTests(unittest.TestCase):
    def test_disabled_database_does_not_open_a_connection(self):
        with patch("src.ge_db.bridge.enabled", return_value=False), \
                patch("src.ge_db.bridge.SessionLocal") as db:
            self.assertEqual(persist_updates({"orders": []}), 0)
            db.assert_not_called()

    def test_database_failure_preserves_callback_response(self):
        server = Flask(__name__)
        install(server)
        payload = {"response": {"store-order-log": {"data": []}}, "multi": True}
        server.add_url_rule("/_dash-update-component", view_func=lambda: jsonify(payload), methods=["POST"])
        with patch("src.ge_db.bridge.enabled", return_value=True), \
                patch("src.ge_db.bridge.persist_updates", side_effect=RuntimeError("offline")), \
                self.assertLogs("src.ge_db.bridge", level="ERROR"):
            response = server.test_client().post("/_dash-update-component")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), payload)


if __name__ == "__main__":
    unittest.main()
