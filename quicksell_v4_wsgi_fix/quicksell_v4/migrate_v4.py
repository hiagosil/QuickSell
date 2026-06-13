"""
QuickSell v4 — Script de Migração: Tabelas de Pagamento Mercado Pago
Uso: python migrate_v4.py
Idempotente — pode rodar múltiplas vezes com segurança.
"""
import sqlite3, os

DB_PATH = os.environ.get("DB_PATH", "store_generator_dev.db")

MIGRATIONS = [
    ("mp_configs table", """
        CREATE TABLE IF NOT EXISTS mp_configs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id       INTEGER NOT NULL UNIQUE REFERENCES stores(id) ON DELETE CASCADE,
            access_token   VARCHAR(512) NOT NULL,
            webhook_secret VARCHAR(256),
            is_active      BOOLEAN DEFAULT 1,
            created_at     DATETIME DEFAULT (datetime('now')),
            updated_at     DATETIME DEFAULT (datetime('now'))
        )"""),
    ("payments table", """
        CREATE TABLE IF NOT EXISTS payments (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id          INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            store_id          INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
            mp_payment_id     VARCHAR(100) UNIQUE,
            mp_preference_id  VARCHAR(200),
            mp_status         VARCHAR(50),
            mp_status_detail  VARCHAR(100),
            pix_qr_code       TEXT,
            pix_copy_paste    TEXT,
            pix_expires_at    DATETIME,
            status            VARCHAR(30) DEFAULT 'pendente',
            amount            NUMERIC(10,2) NOT NULL,
            webhook_validated BOOLEAN DEFAULT 0,
            idempotency_key   VARCHAR(100) UNIQUE,
            created_at        DATETIME DEFAULT (datetime('now')),
            updated_at        DATETIME DEFAULT (datetime('now'))
        )"""),
    ("payments idx store_id",
     "CREATE INDEX IF NOT EXISTS ix_payments_store_id ON payments(store_id)"),
    ("payments idx status",
     "CREATE INDEX IF NOT EXISTS ix_payments_status ON payments(status)"),
]

def run():
    if not os.path.exists(DB_PATH):
        print(f"Banco nao encontrado em {DB_PATH!r}.")
        print("Execute app.py primeiro para criar via db.create_all().")
        return
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    for label, sql in MIGRATIONS:
        try:
            cur.execute(sql.strip())
            print(f"  OK: {label}")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                print(f"  --: {label} (ja existe)")
            else:
                print(f"  ERRO: {label}: {e}")
    conn.commit()
    conn.close()
    print("Migracao v4 concluida.")

if __name__ == "__main__":
    run()
