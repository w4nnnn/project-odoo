import os
import random
from datetime import datetime, timedelta
from api import OdooAPI

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")

def main():
    print("=" * 60)
    print("  🏭 Odoo Seeding — Data Terhubung Massal (Chain)")
    print("=" * 60)

    api = OdooAPI(ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD)
    api.create_database_if_not_exists()
    api.authenticate()
    api.install_required_modules()

    # === Mengatur Konfigurasi Mata Uang (IDR) ===
    print("\n⚙️ Mengatur Mata Uang Perusahaan ke IDR...")
    # Jika tidak mencari nama, Odoo sering memakai 'name' sebagai simbol, jadi kita cari berdasar nama
    idr_currency = api.search_read('res.currency', [('name', '=', 'IDR')], fields=['id', 'active'], limit=1)
    # Tapi karena IDR seringkali tidak aktif (active=False) secara default, kita harus matikan filter active
    if not idr_currency:
        # Search secara force mengabaikan rule active
        idr_currency_search = api.models.execute_kw(api.db, api.uid, api.password, 'res.currency', 'search_read', 
            [[('name', '=', 'IDR'), '|', ('active', '=', True), ('active', '=', False)]], 
            {'fields': ['id', 'active'], 'limit': 1})
        if idr_currency_search:
            idr_currency = idr_currency_search
            
    if idr_currency and isinstance(idr_currency, list) and isinstance(idr_currency[0], dict):
        idr_id = idr_currency[0]['id']
        # Aktifkan IDR jika masih inactive
        if not idr_currency[0].get('active'):
            api.write('res.currency', [idr_id], {'active': True})
            print(f"   ✅ Mengaktifkan mata uang IDR (ID: {idr_id}).")
        
        company = api.search_read('res.company', [], limit=1)
        if company and isinstance(company, list) and isinstance(company[0], dict):
            try:
                api.write('res.company', [company[0]['id']], {'currency_id': idr_id})
                print(f"   ✅ Mata uang perusahaan berhasil diubah ke IDR.")
            except Exception as e:
                print(f"   ⚠️ Mata uang tidak bisa diubah (Mungkin sudah IDR, atau sudah ada transaksi).")
                
        # Update semua Pricelist (Daftar Harga) yang ada ke IDR agar Sales order menggunakan IDR
        pricelists = api.search_read('product.pricelist', [], fields=['id', 'name'])
        if pricelists and isinstance(pricelists, list):
            try:
                pl_ids = [pl['id'] for pl in pricelists if isinstance(pl, dict) and 'id' in pl]
                if pl_ids:
                    api.write('product.pricelist', pl_ids, {'currency_id': idr_id})
                    print(f"   ✅ Berhasil mengubah {len(pl_ids)} Pricelist ke IDR.")
            except Exception as e:
                print(f"   ⚠️ Tidak dapat mengubah mata uang Pricelist (biasanya terkunci jika ada transaksi): {e}")
    else:
        print("   ⚠️ Mata uang IDR tidak ditemukan!")

    # === 1. Membuat Master Data (Pelanggan, Vendor, Barang) ===
    print("\n1. Membuat Master Data (Pelanggan, Vendor, dan Barang)...")
    
    # Pelanggan (Fokus Jawa Timur)
    customers = []
    for name, city in [
        ('Warung Jamu Mbah Joyo', 'Sidoarjo'), 
        ('Apotek Sehat', 'Surabaya'), 
        ('Toko Herbal Nusantara', 'Malang'), 
        ('Minimarket Segar', 'Pasuruan'), 
        ('Klinik Berkah', 'Gresik')
    ]:
        customers.append(api.create('res.partner', {
            'name': name, 'city': city, 'country_id': 100, # 100 is typically Indonesia in Odoo res.country
            'is_company': True, 'customer_rank': 1
        }))
        
    # Vendor (Fokus Jawa Timur)
    vendors = {
        'rempah': api.create('res.partner', {
            'name': 'UD Tani Makmur (Rempah)', 'city': 'Mojokerto', 'country_id': 100, 
            'is_company': True, 'supplier_rank': 1
        }),
        'kemasan': api.create('res.partner', {
            'name': 'Pabrik Kemasan Botol', 'city': 'Sidoarjo', 'country_id': 100, 
            'is_company': True, 'supplier_rank': 1
        }),
        'pemanis': api.create('res.partner', {
            'name': 'PT Gula Madu Sejahtera', 'city': 'Batu', 'country_id': 100, 
            'is_company': True, 'supplier_rank': 1
        })
    }

    # Kategori Produk
    categ_bahan = api.create('product.category', {'name': 'Bahan Baku Herbal'})
    categ_kemasan = api.create('product.category', {'name': 'Kemasan'})
    categ_jamu = api.create('product.category', {'name': 'Jamu Jadi'})

    # Bahan Baku
    raw_materials = {
        'Jahe Merah': api.create('product.product', {'name': 'Jahe Merah', 'type': 'consu', 'categ_id': categ_bahan, 'is_storable': True, 'standard_price': 25000}),
        'Kunyit': api.create('product.product', {'name': 'Kunyit', 'type': 'consu', 'categ_id': categ_bahan, 'is_storable': True, 'standard_price': 15000}),
        'Beras': api.create('product.product', {'name': 'Beras Putih', 'type': 'consu', 'categ_id': categ_bahan, 'is_storable': True, 'standard_price': 12000}),
        'Kencur': api.create('product.product', {'name': 'Kencur', 'type': 'consu', 'categ_id': categ_bahan, 'is_storable': True, 'standard_price': 20000}),
        'Gula Merah': api.create('product.product', {'name': 'Gula Merah', 'type': 'consu', 'categ_id': categ_bahan, 'is_storable': True, 'standard_price': 18000}),
        'Botol 250ml': api.create('product.product', {'name': 'Botol Kaca 250ml', 'type': 'consu', 'categ_id': categ_kemasan, 'is_storable': True, 'standard_price': 2000}),
        'Label': api.create('product.product', {'name': 'Label Sticker', 'type': 'consu', 'categ_id': categ_kemasan, 'is_storable': True, 'standard_price': 500})
    }

    # Produk Jadi & BoM (Resep)
    jamu_products = [
        {'name': 'Jamu Jahe Merah 250ml', 'price': 18000, 'recipe': {'Jahe Merah': 0.1, 'Gula Merah': 0.05, 'Botol 250ml': 1, 'Label': 1}},
        {'name': 'Jamu Kunyit Asam 250ml', 'price': 15000, 'recipe': {'Kunyit': 0.1, 'Gula Merah': 0.05, 'Botol 250ml': 1, 'Label': 1}},
        {'name': 'Jamu Beras Kencur 250ml', 'price': 17000, 'recipe': {'Beras': 0.05, 'Kencur': 0.05, 'Gula Merah': 0.05, 'Botol 250ml': 1, 'Label': 1}},
    ]

    finished_goods = {}
    print("\n2. Membuat Bill of Materials / Resep Jamu...")
    for j in jamu_products:
        pid = api.create('product.product', {'name': j['name'], 'type': 'consu', 'categ_id': categ_jamu, 'is_storable': True, 'list_price': j['price']})
        finished_goods[j['name']] = pid
        
        prod_data = api.search_read('product.product', [('id', '=', pid)], fields=['product_tmpl_id'], limit=1)[0]
        tmpl_id = prod_data['product_tmpl_id'][0] if isinstance(prod_data, dict) and 'product_tmpl_id' in prod_data else False
        
        if tmpl_id:
            bom_id = api.create('mrp.bom', {'product_tmpl_id': tmpl_id, 'product_qty': 1.0, 'type': 'normal'})
            for comp_name, qty in j['recipe'].items():
                api.create('mrp.bom.line', {'bom_id': bom_id, 'product_id': raw_materials[comp_name], 'product_qty': qty})
            print(f"   ✅ BoM {j['name']} dibuat.")

    # Helper function untuk Receipt / Delivery
    def validate_picking(picking_id, done_date):
        # Update tanggal pada moves SEBELUM validasi
        move_lines = api.search_read('stock.move.line', [('picking_id', '=', picking_id)], fields=['id', 'quantity_product_uom'])
        if isinstance(move_lines, list):
            for ml in move_lines:
                if isinstance(ml, dict):
                    api.write('stock.move.line', [ml['id']], {'quantity': ml['quantity_product_uom'], 'date': done_date})
        
        moves = api.search_read('stock.move', [('picking_id', '=', picking_id)], fields=['id', 'product_uom_qty'])
        if isinstance(moves, list):
            for mv in moves:
                if isinstance(mv, dict):
                    api.write('stock.move', [mv['id']], {'quantity': mv['product_uom_qty'], 'date': done_date})
                    
        # Validasi
        api.safe_action('stock.picking', picking_id, 'button_validate')
        
        # Set tanggal SELURUH dokumen setelah validasi agar tidak diremote Odoo menjadi 'sekarang'
        api.write('stock.picking', [picking_id], {'date_done': done_date, 'scheduled_date': done_date})
        if isinstance(moves, list):
            for mv in moves:
                if isinstance(mv, dict):
                    api.write('stock.move', [mv['id']], {'date': done_date})
        if isinstance(move_lines, list):
            for ml in move_lines:
                if isinstance(ml, dict):
                    api.write('stock.move.line', [ml['id']], {'date': done_date})

    # === LOOP TRANSAKSI (30 Hari Terakhir) ===
    print("\n⏳ Membangun Rantai Transaksi Massal (PO -> MO -> SO)...")
    today = datetime.now()
    
    total_po, total_mo, total_so = 0, 0, 0
    
    # Kita buat simulasi 10 "Batch/Siklus" dalam 60 hari terakhir
    for i in range(10):
        # Tentukan titik waktu untuk siklus ini
        days_ago = 60 - (i * 6)  # siklus per 6 hari
        cycle_date = today - timedelta(days=days_ago)
        
        po_date = (cycle_date - timedelta(days=2)).strftime('%Y-%m-%d 09:00:00')
        receipt_date = (cycle_date - timedelta(days=1)).strftime('%Y-%m-%d 10:00:00')
        mo_start = cycle_date.strftime('%Y-%m-%d 08:00:00')
        mo_end = (cycle_date + timedelta(hours=8)).strftime('%Y-%m-%d 16:00:00')
        so_date = (cycle_date + timedelta(days=1)).strftime('%Y-%m-%d 11:00:00')
        delivery_date = (cycle_date + timedelta(days=2)).strftime('%Y-%m-%d 14:00:00')

        # --- A. Pengadaan (PO) ---
        # Setiap siklus pesan random jumlah bahan baku
        vendor_orders = {
            vendors['rempah']: [raw_materials['Jahe Merah'], raw_materials['Kunyit'], raw_materials['Kencur']],
            vendors['kemasan']: [raw_materials['Botol 250ml'], raw_materials['Label']],
            vendors['pemanis']: [raw_materials['Gula Merah'], raw_materials['Beras']]
        }
        
        for vendor_id, items in vendor_orders.items():
            po_id = api.create('purchase.order', {'partner_id': vendor_id, 'date_order': po_date})
            for prod_id in items:
                qty = random.randint(100, 500) if prod_id not in [raw_materials['Botol 250ml'], raw_materials['Label']] else random.randint(1000, 3000)
                price = 1000 # dummy default
                api.create('purchase.order.line', {'order_id': po_id, 'product_id': prod_id, 'product_qty': qty, 'price_unit': price})
            api.safe_action('purchase.order', po_id, 'button_confirm')
            api.write('purchase.order', [po_id], {'date_approve': po_date})
            
            po_results = api.search_read('purchase.order', [('id', '=', po_id)], fields=['picking_ids'], limit=1)
            if po_results and isinstance(po_results, list):
                po_res = po_results[0]
                if isinstance(po_res, dict) and 'picking_ids' in po_res:
                    for pick_id in po_res['picking_ids']:
                        validate_picking(pick_id, receipt_date)
            total_po += 1

        # --- B. Produksi (MO) ---
        # Produksi 1-3 jenis jamu tiap siklus
        for jamu in random.sample(jamu_products, random.randint(1, 3)):
            prod_qty = random.randint(50, 200)
            jamu_pid = finished_goods[jamu['name']]
            
            prod_data_res = api.search_read('product.product', [('id', '=', jamu_pid)], fields=['uom_id'], limit=1)
            if not prod_data_res or not isinstance(prod_data_res, list):
                continue
            prod_data = prod_data_res[0]
            if isinstance(prod_data, dict):
                uom_id = prod_data['uom_id'][0] if 'uom_id' in prod_data else False
            else:
                uom_id = False
            
            bom_id_res = api.search_read('mrp.bom', [('product_id', '=', False), ('product_tmpl_id.product_variant_ids', '=', jamu_pid)], fields=['id'], limit=1)
            if not bom_id_res:
                bom_id_res = api.search_read('mrp.bom', [('product_id', '=', jamu_pid)], fields=['id'], limit=1)
            if bom_id_res and isinstance(bom_id_res, list):
                b_res = bom_id_res[0]
                b_id = b_res['id'] if isinstance(b_res, dict) and 'id' in b_res else False
            else:
                b_id = False

            if not b_id: continue

            mo_id = api.create('mrp.production', {
                'product_id': jamu_pid, 'product_qty': prod_qty, 'product_uom_id': uom_id,
                'bom_id': b_id, 'date_start': mo_start,
            })
            api.action('mrp.production', mo_id, 'action_confirm')
            api.action('mrp.production', mo_id, 'action_assign')
            api.write('mrp.production', [mo_id], {'qty_producing': prod_qty})
            
            mo_res = api.search_read('mrp.production', [('id', '=', mo_id)], fields=['move_raw_ids'], limit=1)
            if mo_res and isinstance(mo_res, list) and isinstance(mo_res[0], dict) and 'move_raw_ids' in mo_res[0]:
                for m_id in mo_res[0].get('move_raw_ids', []):
                    m_res_line = api.search_read('stock.move', [('id', '=', m_id)], fields=['product_uom_qty'], limit=1)
                    if m_res_line and isinstance(m_res_line, list) and isinstance(m_res_line[0], dict):
                        api.write('stock.move', [m_id], {'quantity': m_res_line[0].get('product_uom_qty', 0), 'picked': True, 'date': mo_end})

            try:
                api.action('mrp.production', mo_id, 'button_mark_done')
                api.write('mrp.production', [mo_id], {'date_finished': mo_end})
                f_moves = api.search_read('stock.move', [('production_id', '=', mo_id)], fields=['id'])
                if isinstance(f_moves, list):
                    for fm in f_moves:
                        if isinstance(fm, dict):
                            api.write('stock.move', [fm['id']], {'date': mo_end})
                total_mo += 1
            except Exception:
                pass # skip jika bahan baku kurang

        # --- C. Penjualan (SO) ---
        # Buat 2-5 pesanan dari pelanggan secara acak
        for _ in range(random.randint(2, 5)):
            cust_id = random.choice(customers)
            # Buat SO dengan backdate
            so_id = api.create('sale.order', {'partner_id': cust_id, 'date_order': so_date})
            
            for jamu in random.sample(jamu_products, random.randint(1, 2)):
                api.create('sale.order.line', {
                    'order_id': so_id, 'product_id': finished_goods[jamu['name']],
                    'product_uom_qty': random.randint(10, 50), 'price_unit': jamu['price'],
                })
            
            api.safe_action('sale.order', so_id, 'action_confirm')
            # Set ulang date_order setelah confirm karena Odoo sering me-reset ke hari ini saat confirm
            api.write('sale.order', [so_id], {'date_order': so_date})
            
            so_res = api.search_read('sale.order', [('id', '=', so_id)], fields=['picking_ids'], limit=1)
            if so_res and isinstance(so_res, list) and isinstance(so_res[0], dict) and 'picking_ids' in so_res[0]:
                for pick_id in so_res[0].get('picking_ids', []):
                    api.safe_action('stock.picking', pick_id, 'action_assign')
                    validate_picking(pick_id, delivery_date)
            total_so += 1

        print(f"   🔄 Siklus {i+1}/10 selesai (Tgl: {cycle_date.strftime('%Y-%m-%d')})")

    print("\n" + "=" * 60)
    print("  ✅ SEEDING MASSAL SELESAI!")
    print("=" * 60)
    print(f"  🛒 Total PO (Bahan Baku): {total_po} Dokumen")
    print(f"  🏭 Total MO (Produksi):   {total_mo} Dokumen")
    print(f"  🚚 Total SO (Penjualan):  {total_so} Dokumen")
    print("=" * 60)

if __name__ == "__main__":
    main()