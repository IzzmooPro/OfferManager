"""Veritabanı yönetimi — SQLite, migration desteği."""
import sqlite3, logging
import threading
from contextlib import contextmanager
from typing import Optional, List
from core.app_paths import DB_PATH, SCHEMA_PATH

logger = logging.getLogger("db_manager")


_schema_initialized = False


class DB:
    def __init__(self):
        global _schema_initialized
        self.db_path  = DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not _schema_initialized:
            self._init_schema()
            self._migrate()
            _schema_initialized = True

    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self):
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        conn = self._get_conn()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(schema)
            conn.commit()
        finally:
            conn.close()
        logger.debug("Şema başlatıldı.")

    def _migrate(self):
        """Eksik sütunları mevcut DB'ye ekler — güvenli ALTER TABLE."""
        migrations = [
            ("customers", "notes",           "TEXT DEFAULT ''"),
            ("offers", "company_name",       "TEXT DEFAULT ''"),
            ("offers", "customer_address",   "TEXT DEFAULT ''"),
            ("offers", "contact_person",     "TEXT DEFAULT ''"),
            ("offers", "customer_phone",     "TEXT DEFAULT ''"),
            ("offers", "customer_email",     "TEXT DEFAULT ''"),
            ("offers", "validity",           "TEXT DEFAULT ''"),
            ("offers", "validity_note",      "TEXT DEFAULT ''"),
            ("offers", "payment_term",       "TEXT DEFAULT ''"),
            ("offers", "status",             "TEXT DEFAULT 'Beklemede'"),
            ("offers", "discount_amount",    "REAL DEFAULT 0.0"),
            ("offers", "discount_type",      "TEXT DEFAULT 'amount'"),
            ("offers", "discount_value",     "REAL DEFAULT 0.0"),
            ("offers", "show_discount",      "INTEGER DEFAULT 1"),
        ]
        conn = self._get_conn()
        try:
            for table, col, coltype in migrations:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                    logger.info("Migration: %s.%s eklendi", table, col)
                except sqlite3.OperationalError:
                    pass  # Sütun zaten var

            # Mevcut tekliflerde company_name boşsa → customers tablosundan doldur
            conn.execute("""
                UPDATE offers
                SET company_name = (
                    SELECT c.company_name FROM customers c
                    WHERE c.id = offers.customer_id
                )
                WHERE (company_name IS NULL OR company_name = '')
                  AND customer_id IS NOT NULL
            """)

            # Eski sürümlerde iskonto yalnız sabit parasal tutar olarak saklanıyordu.
            conn.execute("""
                UPDATE offers
                SET discount_type = 'amount',
                    discount_value = discount_amount
                WHERE discount_amount > 0
                  AND (discount_value IS NULL OR discount_value = 0)
            """)

            # Eski sürümler tarihi dd.MM.yyyy biçiminde saklıyordu. Sıralama,
            # tarih aralığı ve ciro sorguları için veritabanında ISO biçimi kullan.
            conn.execute("""
                UPDATE offers
                SET date = substr(date, 7, 4) || '-' ||
                           substr(date, 4, 2) || '-' ||
                           substr(date, 1, 2)
                WHERE date GLOB '[0-9][0-9].[0-9][0-9].[0-9][0-9][0-9][0-9]'
            """)

            # Kategori tablosu (v3.0) — eski DB'lerde yoksa oluştur
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    parent_id INTEGER,
                    sort_order INTEGER DEFAULT 0,
                    FOREIGN KEY (parent_id) REFERENCES product_categories(id) ON DELETE SET NULL
                )
            """)
            try:
                conn.execute("ALTER TABLE products ADD COLUMN category_id INTEGER DEFAULT NULL")
                logger.info("Migration: products.category_id eklendi")
            except sqlite3.OperationalError:
                pass

            # Şablon tablosu (v3.0) — eski DB'lerde yoksa oluştur
            conn.execute("""
                CREATE TABLE IF NOT EXISTS offer_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name TEXT NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'EUR',
                    items_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT (date('now'))
                )
            """)

            # Mevcut DB'lere index ekle (schema.sql zaten IF NOT EXISTS içeriyor)
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_offers_customer_id     ON offers(customer_id)",
                "CREATE INDEX IF NOT EXISTS idx_offers_status          ON offers(status)",
                "CREATE INDEX IF NOT EXISTS idx_offers_date            ON offers(date)",
                "CREATE INDEX IF NOT EXISTS idx_offer_items_offer_id   ON offer_items(offer_id)",
                "CREATE INDEX IF NOT EXISTS idx_offer_items_product_id ON offer_items(product_id)",
            ]:
                try:
                    conn.execute(idx_sql)
                except sqlite3.OperationalError as e:
                    logger.debug("Index oluşturma atlandı: %s", e)
            conn.commit()
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self._get_conn()
        try:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor
        finally:
            conn.close()

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        conn = self._get_conn()
        try:
            return conn.execute(sql, params).fetchone()
        finally:
            conn.close()

    def fetchall(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        conn = self._get_conn()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    @contextmanager
    def transaction(self, exclusive: bool = False):
        """Atomik işlemler için context manager.

        Kullanım:
            with db.transaction() as conn:
                conn.execute("INSERT ...")
            # Hata olursa otomatik ROLLBACK

        exclusive=True → BEGIN EXCLUSIVE: teklif numarası gibi
        sayaç güncellemelerinde eşzamanlı yazma engelini garanti eder.
        """
        conn = self._get_conn()
        try:
            conn.execute("BEGIN EXCLUSIVE" if exclusive else "BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def close(self) -> None:
        """Bağlantıyı kapat (uygulama kapanırken)."""
        logger.debug("Veritabanı bağlantısı kapatıldı.")
        global _instance
        with _instance_lock:
            _instance = None


_instance = None
_instance_lock = threading.Lock()

def get_db() -> DB:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DB()
    return _instance
