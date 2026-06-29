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
└── scripts/
    └── seed/                 # Script seeding otomatis berbasis Python
        ├── api.py            # Odoo API (koneksi & fungsi CRUD/Action)
        ├── main.py           # Eksekutor rantai transaksi (PO, MO, SO) & master data
        └── utils.py          # Helper function
```

## Quick Start

### 1. Build & Jalankan

```bash
docker compose build
docker compose up -d
```

> Build pertama kali ~2-3 menit (install wkhtmltopdf + imgkit).

### 2. Jalankan Seeding Script

Kini tidak perlu membuat database secara manual, jalankan perintah di bawah ini dan skrip otomatis mengecek serta membangun databasenya.

```bash
cd scripts/seed
python3 main.py
```

Script akan otomatis:
1. **Membuat Database**: Membuat database bernama `odoo` jika belum ada.
2. **Install Modul**: Menginstal modul Sales, Inventory, Invoicing (Account), Purchase, Manufacturing, serta _addon custom_ Premium Home Menu (`custom_home_menu`).
3. **Membuat Master Data**: Menginjeksi Pelanggan (terfokus di Jawa Timur), Vendor (Pemasok herbal di Jawa Timur), Kategori Produk, dan daftar produk (Jamu & Bahan Baku).
4. **Membuat BOM (Resep Jamu)**: Mendaftarkan Bill of Materials untuk proses pabrikasi jamu.
5. **Membuat Rantai Transaksi (Supply Chain)**: Membuat Purchase Order -> Material Receipt -> Manufacturing Order -> Sales Order -> Delivery Order yang tersebar ke masa lalu secara bertahap menggunakan _backdating_ acak selama beberapa bulan ke belakang.

### Supply Chain Terhubung

```
📋 Purchase Order      🏭 Manufacturing      🛒 Sales Order
(beli bahan baku)      (produksi jamu)        (jual ke customer)
────────────────       ────────────────       ────────────────
Supplier → bahan       BOM → jamu jadi        Customer ← jamu
```

## Data Seeding

### Kontak

Data fokus untuk regional Jawa Timur:
- **Pelanggan**: Warung Jamu Mbah Joyo (Sidoarjo), Apotek Sehat (Surabaya), Toko Herbal Nusantara (Malang), Minimarket Segar (Pasuruan), Klinik Berkah (Gresik).
- **Vendor**: UD Tani Makmur (Rempah - Mojokerto), Pabrik Kemasan Botol (Sidoarjo), PT Gula Madu Sejahtera (Batu).

### Produk & BOM (Resep)

- **Bahan Baku**: Jahe Merah, Kunyit, Beras Putih, Kencur, Gula Merah, Botol Kaca 250ml, Label Sticker.
- **Jamu Jadi**: 
  - Jamu Jahe Merah 250ml
  - Jamu Kunyit Asam 250ml
  - Jamu Beras Kencur 250ml

## Konfigurasi

### Koneksi Script

Anda dapat mengontrol kredenisal _seeding_ skrip melalui Environment Variable (`export ODOO_USER="..."`) atau mengubah nilainya langsung di bagian atas `scripts/seed/main.py`:
```python
ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")
```

### Ubah Master Password Odoo Docker

Edit `config/odoo.conf`:
```ini
admin_passwd = password_baru
```

## Troubleshooting

### Reset semua data

Jika Anda ingin membersihkan seluruh data secara total dan mengulang simulasi:
```bash
docker compose down -v
docker compose up -d
```
Lalu jalankan ulang `python3 scripts/seed/main.py`.

### Rebuild Docker image

```bash
docker compose up -d --build
```

### Cek logs

```bash
docker logs -f odoo-web     # Log Odoo
docker logs -f odoo-db      # Log PostgreSQL
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
