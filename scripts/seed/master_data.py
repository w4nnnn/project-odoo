import xmlrpc.client

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
    location_id = locations[0]["id"] if isinstance(locations[0], dict) else False
    if not location_id:
        return
    print(f"   📍 Location: {locations[0].get('name')} (id={location_id})")

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
        except xmlrpc.client.Fault as e:
            if "cannot marshal None unless allow_none is enabled" not in str(e):
                print(f"   ⚠️  {row['name']}: {qty} unit (Error: {e})")
            else:
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