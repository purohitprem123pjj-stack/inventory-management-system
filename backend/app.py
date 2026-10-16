"""Inventory Management System - Flask REST API with SQLite."""
import os
import sqlite3

from flask import Flask, g, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
LOW_STOCK_THRESHOLD = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL,
    quantity   INTEGER NOT NULL CHECK (quantity >= 0),
    price      REAL NOT NULL CHECK (price >= 0)
);
"""


def create_app(db_path=None):
    app = Flask(__name__, static_folder=None)
    app.config["DATABASE"] = db_path or os.path.join(BASE_DIR, "inventory.db")

    # ---------- database helpers ----------
    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with sqlite3.connect(app.config["DATABASE"]) as conn:
        conn.executescript(SCHEMA)

    # ---------- CORS (lets the Node dev server call the API) ----------
    @app.after_request
    def add_cors(resp):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        return resp

    # ---------- validation ----------
    def error(message, status=400):
        return jsonify({"error": message}), status

    def parse_number(value, field, integer=False):
        """Return (number, error_message). Rejects negatives, NaN and bad types."""
        if isinstance(value, bool) or value is None or value == "":
            return None, f"{field} is required"
        try:
            num = int(value) if integer else float(value)
            if integer and float(value) != num:
                return None, f"{field} must be a whole number"
        except (TypeError, ValueError):
            return None, f"{field} must be a valid number"
        if num != num or num in (float("inf"), float("-inf")):
            return None, f"{field} must be a valid number"
        if num < 0:
            return None, f"{field} cannot be negative"
        return num, None

    def row_to_dict(row):
        d = dict(row)
        d["low_stock"] = d["quantity"] <= LOW_STOCK_THRESHOLD
        return d

    # ---------- routes ----------
    @app.route("/api/products", methods=["GET"])
    def list_products():
        rows = get_db().execute(
            "SELECT * FROM products ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])

    @app.route("/api/products/search", methods=["GET"])
    def search_products():
        q = (request.args.get("q") or "").strip()
        if not q:
            return list_products()
        like = f"%{q}%"
        rows = get_db().execute(
            """SELECT * FROM products
               WHERE product_id LIKE ? OR name LIKE ? OR category LIKE ?
               ORDER BY name COLLATE NOCASE""",
            (like, like, like),
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])

    @app.route("/api/products/low-stock", methods=["GET"])
    def low_stock():
        rows = get_db().execute(
            "SELECT * FROM products WHERE quantity <= ? ORDER BY quantity ASC",
            (LOW_STOCK_THRESHOLD,),
        ).fetchall()
        return jsonify({"threshold": LOW_STOCK_THRESHOLD,
                        "products": [row_to_dict(r) for r in rows]})

    @app.route("/api/products/<product_id>", methods=["GET"])
    def get_product(product_id):
        row = get_db().execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
        if row is None:
            return error("Product not found", 404)
        return jsonify(row_to_dict(row))

    @app.route("/api/products", methods=["POST"])
    def add_product():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error("Request body must be JSON")

        product_id = str(data.get("product_id", "")).strip()
        name = str(data.get("name", "")).strip()
        category = str(data.get("category", "")).strip()
        if not product_id:
            return error("product_id is required")
        if not name:
            return error("name is required")
        if not category:
            return error("category is required")

        quantity, err = parse_number(data.get("quantity"), "quantity", integer=True)
        if err:
            return error(err)
        price, err = parse_number(data.get("price"), "price")
        if err:
            return error(err)

        db = get_db()
        try:
            db.execute(
                "INSERT INTO products (product_id, name, category, quantity, price) "
                "VALUES (?, ?, ?, ?, ?)",
                (product_id, name, category, quantity, price),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return error(f"Product ID '{product_id}' already exists", 409)
        created = db.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
        return jsonify(row_to_dict(created)), 201

    @app.route("/api/products/<product_id>", methods=["PUT", "PATCH"])
    def update_product(product_id):
        """Update stock quantity and/or price.

        Send "quantity" to set an absolute quantity, or "change" to adjust it
        by a signed delta. Stock can never go below zero.
        """
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error("Request body must be JSON")

        db = get_db()
        row = db.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
        if row is None:
            return error("Product not found", 404)

        quantity, price = row["quantity"], row["price"]
        touched = False

        if "quantity" in data:
            quantity, err = parse_number(data["quantity"], "quantity", integer=True)
            if err:
                return error(err)
            touched = True
        elif "change" in data:
            try:
                delta = int(data["change"])
                if float(data["change"]) != delta or isinstance(data["change"], bool):
                    raise ValueError
            except (TypeError, ValueError):
                return error("change must be a whole number")
            if row["quantity"] + delta < 0:
                return error(
                    f"Insufficient stock: only {row['quantity']} in stock, "
                    f"cannot reduce by {abs(delta)}"
                )
            quantity = row["quantity"] + delta
            touched = True

        if "price" in data:
            price, err = parse_number(data["price"], "price")
            if err:
                return error(err)
            touched = True

        if not touched:
            return error("Provide quantity, change, or price to update")

        db.execute(
            "UPDATE products SET quantity = ?, price = ? WHERE product_id = ?",
            (quantity, price, product_id),
        )
        db.commit()
        updated = db.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
        return jsonify(row_to_dict(updated))

    @app.route("/api/products/<product_id>", methods=["DELETE"])
    def delete_product(product_id):
        db = get_db()
        cur = db.execute("DELETE FROM products WHERE product_id = ?", (product_id,))
        db.commit()
        if cur.rowcount == 0:
            return error("Product not found", 404)
        return jsonify({"message": f"Product '{product_id}' deleted"})

    @app.route("/api/products", methods=["OPTIONS"])
    @app.route("/api/products/<path:_p>", methods=["OPTIONS"])
    def preflight(_p=None):
        return ("", 204)

    # ---------- serve the frontend too (single-command run) ----------
    @app.route("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(FRONTEND_DIR, filename)

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
