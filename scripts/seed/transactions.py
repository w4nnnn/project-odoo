import xmlrpc.client
from collections import OrderedDict
from collections import defaultdict

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
    print("\n🔗 Membangun Supply Chain (Purchase → Manufacturing → Sales)...")

    try:
        api.search("mrp.production", [], limit=1)
    except xmlrpc.client.Fault:
        print("   ⚠️  Modul Manufacturing belum di-install, skip")
        return

    bom_map = {}
    for row in bom_data:
        product = row["product_name"]
        if product not in bom_map:
            bom_map[product] = []
        bom_map[product].append((row["component_name"], float(row["quantity"])))

    monthly_demand = defaultdict(lambda: defaultdict(int))
    for row in orders_data:
        if row["order_type"] != "sales":
            continue
        month_key = row["date"][:7]
        monthly_demand[month_key][row["product_name"]] += int(row["quantity"])

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
            if isinstance(picking, dict) and picking.get("state") not in ("done", "cancel"):
                api.validate_picking(picking.get("id"))

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
            if isinstance(pickings, list):
                for picking in pickings:
                    if isinstance(picking, dict) and picking.get("state") not in ("done", "cancel"):
                        api.validate_picking(picking.get("id"))

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
            if isinstance(pickings, list):
                for picking in pickings:
                    if isinstance(picking, dict) and picking.get("state") not in ("done", "cancel"):
                        api.validate_picking(picking.get("id"))

        status_label = {"confirmed": "Confirmed", "done": "Received"}
        print(f"   ✅ PO #{count} — {partner_name} ({date_str}, {status_label.get(status, status)})")