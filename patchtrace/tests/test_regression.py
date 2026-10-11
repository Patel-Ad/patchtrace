from conftest import ALICE


def test_user_can_read_own_order(client):
    r = client.get("/orders/1", headers=ALICE)
    assert r.status_code == 200
    assert r.get_json()["item"] == "Laptop"


def test_unauthenticated_request_rejected(client):
    assert client.get("/orders/1").status_code == 401


def test_list_returns_only_own_orders(client):
    items = client.get("/orders", headers=ALICE).get_json()
    assert len(items) == 2
    assert all(o["user_id"] == 1 for o in items)


def test_missing_order_returns_404(client):
    assert client.get("/orders/999", headers=ALICE).status_code == 404
