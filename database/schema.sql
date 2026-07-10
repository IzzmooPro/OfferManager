-- Ürün kategorileri tablosu
CREATE TABLE IF NOT EXISTS product_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER,
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY (parent_id) REFERENCES product_categories(id) ON DELETE SET NULL
);

-- Ürünler tablosu
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'EUR',
    stock REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT 'Adet',
    category_id INTEGER DEFAULT NULL,
    -- Alış fiyatı (maliyet) — yalnızca dahili kâr hesabı için; PDF/Excel
    -- teklif çıktılarına ve müşteri görünümüne asla dahil edilmez.
    cost_price REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (category_id) REFERENCES product_categories(id) ON DELETE SET NULL
);

-- Müşteriler tablosu
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    contact_person TEXT,
    address TEXT,
    phone TEXT,
    email TEXT,
    notes TEXT DEFAULT ''
);

-- Teklifler tablosu
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_no TEXT NOT NULL UNIQUE,
    customer_id INTEGER,
    company_name TEXT,
    customer_address TEXT,
    contact_person TEXT,
    customer_phone TEXT,
    customer_email TEXT,
    date TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    total_amount REAL NOT NULL DEFAULT 0,
    validity TEXT DEFAULT '',
    validity_note TEXT DEFAULT '',
    payment_term TEXT DEFAULT '',
    status TEXT DEFAULT 'Beklemede',
    discount_amount REAL DEFAULT 0.0,
    discount_type TEXT DEFAULT 'amount',
    discount_value REAL DEFAULT 0.0,
    show_discount INTEGER DEFAULT 1,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
);

-- Teklif kalemleri tablosu
CREATE TABLE IF NOT EXISTS offer_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id INTEGER NOT NULL,
    product_id INTEGER,
    product_code TEXT,
    product_name TEXT,
    description TEXT,
    quantity REAL NOT NULL DEFAULT 1,
    unit TEXT DEFAULT 'Adet',
    delivery_time TEXT DEFAULT '2-3 Hafta',
    unit_price REAL NOT NULL DEFAULT 0,
    total_price REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (offer_id) REFERENCES offers(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

-- Teklif şablonları tablosu
CREATE TABLE IF NOT EXISTS offer_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    items_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (date('now'))
);

-- Teklif sayacı tablosu
CREATE TABLE IF NOT EXISTS offer_counter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    last_number INTEGER NOT NULL DEFAULT 0
);

-- Performans indexleri
CREATE INDEX IF NOT EXISTS idx_offers_customer_id     ON offers(customer_id);
CREATE INDEX IF NOT EXISTS idx_offers_status          ON offers(status);
CREATE INDEX IF NOT EXISTS idx_offers_date            ON offers(date);
CREATE INDEX IF NOT EXISTS idx_offer_items_offer_id   ON offer_items(offer_id);
CREATE INDEX IF NOT EXISTS idx_offer_items_product_id ON offer_items(product_id);
