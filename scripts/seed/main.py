import os
from api import OdooAPI
from utils import read_csv
from master_data import seed_categories, seed_products, seed_contacts, seed_inventory, seed_bom
from transactions import seed_sales_orders, seed_supply_chain, group_orders

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")

def main():
    print("=" * 60)
    print("  🏭 Odoo Seeding — CV Jamu Sehat Nusantara")
    print("=" * 60)
    print(f"  URL:      {ODOO_URL}")
    print(f"  Database: {ODOO_DB}")
    print(f"  User:     {ODOO_USER}")
    print("=" * 60)

    api = OdooAPI(ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD)
    api.create_database_if_not_exists()
    api.authenticate()

    api.install_required_modules()

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