from conftest import ALICE, BOB


def test_alice_cannot_read_bobs_order(client):
    # Order 2 belongs to Bob. Alice must NOT be able to read it.
    r = client.get("/orders/2", headers=ALICE)
    assert r.status_code in (403, 404)
    assert b"Secret gift" not in r.data


def test_bob_cannot_read_alices_order(client):
    # Order 1 belongs to Alice. Bob must NOT be able to read it (the attack works in both directions).
    r = client.get("/orders/1", headers=BOB)
    assert r.status_code in (403, 404)
    assert b"Laptop" not in r.data
