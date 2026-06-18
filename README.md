# CV Jamu Sehat Nusantara — Odoo ERP

Setup Odoo 19 ERP dengan Docker untuk perusahaan manufaktur jamu tradisional. Termasuk script seeding otomatis untuk mengisi data transaksi realistis (Purchase → Manufacturing → Sales).

## Struktur Folder

```
odoo/
├── docker-compose.yml        # Docker Compose config
├── Dockerfile                # Custom image (imgkit + wkhtmltopdf)
├── .env                      # Environment variables
├── config/
│   └── odoo.conf             # Konfigurasi Odoo
├── addons/                   # Custom modules (taruh di sini)
├── data/
│   ├── products.csv          # Bahan baku, kemasan, produk jadi
│   ├── contacts.csv          # Customer & supplier (dengan country)
│   ├── orders.csv            # Sales & purchase orders
│   ├── bom.csv               # Bill of Materials (resep jamu)
│   └── generate_orders.py    # Generator untuk orders.csv
└── seed_odoo.py              # Script seeding otomatis
```

## Quick Start

### 1. Build & Jalankan

```bash
docker compose build
docker compose up -d
```

> Build pertama kali ~2-3 menit (install wkhtmltopdf + imgkit).

### 2. Buat Database

Buka `http://localhost:8069/web/database/manager`:
- **Master Password**: `admin` (lihat `config/odoo.conf`)
- **Database Name**: `odoo_prod` (sesuaikan di `seed_odoo.py`)
- **Email / Password**: untuk login admin

### 3. Jalankan Seeding Script

```bash
python seed_odoo.py
```

Script akan otomatis:
1. Install modul: Sales, Inventory, Purchase, Manufacturing, Invoicing
2. Buat kategori, produk (bahan baku + jamu jadi), dan kontak
3. Isi stok bahan baku & kemasan
4. Buat BOM (resep jamu)
5. Buat Sales Orders dari data CSV
6. Buat Manufacturing Orders (tanggal sebelum sales)
7. Buat Purchase Orders (tanggal sebelum manufacturing)

### Supply Chain Terhubung

```
📋 Purchase Order      🏭 Manufacturing      🛒 Sales Order
(beli bahan baku)      (produksi jamu)        (jual ke customer)
────────────────       ────────────────       ────────────────
Supplier → bahan       BOM → jamu jadi        Customer ← jamu
Tanggal: awal          Tanggal: tengah        Tanggal: akhir

Contoh (penjualan Januari 2025):
  2024-12-01  PO beli kencur, gula merah, botol
  2024-12-15  MO produksi Jamu Beras Kencur x50
  2025-01-06  SO jual ke Apotek Kimia Farma x24
```

## Data Seeding

### Produk

| Kategori | Jumlah | Contoh |
|---|---|---|
| Bahan Baku Herbal | 15 | Jahe Merah, Kencur, Kunyit, Temulawak |
| Kemasan | 4 | Botol Kaca 250ml, Label, Tutup Botol |
| Jamu Jadi | 6 | Beras Kencur, Kunyit Asam, Temulawak, Cabe Puyang, Uyup-uyup, Tolak Angin |

### BOM (Resep)

```
Jamu Beras Kencur  ← Kencur + Beras + Gula Merah + Botol + Label + Tutup
Jamu Kunyit Asam   ← Kunyit + Asam Jawa + Gula Pasir + Botol + Label + Tutup
Jamu Temulawak     ← Temulawak + Gula Merah + Madu + Botol + Label + Tutup
Jamu Cabe Puyang   ← Cabe Jawa + Puyang + Gula Merah + Botol + Label + Tutup
Jamu Uyup-uyup     ← Temu Ireng + Daun Sirih + Serai + Gula Merah + Botol + Label + Tutup
Tolak Angin Sachet ← Jahe Merah + Kayu Manis + Madu + Gula Pasir
```

### Kontak

- **24 Customer**: Apotek (Kimia Farma, Century, K-24, Guardian, Watson, Roxy), Supermarket (Superindo, Transmart, Hypermart, Carrefour, Lotte Mart, Giant), Distributor, Toko herbal, Individu, Export (Singapore, Malaysia)
- **8 Supplier**: Petani herbal, koperasi, distributor rempah, supplier gula/madu, supplier kemasan

### Transaksi

- **95 Sales Order lines** — Jan 2025 s/d Jun 2026
- **31 Purchase Order lines** — terhubung dengan manufacturing
- **Manufacturing Orders** — otomatis dari demand sales

## Edit Data

Semua data ada di file CSV folder `data/`. Edit pakai Excel/Google Sheets lalu jalankan ulang script.

### Regenerate Orders

```bash
python data/generate_orders.py    # Generate orders.csv baru
python seed_odoo.py               # Jalankan seeding
```

## Konfigurasi

### Koneksi Script

Edit di `seed_odoo.py`:
```python
ODOO_URL = "http://localhost:8069"
ODOO_DB = "odoo_prod"
ODOO_USER = "admin@odoo.com"
ODOO_PASSWORD = "admin123"
```

### Environment Variables

Edit `.env`:

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `odoo` | Username PostgreSQL |
| `POSTGRES_PASSWORD` | `odoo` | Password PostgreSQL |
| `POSTGRES_DB` | `postgres` | Nama database PostgreSQL |
| `ODOO_PORT` | `8069` | Port akses Odoo |
| `ODOO_LONGPOLLING_PORT` | `8072` | Port long polling |

### Ubah Master Password

Edit `config/odoo.conf`:
```ini
admin_passwd = password_baru
```

## Troubleshooting

### Reset semua data

```bash
docker compose down
docker volume rm odoo_odoo-db-data odoo_odoo-web-data
docker compose up -d
```

### Rebuild Docker image

```bash
docker compose build
docker compose up -d
```

### Module tidak muncul

```bash
docker compose restart web
# Lalu di Odoo: Settings → Activate Developer Mode → Apps → Update Apps List
```

### Cek logs

```bash
docker compose logs -f web     # Log Odoo
docker compose logs -f db      # Log PostgreSQL
```

## Backup & Restore

```bash
# Backup
docker exec odoo-db pg_dump -U odoo nama_database > backup.sql

# Restore
cat backup.sql | docker exec -i odoo-db psql -U odoo nama_database
```

## Support

- [Odoo 19 Documentation](https://www.odoo.com/documentation/19.0/)
- [Docker Odoo Image](https://hub.docker.com/_/odoo)
- [Odoo External API](https://www.odoo.com/documentation/19.0/developer/reference/external_rpc_api.html)
