import os
import tempfile
import unittest

from app import create_app


class InventoryApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app = create_app(os.path.join(self.tmp.name, "test.db"))
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, pid="P1", name="USB Cable", category="Electronics", quantity=10, price=199.5):
        return self.client.post("/api/products", json={
            "product_id": pid, "name": name, "category": category,
            "quantity": quantity, "price": price,
        })

    # ---- create / list ----
    def test_add_and_list(self):
        r = self.add()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["name"], "USB Cable")
        items = self.client.get("/api/products").get_json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["product_id"], "P1")

    def test_duplicate_id_rejected(self):
        self.add()
        self.assertEqual(self.add().status_code, 409)

    def test_invalid_numbers_rejected(self):
        for field, value in [("quantity", -1), ("price", -0.01), ("quantity", "abc"),
                             ("price", ""), ("quantity", 2.5)]:
            with self.subTest(field=field, value=value):
                self.assertEqual(self.add(**{field: value}).status_code, 400)

    def test_missing_fields_rejected(self):
        r = self.client.post("/api/products", json={"product_id": "X"})
        self.assertEqual(r.status_code, 400)

    # ---- search ----
    def test_search_by_name_id_category(self):
        self.add("P1", "USB Cable", "Electronics")
        self.add("P2", "Notebook", "Stationery")
        self.assertEqual(len(self.client.get("/api/products/search?q=usb").get_json()), 1)
        self.assertEqual(len(self.client.get("/api/products/search?q=P2").get_json()), 1)
        self.assertEqual(len(self.client.get("/api/products/search?q=station").get_json()), 1)

    def test_search_unavailable_product_returns_empty(self):
        self.add()
        r = self.client.get("/api/products/search?q=doesnotexist")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), [])

    # ---- update ----
    def test_update_stock_and_price(self):
        self.add()
        r = self.client.patch("/api/products/P1", json={"quantity": 25, "price": 150})
        self.assertEqual(r.get_json()["quantity"], 25)
        self.assertEqual(r.get_json()["price"], 150)
        r = self.client.patch("/api/products/P1", json={"change": -5})
        self.assertEqual(r.get_json()["quantity"], 20)

    def test_reduce_stock_below_zero_rejected(self):
        self.add(quantity=3)
        r = self.client.patch("/api/products/P1", json={"change": -4})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Insufficient stock", r.get_json()["error"])
        self.assertEqual(self.client.get("/api/products/P1").get_json()["quantity"], 3)

    def test_set_negative_quantity_or_price_rejected(self):
        self.add()
        self.assertEqual(self.client.patch("/api/products/P1", json={"quantity": -1}).status_code, 400)
        self.assertEqual(self.client.patch("/api/products/P1", json={"price": -5}).status_code, 400)

    def test_update_unknown_product_404(self):
        self.assertEqual(self.client.patch("/api/products/NOPE", json={"quantity": 1}).status_code, 404)

    # ---- delete ----
    def test_delete(self):
        self.add()
        self.assertEqual(self.client.delete("/api/products/P1").status_code, 200)
        self.assertEqual(self.client.get("/api/products").get_json(), [])
        self.assertEqual(self.client.delete("/api/products/P1").status_code, 404)

    # ---- low stock ----
    def test_low_stock_alerts(self):
        self.add("P1", quantity=2)
        self.add("P2", quantity=50)
        data = self.client.get("/api/products/low-stock").get_json()
        self.assertEqual([p["product_id"] for p in data["products"]], ["P1"])
        prods = {p["product_id"]: p for p in self.client.get("/api/products").get_json()}
        self.assertTrue(prods["P1"]["low_stock"])
        self.assertFalse(prods["P2"]["low_stock"])

    # ---- frontend is served ----
    def test_frontend_served(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Inventory Management", r.data)


if __name__ == "__main__":
    unittest.main()
