"""
QuickSell v2 — Script de Migração do Banco de Dados
Uso: python migrate_v2.py
Executa uma vez para adicionar as novas colunas e criar a tabela categories.
"""

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "store_generator_dev.db")

MIGRATIONS = [
    # 1. Tabela de categorias
    """
    CREATE TABLE IF NOT EXISTS categories (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       VARCHAR(120) NOT NULL,
        slug       VARCHAR(120) NOT NULL,
        store_id   INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
        created_at DATETIME DEFAULT (datetime('now')),
        UNIQUE(slug, store_id)
    )
    """,
    # 2. Coluna stock_quantity em products
    "ALTER TABLE products ADD COLUMN stock_quantity INTEGER DEFAULT 0",
    # 3. Coluna sku em products
    "ALTER TABLE products ADD COLUMN sku VARCHAR(100)",
    # 4. Coluna image_path (upload local)
    "ALTER TABLE products ADD COLUMN image_path VARCHAR(500)",
    # 5. Coluna category_id em products
    "ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES categories(id)",
    # 6. Sincroniza stock_quantity com stock existente
    "UPDATE products SET stock_quantity = stock WHERE stock_quantity IS NULL OR stock_quantity = 0",
]

def run():
    if not os.path.exists(DB_PATH):
        print(f"⚠  Banco não encontrado em {DB_PATH!r}.")
        print("   Execute app.py primeiro para criá-lo via db.create_all().")
        return

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    for i, sql in enumerate(MIGRATIONS, 1):
        try:
            cur.execute(sql.strip())
            print(f"  ✅ Migração {i} aplicada.")
        except sqlite3.OperationalError as e:
            # Coluna já existe = OK
            if "duplicate column name" in str(e) or "already exists" in str(e):
                print(f"  ⏭  Migração {i} ignorada (já aplicada).")
            else:
                print(f"  ❌ Migração {i} FALHOU: {e}")

    conn.commit()
    conn.close()
    print("\n✔  Migração concluída.")

if __name__ == "__main__":
    run()
