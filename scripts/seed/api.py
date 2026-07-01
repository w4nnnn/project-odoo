import xmlrpc.client
import sys
import time

class OdooAPI:
    def __init__(self, url, db, username, password):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self.common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        self.db_rpc = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/db")

    def create_database_if_not_exists(self):
        try:
            db_list = self.db_rpc.list()
            if self.db not in db_list:
                print(f"🗄️ Database '{self.db}' tidak ditemukan. Membuat database dasar (ini memakan waktu)...")
                self.db_rpc.create_database("admin", self.db, False, "en_US", self.password)
                print(f"✅ Database '{self.db}' berhasil dibuat.")
                
                # Memastikan Odoo mendeteksi modul custom di folder addons
                try:
                    temp_uid = self.common.authenticate(self.db, self.username, self.password, {})
                    if temp_uid:
                        self.models.execute_kw(self.db, temp_uid, self.password, 'ir.module.module', 'update_list', [])
                        print("✅ Daftar modul (update_list) berhasil diperbarui.")
                except Exception as e:
                    print(f"⚠️ Gagal mengupdate module list: {e}")
                    
            else:
                print(f"✅ Database '{self.db}' sudah ada.")
        except xmlrpc.client.Fault as e:
            if "Access denied" in str(e):
                print("⚠️ Tidak ada akses ke database manager (master password mungkin salah), menganggap database sudah ada.")
            else:
                print(f"⚠️ Gagal mengecek/membuat database: {e}")
        except xmlrpc.client.ProtocolError as e:
            if e.errcode == 500:
                print(f"⚠️ Error 500 dari Odoo. Memaksa pembuatan database langsung...")
                self.db_rpc.create_database("admin", self.db, False, "en_US", self.password)
            else:
                print(f"⚠️ Gagal menghubungi server Odoo: {e}")
        except Exception as e:
            print(f"⚠️ Gagal menghubungi server Odoo: {e}")

    def install_required_modules(self):
        print("\n📦 Memeriksa dan meng-install modul satu per satu...")
        modules_to_check = ["sale_management", "stock", "account", "purchase", "mrp", "custom_home_menu"]
        
        for name in modules_to_check:
            # Re-authenticate in case Odoo just restarted from a previous install
            try:
                self.authenticate()
            except SystemExit:
                return

            mods = self.search_read(
                "ir.module.module",
                [("name", "=", name)],
                fields=["id", "state", "shortdesc"],
                limit=1,
            )
            if not mods:
                print(f"   ⚠️  Modul {name} tidak ditemukan, skip")
                continue
            
            mod = mods[0]
            if not isinstance(mod, dict):
                continue
                
            shortdesc = mod.get('shortdesc')
            if mod.get("state") == "installed":
                print(f"   ✅ {shortdesc} ({name}) sudah ter-install.")
                continue

            mod_id = mod.get("id")
            print(f"\n   ⏳ Meng-install {shortdesc} ({name})...")
            
            self.safe_action("ir.module.module", [mod_id], "button_immediate_install")
            print(f"   Menunggu Odoo menyelesaikan instalasi dan me-restart untuk {name}...")
            
            # Tunggu setidaknya 15 detik sebelum mulai polling
            time.sleep(15)

            installed = False
            for attempt in range(60):
                time.sleep(5)
                try:
                    # Update module list saat restart selesai jika perlu
                    if attempt == 0:
                        try:
                            temp_uid = self.common.authenticate(self.db, self.username, self.password, {})
                            if temp_uid:
                                self.models.execute_kw(self.db, temp_uid, self.password, 'ir.module.module', 'update_list', [])
                        except Exception:
                            pass
                            
                    temp_uid = self.common.authenticate(self.db, self.username, self.password, {})
                    if not temp_uid:
                        continue
                        
                    check_mod = self.models.execute_kw(self.db, temp_uid, self.password, 'ir.module.module', 'search_read',
                        [[("id", "=", mod_id)]],
                        {'fields': ["state"], 'limit': 1})
                        
                    if check_mod and isinstance(check_mod, list) and len(check_mod) > 0:
                        state = check_mod[0].get("state")
                        if state == "installed":
                            print(f"   ✅ {shortdesc} ({name}) berhasil ter-install!")
                            installed = True
                            break
                        elif attempt % 6 == 0:
                            print(f"   ⏳ Menunggu instalasi {name}... ({(attempt+1)*5}s) [Status: {state}]")
                except Exception:
                    # Server masih proses restart
                    continue
                    
            if not installed:
                print(f"   ⚠️  Timeout! Modul {name} mungkin belum selesai di-install.")
                print(f"   Akan mencoba lanjut ke modul berikutnya...")

        print("\n   ✅ Selesai memproses instalasi modul.")

    def authenticate(self):
        for attempt in range(12):
            try:
                self.uid = self.common.authenticate(self.db, self.username, self.password, {})
                if self.uid:
                    print(f"✅ Login berhasil (uid={self.uid})")
                    return
            except xmlrpc.client.ProtocolError as e:
                if e.errcode == 500:
                    print(f"   ⏳ Menunggu Odoo siap (Error 500)... {55 - attempt*5}s tersisa")
                    time.sleep(5)
                else:
                    raise
            except Exception as e:
                print(f"   ⏳ Menunggu Odoo siap ({e})... {55 - attempt*5}s tersisa")
                time.sleep(5)
        
        print("❌ Gagal login! Periksa ODOO_DB, ODOO_USER, ODOO_PASSWORD, atau status server.")
        sys.exit(1)

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
        if isinstance(move_lines, list):
            for ml in move_lines:
                if isinstance(ml, dict):
                    if ml.get("state") in ("done", "cancel"):
                        continue
                    qty = ml.get("quantity_product_uom", 0) or 0
                    if qty > 0:
                        self.write("stock.move.line", [ml["id"]], {"quantity": qty})
                        
        moves = self.search_read(
            "stock.move",
            [("picking_id", "=", picking_id)],
            fields=["id", "product_uom_qty"],
        )
        if isinstance(moves, list):
            for mv in moves:
                if isinstance(mv, dict):
                    self.write("stock.move", [mv["id"]], {"quantity": mv["product_uom_qty"]})
                    
        self.safe_action("stock.picking", picking_id, "button_validate")
