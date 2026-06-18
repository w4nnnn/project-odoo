"""
Generator script — membuat orders.csv dengan data transaksi realistis
untuk CV Jamu Sehat Nusantara (Jan 2025 - Jun 2026)

Jalankan: python data/generate_orders.py
"""
import csv
import os
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SALES_CUSTOMERS = [
    ("Apotek Kimia Farma Diponegoro", "pharmacy"),
    ("Apotek Century Solo", "pharmacy"),
    ("Superindo Ahmad Yani", "supermarket"),
    ("Transmart Cirebon", "supermarket"),
    ("CV Distribusi Herbal Nusantara", "distributor"),
    ("UD Sehat Sentosa", "shop"),
    ("Apotek K-24 Gatot Subroto", "pharmacy"),
    ("Apotek Roxy Medika", "pharmacy"),
    ("Guardian Health Sudirman", "pharmacy"),
    ("Apotek K-24 Malioboro", "pharmacy"),
    ("Watson Thamrin City", "pharmacy"),
    ("Hypermart BSD City", "supermarket"),
    ("Carrefour Surabaya", "supermarket"),
    ("Lotte Mart Bali", "supermarket"),
    ("Giant Ekstra Bekasi", "supermarket"),
    ("Toko Herbal Sehat Alami", "shop"),
    ("Warung Jamu Mbah Joyo", "shop"),
    ("Toko Obat Sin Tjong", "shop"),
    ("Rita Hartono", "individual"),
    ("Agus Prasetyo", "individual"),
    ("Nurul Hidayah", "individual"),
    ("PT Herbal Asia Trading", "distributor"),
    ("Singapore Herbal Pte Ltd", "export"),
    ("Herbal Malaysia Sdn Bhd", "export"),
]

PURCHASE_SUPPLIERS = [
    "UD Tani Makmur Herbal",
    "Koperasi Petani Jamu Ngemplak",
    "CV Rempah Nusantara",
    "PT Gula Madu Sejahtera",
    "UD Kemasan Prima",
    "PT Bumbu Rempah Jatim",
    "Koperasi Madu Hutan Sumbawa",
    "UD Plastik Nusantara",
]

JAMU_PRODUCTS = [
    ("Jamu Beras Kencur 250ml", 18000),
    ("Jamu Kunyit Asam 250ml", 18000),
    ("Jamu Temulawak 250ml", 20000),
    ("Jamu Cabe Puyang 250ml", 22000),
    ("Jamu Uyup-uyup 250ml", 20000),
    ("Tolak Angin Sachet", 5000),
]

RAW_MATERIALS = [
    ("UD Tani Makmur Herbal", [("Jahe Merah", 28000), ("Kencur", 22000), ("Kunyit", 18000), ("Beras Putih", 10000)]),
    ("Koperasi Petani Jamu Ngemplak", [("Temulawak", 20000), ("Temu Ireng", 18000), ("Puyang", 25000)]),
    ("CV Rempah Nusantara", [("Cabe Jawa", 35000), ("Kayu Manis", 30000), ("Serai", 10000), ("Asam Jawa", 16000), ("Daun Sirih", 15000)]),
    ("PT Gula Madu Sejahtera", [("Gula Merah", 14000), ("Gula Pasir", 12000), ("Madu Murni", 55000)]),
    ("UD Kemasan Prima", [("Botol Kaca 250ml", 2000), ("Label Sticker", 200), ("Tutup Botol", 400), ("Karton Dus 12pcs", 5000)]),
    ("PT Bumbu Rempah Jatim", [("Jahe Merah", 28000), ("Kunyit", 18000), ("Temulawak", 20000)]),
    ("Koperasi Madu Hutan Sumbawa", [("Madu Murni", 55000)]),
    ("UD Plastik Nusantara", [("Botol Kaca 250ml", 2000), ("Tutup Botol", 400)]),
]

QTY_RANGE = {
    "pharmacy": (12, 36),
    "supermarket": (24, 60),
    "distributor": (48, 120),
    "shop": (10, 30),
    "individual": (3, 12),
    "export": (60, 150),
}

def pick_products(customer_type, seed):
    import random
    random.seed(seed)
    n = random.choice([2, 3]) if customer_type in ("pharmacy", "supermarket", "distributor", "export") else random.choice([1, 2])
    products = random.sample(JAMU_PRODUCTS, min(n, len(JAMU_PRODUCTS)))
    lo, hi = QTY_RANGE.get(customer_type, (5, 20))
    return [(p[0], random.randint(lo, hi)) for p in products]

def get_status(order_date, ref_date):
    diff = (ref_date - order_date).days
    if diff > 90:
        return "paid"
    elif diff > 45:
        return "done"
    elif diff > 21:
        return "confirmed"
    else:
        return "draft"

def generate_sales_dates():
    import random
    random.seed(42)
    dates = []
    start = date(2025, 1, 6)
    end = date(2026, 6, 14)
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=random.choice([3, 4, 5, 7]))
    return dates

def generate_purchase_dates():
    import random
    random.seed(99)
    dates = []
    start = date(2024, 12, 15)
    end = date(2026, 6, 1)
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=random.choice([21, 30, 45, 60]))
    return dates

def main():
    ref_date = date(2026, 6, 15)
    rows = []

    sales_dates = generate_sales_dates()
    import random
    random.seed(77)
    for i, d in enumerate(sales_dates):
        customer_name, ctype = random.choice(SALES_CUSTOMERS)
        products = pick_products(ctype, seed=i * 31 + 7)
        status = get_status(d, ref_date)
        for prod_name, qty in products:
            rows.append(("sales", customer_name, prod_name, qty, d.isoformat(), status))

    purchase_dates = generate_purchase_dates()
    random.seed(88)
    for i, d in enumerate(purchase_dates):
        supplier_name, materials = random.choice(RAW_MATERIALS)
        n = random.choice([2, 3])
        selected = random.sample(materials, min(n, len(materials)))
        status = get_status(d, ref_date)
        for mat_name, mat_price in selected:
            qty = random.randint(30, 150)
            rows.append(("purchase", supplier_name, mat_name, qty, d.isoformat(), status))

    rows.sort(key=lambda r: r[4])

    filepath = os.path.join(SCRIPT_DIR, "orders.csv")
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["order_type", "partner_name", "product_name", "quantity", "date", "status"])
        for row in rows:
            writer.writerow(row)

    sales = sum(1 for r in rows if r[0] == "sales")
    purchases = sum(1 for r in rows if r[0] == "purchase")
    print(f"Generated {len(rows)} order lines:")
    print(f"   Sales lines:    {sales}")
    print(f"   Purchase lines: {purchases}")
    print(f"   Date range:     {rows[0][4]} to {rows[-1][4]}")
    print(f"   Written to:     {filepath}")

if __name__ == "__main__":
    main()
