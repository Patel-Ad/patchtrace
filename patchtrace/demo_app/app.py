import sqlite3
from flask import Flask, request, jsonify


def create_app():
    app = Flask(__name__)
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT, token TEXT);
    CREATE TABLE orders(id INTEGER PRIMARY KEY, user_id INTEGER, item TEXT, total REAL);
    INSERT INTO users VALUES (1,'alice','token-alice'),(2,'bob','token-bob');
    INSERT INTO orders VALUES (1,1,'Laptop',999.0),(2,2,'Secret gift',49.0),(3,1,'Mouse',19.0);
    """)

    def current_user():
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        return db.execute("SELECT * FROM users WHERE token=?", (token,)).fetchone()

    @app.get("/orders")
    def list_orders():
        user = current_user()
        if not user:
            return jsonify(error="unauthorized"), 401
        rows = db.execute("SELECT * FROM orders WHERE user_id=?", (user["id"],)).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.get("/orders/<int:order_id>")
    def get_order(order_id):
        user = current_user()
        if not user:
            return jsonify(error="unauthorized"), 401
        order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            return jsonify(error="not found"), 404
        return jsonify(dict(order))  # BUG: never checks that this order belongs to the logged-in user

    return app
