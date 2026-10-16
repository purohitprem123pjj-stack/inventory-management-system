// When served by Flask (same origin) use a relative URL; when served by the
// Node dev server (port 5173) point at the Flask backend on port 5000.
const API = window.location.port === "5173" ? "http://127.0.0.1:5000/api" : "/api";

const $ = (sel) => document.querySelector(sel);
const body = $("#product-body");
const searchInput = $("#search");
const formError = $("#form-error");

let searchTimer = null;
let toastTimer = null;

// ---------- helpers ----------
function toast(message, type = "success") {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = "toast"), 3000);
}

async function request(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* empty body */
  }
  if (!res.ok) {
    throw new Error((data && data.error) || `Request failed (${res.status})`);
  }
  return data;
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = String(value);
  return div.innerHTML;
}

const money = (n) => Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ---------- rendering ----------
function renderProducts(products, query = "") {
  $("#count").textContent = products.length;
  const empty = $("#empty");

  if (products.length === 0) {
    body.innerHTML = "";
    empty.classList.remove("hidden");
    empty.textContent = query
      ? `No products found matching "${query}".`
      : "No products yet. Add your first product above.";
    return;
  }
  empty.classList.add("hidden");

  body.innerHTML = products
    .map((p) => {
      const badge =
        p.quantity === 0
          ? '<span class="badge out">OUT OF STOCK</span>'
          : p.low_stock
          ? '<span class="badge low">LOW STOCK</span>'
          : "";
      const id = escapeHtml(p.product_id);
      return `
      <tr class="${p.low_stock ? "low" : ""}" data-id="${id}">
        <td>${id}</td>
        <td>${escapeHtml(p.name)}${badge}</td>
        <td>${escapeHtml(p.category)}</td>
        <td class="num">
          <span class="stock-cell">
            <button class="btn step" data-action="dec" title="Reduce stock by 1">−</button>
            <span class="qty">${p.quantity}</span>
            <button class="btn step" data-action="inc" title="Increase stock by 1">+</button>
          </span>
        </td>
        <td class="num">${money(p.price)}</td>
        <td class="actions">
          <button class="btn small" data-action="set-stock">Set stock</button>
          <button class="btn small" data-action="set-price">Set price</button>
          <button class="btn small danger" data-action="delete">Delete</button>
        </td>
      </tr>`;
    })
    .join("");
}

function renderLowStock(data) {
  const banner = $("#low-stock-banner");
  if (!data.products.length) {
    banner.classList.add("hidden");
    return;
  }
  const items = data.products
    .map((p) => `<li>${escapeHtml(p.name)} (${escapeHtml(p.product_id)}) — ${p.quantity} left</li>`)
    .join("");
  banner.innerHTML = `<strong>⚠ Low stock alert: ${data.products.length} product(s) at or below ${data.threshold} units</strong><ul>${items}</ul>`;
  banner.classList.remove("hidden");
}

// ---------- data loading (no page reload) ----------
async function loadProducts() {
  const q = searchInput.value.trim();
  try {
    const path = q ? `/products/search?q=${encodeURIComponent(q)}` : "/products";
    renderProducts(await request(path), q);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function loadLowStock() {
  try {
    renderLowStock(await request("/products/low-stock"));
  } catch (err) {
    /* banner is non-critical */
  }
}

async function refresh() {
  await Promise.all([loadProducts(), loadLowStock()]);
}

// ---------- events ----------
$("#add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  formError.textContent = "";
  const form = e.target;
  const f = new FormData(form);

  const payload = {
    product_id: f.get("product_id").trim(),
    name: f.get("name").trim(),
    category: f.get("category").trim(),
    quantity: f.get("quantity"),
    price: f.get("price"),
  };

  // client-side validation (server validates again)
  if (!payload.product_id || !payload.name || !payload.category) {
    formError.textContent = "Product ID, name and category are required.";
    return;
  }
  if (payload.quantity === "" || Number(payload.quantity) < 0 || !Number.isInteger(Number(payload.quantity))) {
    formError.textContent = "Quantity must be a whole number, 0 or more.";
    return;
  }
  if (payload.price === "" || Number(payload.price) < 0) {
    formError.textContent = "Price must be 0 or more.";
    return;
  }

  try {
    await request("/products", { method: "POST", body: JSON.stringify(payload) });
    form.reset();
    toast(`Added "${payload.name}"`);
    await refresh();
  } catch (err) {
    formError.textContent = err.message;
  }
});

searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadProducts, 250); // debounce live search
});

body.addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const row = btn.closest("tr");
  const id = row.dataset.id;
  const url = `/products/${encodeURIComponent(id)}`;

  try {
    switch (btn.dataset.action) {
      case "inc":
        await request(url, { method: "PATCH", body: JSON.stringify({ change: 1 }) });
        break;
      case "dec":
        await request(url, { method: "PATCH", body: JSON.stringify({ change: -1 }) });
        break;
      case "set-stock": {
        const v = prompt(`Set new stock quantity for ${id}:`);
        if (v === null) return;
        await request(url, { method: "PATCH", body: JSON.stringify({ quantity: v }) });
        toast("Stock updated");
        break;
      }
      case "set-price": {
        const v = prompt(`Set new price (₹) for ${id}:`);
        if (v === null) return;
        await request(url, { method: "PATCH", body: JSON.stringify({ price: v }) });
        toast("Price updated");
        break;
      }
      case "delete":
        if (!confirm(`Delete product ${id}? This cannot be undone.`)) return;
        await request(url, { method: "DELETE" });
        toast(`Deleted ${id}`);
        break;
    }
    await refresh();
  } catch (err) {
    toast(err.message, "error");
  }
});

refresh();
