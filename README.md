# Inventory Management System

Full-stack CRUD app: **HTML/CSS/JavaScript** frontend (Node.js tooling), **Python Flask** REST API, **SQLite** database.

## Structure

```
inventory-system/
├── backend/
│   ├── app.py            # Flask REST API + SQLite schema
│   ├── test_app.py       # unit tests (unittest)
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js            # Fetch API calls, live search, low-stock alerts
└── package.json          # Node.js tooling (dev server, formatter, checks)
```

## Run it

**Option 1 – single command (Flask serves the frontend too)**

```bash
pip install -r backend/requirements.txt
python backend/app.py
# open http://127.0.0.1:5000
```

**Option 2 – Node.js dev server for the frontend**

```bash
npm install
python backend/app.py      # terminal 1 -> API on :5000
npm run serve              # terminal 2 -> UI on :5173
```

Other scripts: `npm run format`, `npm run check`, `npm test`.

## SQLite schema

```sql
CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL,
    quantity   INTEGER NOT NULL CHECK (quantity >= 0),
    price      REAL NOT NULL CHECK (price >= 0)
);
```

The database file (`backend/inventory.db`) is created automatically on first run.

## REST API

| Method | Endpoint                      | Purpose                                              |
|--------|-------------------------------|------------------------------------------------------|
| GET    | `/api/products`               | List all products                                    |
| GET    | `/api/products/search?q=...`  | Search by product ID, name or category               |
| GET    | `/api/products/low-stock`     | Products at or below the threshold (5 units)         |
| GET    | `/api/products/<id>`          | Get one product                                      |
| POST   | `/api/products`               | Add a product                                        |
| PUT/PATCH | `/api/products/<id>`       | Update `quantity`, `price`, or adjust with `change`  |
| DELETE | `/api/products/<id>`          | Delete a product                                     |

## Validation and edge cases

- Quantity and price must be valid, non-negative numbers; quantity must be a whole number.
- Duplicate product IDs return `409`.
- Reducing stock below zero is rejected (`400`, "Insufficient stock") and the stock is left unchanged.
- Searching for an unavailable product returns an empty list; the UI shows "No products found".
- Unknown IDs on update/delete return `404`.
- Validation runs in both the browser and the server; the database also enforces `CHECK` constraints.

## Frontend behaviour (no page reloads)

- Add-product form with inline errors.
- Live, debounced search via `fetch`.
- `+` / `−` stock buttons, "Set stock" and "Set price" actions, delete with confirmation.
- Low-stock banner plus per-row `LOW STOCK` / `OUT OF STOCK` badges, refreshed after every change.

## Tests

```bash
python -m unittest discover -s backend -v
```
