#!/usr/bin/env python3
"""
Odoo Seeding Script — CV Jamu Sehat Nusantara
===============================================
Mengisi Odoo dengan data perusahaan jamu tradisional.

Data dibaca dari file CSV di folder data/:
  - data/products.csv   → bahan baku, kemasan, produk jadi
  - data/contacts.csv   → customer & supplier
  - data/orders.csv     → sales orders & purchase orders
  - data/bom.csv        → Bill of Materials (resep jamu)

Cara pakai:
  1. Pastikan Odoo sudah running (docker compose up -d)
  2. Buat database baru di http://localhost:8069
  3. Edit konfigurasi di bawah sesuai database kamu
  4. Jalankan: python3 seed_odoo.py
"""

import csv
import os
import sys
import time
import xmlrpc.client
from collections import OrderedDict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

ODOO_URL = "http://localhost:8069"
ODOO_DB = "odoo_prod"
ODOO_USER = "irwan@odoo.com"
ODOO_PASSWORD = "admin123"


class OdooAPI:
    def __init__(self, url, db, username, password):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self.common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def authenticate(self):
        self.uid = self.common.authenticate(self.db, self.username, self.password, {})
        if not self.uid:
            print("❌ Gagal login! Periksa ODOO_DB, ODOO_USER, dan ODOO_PASSWORD.")
            sys.exit(1)
        print(f"✅ Login berhasil (uid={self.uid})")

    def _call(self, model, method, args=None, kwargs=None):
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, method, args or [], kwargs or {}
        )

    def create(self, model, values):
        return self._call(model, "create", [values])

    def write(self, model, ids, values):
        return self._call(model, "write", [ids, values])

    def search_read(self, model, domain, fields=None, limit=None):
        kwargs = {}
        if fields:
            kwargs["fields"] = fields
        if limit:
            kwargs["limit"] = limit
        return self._call(model, "search_read", [domain], kwargs)

    def search(self, model, domain, limit=None):
        kwargs = {}
        if limit:
            kwargs["limit"] = limit
        return self._call(model, "search", [domain], kwargs)

    def action(self, model, ids, method_name):
        return self._call(model, method_name, [ids if isinstance(ids, list) else [ids]])

    def safe_action(self, model, ids, method_name):
        try:
            self.action(model, ids, method_name)
        except xmlrpc.client.Fault:
            pass

    def validate_picking(self, picking_id):
        self.action("stock.picking", picking_id, "action_assign")
        move_lines = self.search_read(
            "stock.move.line",
            [("picking_id", "=", picking_id)],
            fields=["id", "state", "quantity_product_uom", "quantity"],
        )
        for ml in move_lines:
            if ml["state"] in ("done", "cancel"):
                continue
            qty = ml.get("quantity_product_uom", 0) or 0
            if qty > 0:
                self.write("stock.move.line", [ml["id"]], {"quantity": qty})
        self.safe_action("stock.picking", picking_id, "button_validate")


def read_csv(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"❌ File tidak ditemukan: {filepath}")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def seed_categories(api, products_data):
    print("\n📁 Membuat Product Categories...")
    cat_ids = {}
    categories = sorted(set(row["category"] for row in products_data))
    for name in categories:
        existing = api.search_read("product.category", [("name", "=", name)], fields=["id"], limit=1)
        if existing:
            cat_ids[name] = existing[0]["id"]
            print(f"   ⏭️  {name} (sudah ada)")
        else:
            cid = api.create("product.category", {"name": name})
            cat_ids[name] = cid
            print(f"   ✅ {name} (id={cid})")
    return cat_ids


def seed_products(api, products_data, cat_ids):
    print("\n📦 Membuat Products...")
    product_map = {}

    buy_route = api.search_read("stock.route", [("name", "ilike", "Buy")], fields=["id"], limit=1)
    mfg_route = api.search_read("stock.route", [("name", "ilike", "Manufacture")], fields=["id"], limit=1)
    buy_route_id = buy_route[0]["id"] if buy_route else False
    mfg_route_id = mfg_route[0]["id"] if mfg_route else False

    for row in products_data:
        name = row["name"]
        existing = api.search_read("product.product", [("name", "=", name)], fields=["id"], limit=1)
        if existing:
            product_map[name] = existing[0]["id"]
            print(f"   ⏭️  {name} (sudah ada)")
        else:
            prod_type = row.get("type", "buy")
            route_ids = []
            if prod_type == "buy" and buy_route_id:
                route_ids = [(4, buy_route_id)]
            elif prod_type == "manufacture" and mfg_route_id:
                route_ids = [(4, mfg_route_id)]

            vals = {
                "name": name,
                "categ_id": cat_ids[row["category"]],
                "list_price": float(row["sell_price"]),
                "standard_price": float(row["cost_price"]),
                "type": "consu",
                "is_storable": row["storable"] == "1",
                "sale_ok": prod_type in ("manufacture",),
                "purchase_ok": prod_type in ("buy",),
            }
            if route_ids:
                vals["route_ids"] = route_ids

            pid = api.create("product.product", vals)
            product_map[name] = pid
            type_label = "🏭" if prod_type == "manufacture" else "🛒"
            print(f"   ✅ {type_label} {name} (id={pid})")
    return product_map


def seed_contacts(api, contacts_data):
    print("\n👥 Membuat Contacts...")
    contact_map = {}
    country_cache = {}
    for row in contacts_data:
        name = row["name"]
        existing = api.search_read("res.partner", [("name", "=", name)], fields=["id"], limit=1)
        if existing:
            contact_map[name] = existing[0]["id"]
            print(f"   ⏭️  {name} (sudah ada)")
        else:
            country_name = row.get("country", "").strip()
            country_id = False
            if country_name:
                if country_name not in country_cache:
                    result = api.search_read("res.country", [("name", "=", country_name)], fields=["id"], limit=1)
                    if not result:
                        result = api.search_read("res.country", [("name", "ilike", country_name)], fields=["id"], limit=1)
                    country_cache[country_name] = result[0]["id"] if result else False
                country_id = country_cache[country_name]

            vals = {
                "name": name,
                "email": row["email"],
                "phone": row["phone"],
                "city": row["city"],
                "customer_rank": 1 if row["type"] == "customer" else 0,
                "supplier_rank": 1 if row["type"] == "supplier" else 0,
                "is_company": row["is_company"] == "1",
            }
            if country_id:
                vals["country_id"] = country_id

            cid = api.create("res.partner", vals)
            contact_map[name] = cid
            country_label = f", {country_name}" if country_id else ""
            print(f"   ✅ {name} ({row['type']}{country_label}, id={cid})")
    return contact_map


def seed_inventory(api, products_data, product_map):
    print("\n📊 Mengisi Stok Awal...")
    locations = api.search_read("stock.location", [("usage", "=", "internal")], fields=["id", "name"], limit=1)
    if not locations:
        print("   ⚠️  Tidak ada internal location, skip")
        return
    location_id = locations[0]["id"]
    print(f"   📍 Location: {locations[0]['name']} (id={location_id})")

    for row in products_data:
        if row["storable"] != "1":
            continue
        if row.get("type") == "manufacture":
            continue
        pid = product_map[row["name"]]
        qty = int(row["initial_stock"])
        try:
            qid = api.create("stock.quant", {
                "product_id": pid,
                "location_id": location_id,
                "inventory_quantity": qty,
            })
            api._call("stock.quant", "action_apply_inventory", [[qid]])
            print(f"   ✅ {row['name']}: {qty} unit")
        except xmlrpc.client.Fault:
            print(f"   ✅ {row['name']}: {qty} unit (applied)")


def seed_bom(api, bom_data, product_map):
    print("\n📐 Membuat Bill of Materials (Resep Jamu)...")
    try:
        api.search("mrp.bom", [], limit=1)
    except xmlrpc.client.Fault:
        print("   ⚠️  Modul Manufacturing belum di-install, skip BOM")
        return

    from collections import OrderedDict
    grouped = OrderedDict()
    for row in bom_data:
        product = row["product_name"]
        if product not in grouped:
            grouped[product] = []
        grouped[product].append({
            "component": row["component_name"],
            "qty": float(row["quantity"]),
        })

    count = 0
    for product_name, components in grouped.items():
        pid = product_map.get(product_name)
        if not pid:
            print(f"   ⚠️  {product_name} tidak ditemukan, skip")
            continue

        product = api.search_read("product.product", [("id", "=", pid)], fields=["product_tmpl_id"], limit=1)
        if not product:
            continue
        tmpl_id = product[0]["product_tmpl_id"][0]

        existing = api.search_read("mrp.bom", [("product_tmpl_id", "=", tmpl_id)], fields=["id"], limit=1)
        if existing:
            print(f"   ⏭️  BOM {product_name} (sudah ada)")
            count += 1
            continue

        bom_lines = []
        for comp in components:
            comp_id = product_map.get(comp["component"])
            if comp_id:
                bom_lines.append((0, 0, {
                    "product_id": comp_id,
                    "product_qty": comp["qty"],
                }))

        bom_id = api.create("mrp.bom", {
            "product_tmpl_id": tmpl_id,
            "product_id": pid,
            "product_qty": 1,
            "bom_line_ids": bom_lines,
        })
        count += 1
        comp_names = ", ".join(c["component"] for c in components)
        print(f"   ✅ {product_name} ← [{comp_names}]")

    print(f"   Total: {count} BOM")


SUPPLIER_MAP = {
    "Jahe Merah": "UD Tani Makmur Herbal",
    "Kencur": "UD Tani Makmur Herbal",
    "Kunyit": "UD Tani Makmur Herbal",
    "Beras Putih": "UD Tani Makmur Herbal",
    "Temulawak": "Koperasi Petani Jamu Ngemplak",
    "Temu Ireng": "Koperasi Petani Jamu Ngemplak",
    "Puyang": "Koperasi Petani Jamu Ngemplak",
    "Cabe Jawa": "CV Rempah Nusantara",
    "Kayu Manis": "CV Rempah Nusantara",
    "Serai": "CV Rempah Nusantara",
    "Asam Jawa": "CV Rempah Nusantara",
    "Daun Sirih": "CV Rempah Nusantara",
    "Gula Merah": "PT Gula Madu Sejahtera",
    "Gula Pasir": "PT Gula Madu Sejahtera",
    "Madu Murni": "Koperasi Madu Hutan Sumbawa",
    "Botol Kaca 250ml": "UD Kemasan Prima",
    "Label Sticker": "UD Kemasan Prima",
    "Tutup Botol": "UD Kemasan Prima",
    "Karton Dus 12pcs": "UD Kemasan Prima",
}


def seed_supply_chain(api, orders_data, bom_data, product_map, contact_map, cost_map):
    """Buat PO dan MO yang terhubung dengan sales orders.

    Alur: Sales Orders → hitung kebutuhan MO → buat MO → hitung bahan baku → buat PO
    Tanggal: PO (awal) → MO (tengah) → SO (akhir)
    """
    print("\n🔗 Membangun Supply Chain (Purchase → Manufacturing → Sales)...")

    try:
        api.search("mrp.production", [], limit=1)
    except xmlrpc.client.Fault:
        print("   ⚠️  Modul Manufacturing belum di-install, skip")
        return

    # 1. Parse BOM: {product_name: [(component_name, qty_per_unit), ...]}
    bom_map = {}
    for row in bom_data:
        product = row["product_name"]
        if product not in bom_map:
            bom_map[product] = []
        bom_map[product].append((row["component_name"], float(row["quantity"])))

    # 2. Hitung demand per bulan dari sales orders
    from collections import defaultdict
    monthly_demand = defaultdict(lambda: defaultdict(int))
    for row in orders_data:
        if row["order_type"] != "sales":
            continue
        month_key = row["date"][:7]
        monthly_demand[month_key][row["product_name"]] += int(row["quantity"])

    # 3. Buat Manufacturing Orders
    print("\n   🏭 Manufacturing Orders:")
    mo_count = 0
    all_raw_needs = {}

    for month in sorted(monthly_demand.keys()):
        year, mon = int(month[:4]), int(month[5:7])
        if mon > 1:
            mo_date = f"{year}-{mon-1:02d}-15"
        else:
            mo_date = f"{year-1}-12-15"

        for product_name, qty in sorted(monthly_demand[month].items()):
            pid = product_map.get(product_name)
            if not pid:
                continue

            mo_id = api.create("mrp.production", {
                "product_id": pid,
                "product_qty": qty,
                "date_start": f"{mo_date} 08:00:00",
            })
            api.safe_action("mrp.production", mo_id, "action_confirm")
            api.safe_action("mrp.production", mo_id, "action_assign")
            api.write("mrp.production", [mo_id], {"qty_producing": qty})
            api.safe_action("mrp.production", mo_id, "button_mark_production_as_done")

            mo_count += 1
            print(f"      ✅ {product_name} x{qty} ({mo_date}, Done)")

            if product_name in bom_map:
                for comp_name, qty_per_unit in bom_map[product_name]:
                    supplier = SUPPLIER_MAP.get(comp_name)
                    if supplier:
                        key = (month, supplier, comp_name)
                        all_raw_needs[key] = all_raw_needs.get(key, 0) + qty * qty_per_unit

    print(f"      Total: {mo_count} Manufacturing Orders")

    print("\n   📋 Purchase Orders (bahan baku):")
    supplier_monthly = defaultdict(lambda: defaultdict(float))
    for (month, supplier, comp_name), total_qty in all_raw_needs.items():
        supplier_monthly[(month, supplier)][comp_name] += total_qty

    po_count = 0
    for (month, supplier), materials in sorted(supplier_monthly.items()):
        partner_id = contact_map.get(supplier)
        if not partner_id:
            continue

        year, mon = int(month[:4]), int(month[5:7])
        prev_month = mon - 1 if mon > 1 else 12
        prev_year = year if mon > 1 else year - 1
        po_date = f"{prev_year}-{prev_month:02d}-01"

        order_lines = []
        for mat_name, qty in sorted(materials.items()):
            mat_id = product_map.get(mat_name)
            mat_cost = cost_map.get(mat_name, 0)
            if mat_id and qty > 0:
                order_lines.append((0, 0, {
                    "product_id": mat_id,
                    "product_qty": round(qty, 2),
                    "price_unit": mat_cost,
                }))

        if not order_lines:
            continue

        po_id = api.create("purchase.order", {
            "partner_id": partner_id,
            "order_line": order_lines,
        })
        api.action("purchase.order", po_id, "button_confirm")
        api.write("purchase.order", [po_id], {"date_order": f"{po_date} 09:00:00"})

        pickings = api.search_read("stock.picking", [("purchase_id", "=", po_id)], fields=["id", "state"])
        for picking in pickings:
            if picking["state"] not in ("done", "cancel"):
                api.validate_picking(picking["id"])

        mat_summary = ", ".join(f"{n} ({q:.0f})" for n, q in sorted(materials.items()))
        po_count += 1
        print(f"      ✅ {supplier} ({po_date}): {mat_summary}")

    print(f"      Total: {po_count} Purchase Orders")


def group_orders(orders_data, order_type):
    grouped = OrderedDict()
    for row in orders_data:
        if row["order_type"] != order_type:
            continue
        key = (row["partner_name"], row["date"], row["status"])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({
            "product_name": row["product_name"],
            "quantity": int(row["quantity"]),
        })
    return grouped


def seed_sales_orders(api, orders_data, product_map, contact_map, products_data):
    print("\n🛒 Membuat Sales Orders...")
    price_map = {row["name"]: float(row["sell_price"]) for row in products_data}
    grouped = group_orders(orders_data, "sales")
    count = 0

    for (partner_name, date_str, status), lines in grouped.items():
        count += 1
        partner_id = contact_map.get(partner_name)
        if not partner_id:
            print(f"   ⚠️  SO #{count} — {partner_name} tidak ditemukan, skip")
            continue

        existing = api.search_read(
            "sale.order",
            [("partner_id", "=", partner_id), ("name", "ilike", date_str)],
            fields=["id"], limit=1,
        )
        if existing:
            print(f"   ⏭️  SO #{count} — {partner_name} ({date_str}, sudah ada)")
            continue

        order_lines = []
        total = 0
        for line in lines:
            pid = product_map.get(line["product_name"])
            price = price_map.get(line["product_name"], 0)
            if not pid:
                continue
            order_lines.append((0, 0, {
                "product_id": pid,
                "product_uom_qty": line["quantity"],
                "price_unit": price,
            }))
            total += price * line["quantity"]

        order_id = api.create("sale.order", {
            "partner_id": partner_id,
            "order_line": order_lines,
        })

        if status in ("confirmed", "done", "paid"):
            api.action("sale.order", order_id, "action_confirm")
            api.write("sale.order", [order_id], {"date_order": f"{date_str} 10:00:00"})

        if status in ("done", "paid"):
            pickings = api.search_read("stock.picking", [("sale_id", "=", order_id)], fields=["id", "state"])
            for picking in pickings:
                if picking["state"] not in ("done", "cancel"):
                    api.validate_picking(picking["id"])

        if status == "paid":
            try:
                so = api.search_read("sale.order", [("id", "=", order_id)], fields=["name"], limit=1)
                inv_lines = []
                for line in lines:
                    pid = product_map.get(line["product_name"])
                    price = price_map.get(line["product_name"], 0)
                    if not pid:
                        continue
                    inv_lines.append((0, 0, {
                        "product_id": pid,
                        "quantity": line["quantity"],
                        "price_unit": price,
                    }))

                invoice_id = api.create("account.move", {
                    "move_type": "out_invoice",
                    "partner_id": partner_id,
                    "invoice_date": date_str,
                    "ref": so[0]["name"],
                    "invoice_line_ids": inv_lines,
                })
                api.safe_action("account.move", invoice_id, "action_post")

                journal = api.search_read("account.journal", [("type", "in", ["bank", "cash"])], fields=["id"], limit=1)
                if journal:
                    payment_id = api.create("account.payment", {
                        "payment_type": "inbound",
                        "partner_type": "customer",
                        "partner_id": partner_id,
                        "amount": total,
                        "journal_id": journal[0]["id"],
                        "date": date_str,
                    })
                    api.safe_action("account.payment", payment_id, "action_post")
            except xmlrpc.client.Fault:
                pass

        status_label = {"draft": "Draft", "confirmed": "Confirmed", "done": "Delivered", "paid": "Paid"}
        print(f"   ✅ SO #{count} — {partner_name} ({date_str}, {status_label.get(status, status)})")


def seed_purchase_orders(api, orders_data, product_map, contact_map, products_data):
    print("\n📋 Membuat Purchase Orders...")
    try:
        api.search("purchase.order", [], limit=1)
    except xmlrpc.client.Fault:
        print("   ⚠️  Modul Purchase belum di-install, skip")
        return

    cost_map = {row["name"]: float(row["cost_price"]) for row in products_data}
    grouped = group_orders(orders_data, "purchase")
    count = 0

    for (partner_name, date_str, status), lines in grouped.items():
        count += 1
        partner_id = contact_map.get(partner_name)
        if not partner_id:
            print(f"   ⚠️  PO #{count} — {partner_name} tidak ditemukan, skip")
            continue

        existing = api.search_read(
            "purchase.order",
            [("partner_id", "=", partner_id), ("name", "ilike", date_str)],
            fields=["id"], limit=1,
        )
        if existing:
            print(f"   ⏭️  PO #{count} — {partner_name} ({date_str}, sudah ada)")
            continue

        order_lines = []
        for line in lines:
            pid = product_map.get(line["product_name"])
            cost = cost_map.get(line["product_name"], 0)
            if not pid:
                continue
            order_lines.append((0, 0, {
                "product_id": pid,
                "product_qty": line["quantity"],
                "price_unit": cost,
            }))

        po_id = api.create("purchase.order", {
            "partner_id": partner_id,
            "order_line": order_lines,
        })

        if status in ("confirmed", "done"):
            api.action("purchase.order", po_id, "button_confirm")
            api.write("purchase.order", [po_id], {"date_order": f"{date_str} 09:00:00"})

        if status == "done":
            pickings = api.search_read("stock.picking", [("purchase_id", "=", po_id)], fields=["id", "state"])
            for picking in pickings:
                if picking["state"] not in ("done", "cancel"):
                    api.validate_picking(picking["id"])

        status_label = {"confirmed": "Confirmed", "done": "Received"}
        print(f"   ✅ PO #{count} — {partner_name} ({date_str}, {status_label.get(status, status)})")


REQUIRED_MODULES = [
    "sale_management",
    "stock",
    "account",
    "purchase",
    "mrp",
]


def install_modules(api):
    print("\n📦 Memeriksa modul yang diperlukan...")
    to_install = []
    for name in REQUIRED_MODULES:
        mods = api.search_read(
            "ir.module.module",
            [("name", "=", name)],
            fields=["id", "state", "shortdesc"],
            limit=1,
        )
        if not mods:
            print(f"   ⚠️  Modul {name} tidak ditemukan, skip")
            continue
        mod = mods[0]
        if mod["state"] == "installed":
            print(f"   ✅ {mod['shortdesc']} ({name})")
        else:
            to_install.append(mod["id"])
            print(f"   ⏳ {mod['shortdesc']} ({name}) — akan di-install")

    if not to_install:
        print("   Semua modul sudah ter-install!")
        return

    print(f"\n   Meng-install {len(to_install)} modul...")
    api.safe_action("ir.module.module", to_install, "button_immediate_install")

    for attempt in range(90):
        time.sleep(3)
        remaining = api.search_read(
            "ir.module.module",
            [("id", "in", to_install), ("state", "not in", ["installed"])],
            fields=["id", "state", "shortdesc"],
        )
        if not remaining:
            print("   ✅ Semua modul berhasil ter-install!")
            return

        states = set(r["state"] for r in remaining)
        if attempt % 10 == 0:
            print(f"   ⏳ Menunggu... ({(attempt+1)*3}s) [{', '.join(states)}]")

        if "to install" not in states and "installed" not in states:
            for r in remaining:
                if r["state"] not in ("to install", "installed"):
                    print(f"   ⚠️  {r['shortdesc']} stuck di '{r['state']}', mencoba ulang...")
                    api.safe_action("ir.module.module", [r["id"]], "button_immediate_install")

    print("   ⚠️  Timeout! Beberapa modul mungkin belum selesai install.")
    print("   Coba jalankan script lagi.")


def main():
    print("=" * 60)
    print("  🏭 Odoo Seeding — CV Jamu Sehat Nusantara")
    print("=" * 60)
    print(f"  URL:      {ODOO_URL}")
    print(f"  Database: {ODOO_DB}")
    print(f"  User:     {ODOO_USER}")
    print(f"  Data:     {DATA_DIR}")
    print("=" * 60)

    api = OdooAPI(ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD)
    api.authenticate()

    install_modules(api)

    products_data = read_csv("products.csv")
    contacts_data = read_csv("contacts.csv")
    orders_data = read_csv("orders.csv")
    bom_data = read_csv("bom.csv")

    cat_ids = seed_categories(api, products_data)
    product_map = seed_products(api, products_data, cat_ids)
    contact_map = seed_contacts(api, contacts_data)
    seed_inventory(api, products_data, product_map)
    seed_bom(api, bom_data, product_map)

    cost_map = {row["name"]: float(row["cost_price"]) for row in products_data}

    print("\n⏳ Membuat transaksi...")
    seed_sales_orders(api, orders_data, product_map, contact_map, products_data)
    seed_supply_chain(api, orders_data, bom_data, product_map, contact_map, cost_map)

    sales_count = len(group_orders(orders_data, "sales"))
    months = sorted(set(row["date"][:7] for row in orders_data if row["order_type"] == "sales"))

    print("\n" + "=" * 60)
    print("  ✅ SEEDING SELESAI!")
    print("=" * 60)
    print(f"  📁 Kategori:    {len(set(r['category'] for r in products_data))}")
    print(f"  📦 Produk:      {len(products_data)}")
    print(f"  👥 Kontak:      {len(contacts_data)}")
    print(f"  📐 BOM:         {len(set(r['product_name'] for r in bom_data))} resep")
    print(f"  🛒 Sales Order: {sales_count}")
    print(f"  📅 Periode:     {months[0]} s/d {months[-1]}")
    print("=" * 60)
    print(f"\n  Buka Odoo di: {ODOO_URL}\n")


if __name__ == "__main__":
    main()
