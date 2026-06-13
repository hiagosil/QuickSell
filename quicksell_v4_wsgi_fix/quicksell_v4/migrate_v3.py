"""
QuickSell v3 — Script de Migração do Banco de Dados
Uso: python migrate_v3.py
Aplica novas tabelas e colunas (idempotente — pode rodar várias vezes).
"""

import sqlite3, os

DB_PATH = os.environ.get("DB_PATH", "store_generator_dev.db")

MIGRATIONS = [
    # v2 migrations (idempotent)
    ("categories table", """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(120) NOT NULL,
            slug VARCHAR(120) NOT NULL,
            store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
            created_at DATETIME DEFAULT (datetime('now')),
            UNIQUE(slug, store_id)
        )"""),
    ("products.stock_quantity",   "ALTER TABLE products ADD COLUMN stock_quantity INTEGER DEFAULT 0"),
    ("products.sku",              "ALTER TABLE products ADD COLUMN sku VARCHAR(100)"),
    ("products.image_path",       "ALTER TABLE products ADD COLUMN image_path VARCHAR(500)"),
    ("products.category_id",      "ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES categories(id)"),
    ("sync stock_quantity",       "UPDATE products SET stock_quantity = stock WHERE stock_quantity IS NULL OR stock_quantity = 0"),
    # v3 migrations
    ("orders table", """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name  VARCHAR(200) NOT NULL,
            customer_email VARCHAR(200) NOT NULL,
            customer_phone VARCHAR(30),
            address_zip    VARCHAR(10),
            address_street VARCHAR(300),
            address_number VARCHAR(20),
            address_city   VARCHAR(120),
            address_state  VARCHAR(2),
            subtotal       NUMERIC(10,2) DEFAULT 0,
            shipping       NUMERIC(10,2) DEFAULT 0,
            total          NUMERIC(10,2) NOT NULL,
            status         VARCHAR(20) DEFAULT 'pendente',
            notes          TEXT,
            store_id       INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
            created_at     DATETIME DEFAULT (datetime('now')),
            updated_at     DATETIME DEFAULT (datetime('now'))
        )"""),
    ("order_items table", """
        CREATE TABLE IF NOT EXISTS order_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
            product_name VARCHAR(200) NOT NULL,
            quantity     INTEGER NOT NULL DEFAULT 1,
            price        NUMERIC(10,2) NOT NULL
        )"""),
]

def run():
    if not os.path.exists(DB_PATH):
        print(f"⚠  Banco não encontrado em {DB_PATH!r}.")
        print("   Execute app.py primeiro para criá-lo via db.create_all().")
        return

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    for label, sql in MIGRATIONS:
        try:
            cur.execute(sql.strip())
            print(f"  ✅ {label}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e) or "already exists" in str(e):
                print(f"  ⏭  {label} (já aplicado)")
            else:
                print(f"  ❌ {label}: {e}")

    conn.commit()
    conn.close()
    print("\n✔  Migração v3 concluída.")

if __name__ == "__main__":
    run()
