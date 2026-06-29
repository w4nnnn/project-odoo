import os
import csv
from api import OdooAPI

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")

def main():
    print("=" * 60)
    print("  🏭 Odoo Seeding — Data Terhubung (Chain)")
    print("=" * 60)

    api = OdooAPI(ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD)
    api.create_database_if_not_exists()
    api.authenticate()
    api.install_required_modules()

    print("\n1. Membuat Master Data (Pelanggan, Vendor, dan Barang)...")
    
    # 1A. Mitra (Contacts)
    customer_id = api.create('res.partner', {'name': 'Warung Jamu Mbah Joyo', 'is_company': False})
    vendor_rempah_id = api.create('res.partner', {'name': 'UD Tani Makmur (Rempah)', 'is_company': True})
    vendor_kemasan_id = api.create('res.partner', {'name': 'Pabrik Kemasan Botol', 'is_company': True})

    # 1B. Bahan Baku (Raw Materials)
    jahe_id = api.create('product.product', {'name': 'Jahe Merah', 'type': 'consu', 'is_storable': True, 'standard_price': 25000})
    gula_id = api.create('product.product', {'name': 'Gula Merah', 'type': 'consu', 'is_storable': True, 'standard_price': 15000})
    botol_id = api.create('product.product', {'name': 'Botol Kaca 250ml', 'type': 'consu', 'is_storable': True, 'standard_price': 2000})
    
    # 1C. Produk Jadi (Finished Good)
    jamu_id = api.create('product.product', {'name': 'Jamu Jahe Merah 250ml', 'type': 'consu', 'is_storable': True, 'list_price': 18000})

    print(f"✅ Master dibuat! Barang Jadi: Jamu Jahe Merah ({jamu_id})")

    # Ambil template ID & UoM dari Jamu untuk referensi BoM
    jamu_results = api.search_read('product.product', [('id', '=', jamu_id)], fields=['product_tmpl_id', 'uom_id'], limit=1)
    if not jamu_results:
        print("❌ Gagal mendapatkan data jamu.")
        return
    jamu_rec = jamu_results[0]
    jamu_tmpl_id = jamu_rec['product_tmpl_id'][0] if isinstance(jamu_rec, dict) and 'product_tmpl_id' in jamu_rec else False
    uom_id = jamu_rec['uom_id'][0] if isinstance(jamu_rec, dict) and 'uom_id' in jamu_rec else False

    # ---------------------------------------------------------
    print("\n2. Membuat Bill of Materials / Resep Jamu...")
    bom_id = api.create('mrp.bom', {
        'product_tmpl_id': jamu_tmpl_id,
        'product_qty': 1.0,
        'type': 'normal',
    })
    # Komponen Resep
    api.create('mrp.bom.line', {'bom_id': bom_id, 'product_id': jahe_id, 'product_qty': 0.1})  # 100 gram
    api.create('mrp.bom.line', {'bom_id': bom_id, 'product_id': gula_id, 'product_qty': 0.05}) # 50 gram
    api.create('mrp.bom.line', {'bom_id': bom_id, 'product_id': botol_id, 'product_qty': 1.0}) # 1 botol
    
    print(f"✅ Resep/BoM ({bom_id}) untuk Jamu Jahe Merah 250ml berhasil dibuat.")

    # ---------------------------------------------------------
    print("\n3. Proses Pengadaan Bahan Baku (Purchase Order)...")
    # PO ke Supplier Rempah
    po1_id = api.create('purchase.order', {'partner_id': vendor_rempah_id})
    api.create('purchase.order.line', {'order_id': po1_id, 'product_id': jahe_id, 'product_qty': 10, 'price_unit': 25000})
    api.create('purchase.order.line', {'order_id': po1_id, 'product_id': gula_id, 'product_qty': 5, 'price_unit': 15000})
    api.safe_action('purchase.order', po1_id, 'button_confirm')

    # PO ke Supplier Botol
    po2_id = api.create('purchase.order', {'partner_id': vendor_kemasan_id})
    api.create('purchase.order.line', {'order_id': po2_id, 'product_id': botol_id, 'product_qty': 100, 'price_unit': 2000})
    api.safe_action('purchase.order', po2_id, 'button_confirm')
    
    print("✅ Purchase Order untuk bahan baku telah dikonfirmasi.")

    # ---------------------------------------------------------
    print("\n4. Proses Pemindahan Barang Masuk (Penerimaan Bahan Baku)...")
    def validate_receipt(po_id):
        po_results = api.search_read('purchase.order', [('id', '=', po_id)], fields=['picking_ids'], limit=1)
        if not po_results:
            return
        po_record = po_results[0]
        if isinstance(po_record, dict):
            for picking_id in po_record.get('picking_ids', []):
                move_lines = api.search_read('stock.move.line', 
                                     [('picking_id', '=', picking_id)], 
                                     fields=['id', 'quantity_product_uom'])
                if isinstance(move_lines, list):
                    for ml in move_lines:
                        if isinstance(ml, dict):
                            api.write('stock.move.line', [ml['id']], {'quantity': ml['quantity_product_uom']})
                api.safe_action('stock.picking', picking_id, 'button_validate')
            
    validate_receipt(po1_id)
    validate_receipt(po2_id)
    print("✅ Penerimaan barang divalidasi. Bahan baku telah masuk gudang (Stok bertambah).")

    # ---------------------------------------------------------
    print("\n5. Proses Produksi Jamu (Manufacturing Order)...")
    
    # MO 1: Selesai (Done)
    mo_id = api.create('mrp.production', {
        'product_id': jamu_id,
        'product_qty': 50, # Kita memproduksi 50 Botol Jamu
        'product_uom_id': uom_id,
        'bom_id': bom_id,
    })
    # Konfirmasi Produksi
    api.action('mrp.production', mo_id, 'action_confirm')
    
    # Reserve komponen bahan baku
    api.action('mrp.production', mo_id, 'action_assign')
    
    # Isi hasil produksi (Set Qty Producing)
    api.write('mrp.production', [mo_id], {'qty_producing': 50})
    
    # Memastikan bahan baku tercatat sebagai dikonsumsi (consumed)
    mo_results = api.search_read('mrp.production', [('id', '=', mo_id)], fields=['move_raw_ids'], limit=1)
    if mo_results:
        mo_record = mo_results[0]
        if isinstance(mo_record, dict) and 'move_raw_ids' in mo_record:
            for move_id in mo_record.get('move_raw_ids', []):
                move_results = api.search_read('stock.move', [('id', '=', move_id)], fields=['product_uom_qty'], limit=1)
                if move_results:
                    move = move_results[0]
                    if isinstance(move, dict):
                        api.write('stock.move', [move_id], {'quantity': move.get('product_uom_qty', 0), 'picked': True})

    # Tandai Selesai (Mark as Done)
    try:
        api.action('mrp.production', mo_id, 'button_mark_done')
        print(f"✅ Produksi 1 ({mo_id}) selesai! 50 botol Jamu (Status: Done).")
    except Exception as e:
        print(f"⚠️  Gagal validasi MO 1: {e}")

    # MO 2: Sedang Proses (In Progress / To Do)
    mo2_id = api.create('mrp.production', {
        'product_id': jamu_id,
        'product_qty': 30, # Rencana produksi 30 botol lagi
        'product_uom_id': uom_id,
        'bom_id': bom_id,
    })
    api.action('mrp.production', mo2_id, 'action_confirm')
    api.action('mrp.production', mo2_id, 'action_assign') # Reserve bahan baku
    print(f"✅ Produksi 2 ({mo2_id}) dibuat! 30 botol Jamu sedang diproses (Status: In Progress/To Do).")

    # ---------------------------------------------------------
    print("\n6. Proses Jual Beli (Sales Order)...")
    so_id = api.create('sale.order', {'partner_id': customer_id})
    api.create('sale.order.line', {
        'order_id': so_id,
        'product_id': jamu_id,
        'product_uom_qty': 20, # Jual 20 botol
        'price_unit': 18000,
    })
    api.safe_action('sale.order', so_id, 'action_confirm')
    print(f"✅ Sales Order ({so_id}) divalidasi. Berhasil menjual 20 botol jamu.")

    # ---------------------------------------------------------
    print("\n7. Proses Pengiriman Barang ke Pelanggan (Delivery Order)...")
    so_results = api.search_read('sale.order', [('id', '=', so_id)], fields=['picking_ids'], limit=1)
    if not so_results:
        return
    so_record = so_results[0]
    if isinstance(so_record, dict):
        for picking_id in so_record.get('picking_ids', []):
            api.safe_action('stock.picking', picking_id, 'action_assign') # Reserve stok
            
            move_lines = api.search_read('stock.move.line', 
                                 [('picking_id', '=', picking_id)], 
                                 fields=['id', 'quantity_product_uom'])
            if isinstance(move_lines, list):
                for ml in move_lines:
                    if isinstance(ml, dict):
                        api.write('stock.move.line', [ml['id']], {'quantity': ml['quantity_product_uom']})
                
            # Also ensure stock.move has quantity set
            moves = api.search_read('stock.move', [('picking_id', '=', picking_id)], fields=['id', 'product_uom_qty'])
            if isinstance(moves, list):
                for mv in moves:
                    if isinstance(mv, dict):
                        api.write('stock.move', [mv['id']], {'quantity': mv['product_uom_qty']})
                
            api.safe_action('stock.picking', picking_id, 'button_validate')
            print(f"✅ Pengiriman ({picking_id}) selesai. Stok Jamu Jahe Merah berkurang 20 botol.")

    print("\n" + "=" * 60)
    print("  ✅ SEEDING SELESAI!")
    print("=" * 60)

if __name__ == "__main__":
    main()