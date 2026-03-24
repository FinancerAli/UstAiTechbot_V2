import secrets
import aiosqlite
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS services "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, "
            "price INTEGER NOT NULL, active INTEGER DEFAULT 1, category_id INTEGER, image_file_id TEXT)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users "
            "(id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, phone TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, language TEXT DEFAULT 'uz', "
            "referral_code TEXT, referred_by INTEGER, is_blocked INTEGER DEFAULT 0)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS orders "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, service_id INTEGER NOT NULL, "
            "service_name TEXT NOT NULL, price INTEGER NOT NULL, status TEXT DEFAULT 'pending', "
            "note TEXT, receipt_file_id TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, discount INTEGER DEFAULT 0, "
            "final_price INTEGER, coupon_code TEXT)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS categories "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS reviews "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, user_id INTEGER NOT NULL, "
            "service_id INTEGER NOT NULL, rating INTEGER NOT NULL, comment TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS coupons "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, "
            "discount_percent INTEGER NOT NULL, max_uses INTEGER NOT NULL, "
            "used_count INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS bonus_log "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
            "amount INTEGER NOT NULL, type TEXT NOT NULL, description TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS promos "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, "
            "text TEXT, image_file_id TEXT, url TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS service_promotions "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, service_id INTEGER NOT NULL, "
            "title TEXT, cashback_percent REAL NOT NULL, is_active INTEGER DEFAULT 1, "
            "starts_at TIMESTAMP, ends_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY(service_id) REFERENCES services(id))"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS subscriptions "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
            "service_id INTEGER, end_date TIMESTAMP NOT NULL, "
            "is_active INTEGER DEFAULT 1, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS service_bulk_prices "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, service_id INTEGER NOT NULL, "
            "min_quantity INTEGER NOT NULL, price_per_unit INTEGER NOT NULL, "
            "UNIQUE(service_id, min_quantity))"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS bonus_transactions "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
            "order_id INTEGER, amount INTEGER NOT NULL, reason TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_services_category ON services(category_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reviews_service ON reviews(service_id)")
        await db.commit()
        migrations = [
            ("services", "category_id", "INTEGER"),
            ("services", "image_file_id", "TEXT"),
            ("services", "delivery_content", "TEXT"),
            ("services", "stock", "INTEGER DEFAULT 0"),
            ("users", "language", "TEXT DEFAULT 'uz'"),
            ("users", "referral_code", "TEXT"),
            ("users", "referred_by", "INTEGER"),
            ("users", "is_blocked", "INTEGER DEFAULT 0"),
            ("users", "bonus_balance", "INTEGER DEFAULT 0"),
            ("orders", "discount", "INTEGER DEFAULT 0"),
            ("orders", "final_price", "INTEGER"),
            ("orders", "coupon_code", "TEXT"),
            ("orders", "bonus_used", "INTEGER DEFAULT 0"),
            ("orders", "cashback_awarded", "INTEGER DEFAULT 0"),
            ("orders", "quantity", "INTEGER DEFAULT 1"),
            ("services", "description_uz", "TEXT"),
            ("services", "description_ru", "TEXT"),
        ]
        for table, col, col_type in migrations:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                await db.commit()
            except Exception:
                pass


# PROMOS

async def add_promo(title: str, text: str, image_file_id: str = None, url: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO promos (title, text, image_file_id, url) VALUES (?, ?, ?, ?)",
            (title, text, image_file_id, url),
        )
        await db.commit()

async def get_promos():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM promos ORDER BY id DESC")
        return await cursor.fetchall()

async def delete_promo(promo_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promos WHERE id=?", (promo_id,))
        await db.commit()


# SERVICES

async def add_service(name, description, price, category_id=None, image_file_id=None, delivery_content=None, stock=0, description_uz=None, description_ru=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO services (name, description, description_uz, description_ru, price, category_id, image_file_id, delivery_content, stock) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, description, description_uz or description, description_ru or description, price, category_id, image_file_id, delivery_content, stock),
        )
        await db.commit()
        return cursor.lastrowid


async def update_stock(service_id: int, new_stock: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE services SET stock=? WHERE id=?", (new_stock, service_id))
        await db.commit()


async def decrease_stock(service_id: int, amount: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE services SET stock = MAX(0, stock - ?) WHERE id=?", (amount, service_id))
        await db.commit()


async def increase_stock(service_id: int, amount: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE services SET stock = stock + ? WHERE id=?", (amount, service_id))
        await db.commit()


async def set_service_delivery(service_id, delivery_content):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET delivery_content=? WHERE id=?",
            (delivery_content, service_id),
        )
        await db.commit()


async def get_services(only_active=True, category_id=None, query=None, limit=None, offset=0):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        conditions = []
        params = []
        if only_active:
            conditions.append("s.active=1")
        if category_id is not None:
            conditions.append("s.category_id=?")
            params.append(category_id)
        if query:
            conditions.append("LOWER(s.name) LIKE LOWER(?)")
            params.append(f"%{query}%")
            
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        
        # Left join with service_promotions to get active cashback
        sql = f"""
            SELECT s.*, 
                   p.cashback_percent, p.title as promo_title, p.is_active as promo_active 
            FROM services s 
            LEFT JOIN service_promotions p ON s.id = p.service_id AND p.is_active = 1
            {where} 
            ORDER BY s.id DESC
        """
        
        if limit is not None:
            sql += f" LIMIT {limit} OFFSET {offset}"
            
        cursor = await db.execute(sql, params)
        return await cursor.fetchall()


async def get_services_count(only_active=True, category_id=None, query=None):
    async with aiosqlite.connect(DB_PATH) as db:
        conditions = []
        params = []
        if only_active:
            conditions.append("active=1")
        if category_id is not None:
            conditions.append("category_id=?")
            params.append(category_id)
        if query:
            conditions.append("LOWER(name) LIKE LOWER(?)")
            params.append(f"%{query}%")
            
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cursor = await db.execute(f"SELECT COUNT(*) FROM services {where}", params)
        row = await cursor.fetchone()
        return row[0]


async def get_service(service_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = """
            SELECT s.*, 
                   p.cashback_percent, p.title as promo_title, p.is_active as promo_active 
            FROM services s 
            LEFT JOIN service_promotions p ON s.id = p.service_id AND p.is_active = 1
            WHERE s.id=?
        """
        cursor = await db.execute(sql, (service_id,))
        return await cursor.fetchone()


async def update_service(service_id, name, description, price, description_ru=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET name=?, description=?, description_uz=?, description_ru=?, price=? WHERE id=?",
            (name, description, description, description_ru or description, price, service_id),
        )
        await db.commit()


async def toggle_service(service_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET active = CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=?",
            (service_id,),
        )
        await db.commit()


async def delete_service(service_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM services WHERE id=?", (service_id,))
        await db.commit()


# SERVICE PROMOTIONS (CASHBACK)

async def get_service_promo_admin(service_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM service_promotions WHERE service_id=?", (service_id,))
        return await cursor.fetchone()

async def create_or_update_service_promo(service_id: int, title: str, percent: float, starts_at=None, ends_at=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM service_promotions WHERE service_id=?", (service_id,))
        exists = await cursor.fetchone()
        if exists:
            await db.execute(
                "UPDATE service_promotions SET title=?, cashback_percent=?, starts_at=?, ends_at=? WHERE service_id=?",
                (title, percent, starts_at, ends_at, service_id)
            )
        else:
            await db.execute(
                "INSERT INTO service_promotions (service_id, title, cashback_percent, starts_at, ends_at) VALUES (?, ?, ?, ?, ?)",
                (service_id, title, percent, starts_at, ends_at)
            )
        await db.commit()

async def toggle_service_promo(promo_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE service_promotions SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?", (promo_id,))
        await db.commit()

async def delete_service_promo(promo_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM service_promotions WHERE id=?", (promo_id,))
        await db.commit()

async def list_all_service_promotions():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT p.*, s.name as service_name "
            "FROM service_promotions p "
            "JOIN services s ON p.service_id = s.id "
            "ORDER BY p.id DESC"
        )
        return await cursor.fetchall()


async def add_bonus_transaction(user_id: int, order_id: int, amount: int, reason: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bonus_transactions (user_id, order_id, amount, reason) VALUES (?, ?, ?, ?)",
            (user_id, order_id, amount, reason)
        )
        await db.execute(
            "UPDATE users SET bonus_balance = bonus_balance + ? WHERE id=?",
            (amount, user_id)
        )
        await db.commit()

async def mark_order_cashback_awarded(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET cashback_awarded=1 WHERE id=?", (order_id,))
        await db.commit()

async def get_user_total_cashback(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT SUM(amount) FROM bonus_transactions WHERE user_id=? AND reason LIKE 'Cashback%'", (user_id,))
        res = await cursor.fetchone()
        return res[0] or 0


# CATEGORIES

async def add_category(name):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        await db.commit()
        return cursor.lastrowid


async def get_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM categories ORDER BY id")
        return await cursor.fetchall()


async def get_category(cat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM categories WHERE id=?", (cat_id,))
        return await cursor.fetchone()


async def delete_category(cat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        await db.commit()


# USERS

async def save_user(user_id, username, full_name, referred_by=None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        existing = await (await db.execute("SELECT * FROM users WHERE id=?", (user_id,))).fetchone()
        if existing:
            if not existing["referral_code"]:
                ref_code = secrets.token_hex(4)
                await db.execute(
                    "UPDATE users SET username=?, full_name=?, referral_code=? WHERE id=?",
                    (username, full_name, ref_code, user_id),
                )
            else:
                await db.execute(
                    "UPDATE users SET username=?, full_name=? WHERE id=?",
                    (username, full_name, user_id),
                )
        else:
            ref_code = secrets.token_hex(4)
            await db.execute(
                "INSERT INTO users (id, username, full_name, referral_code, referred_by) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, full_name, ref_code, referred_by),
            )
        await db.commit()


async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE id=?", (user_id,))
        return await cursor.fetchone()


# NEW FEATURE: Top services ranking
async def get_top_services(limit: int = 3):
    """
    Return the most ordered services along with their order count.

    Args:
        limit (int): Maximum number of services to return. Defaults to 3.

    Returns:
        List[aiosqlite.Row]: Each row contains service id, name and order_count.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Count the number of orders per service. We use LEFT JOIN so that services with
        # zero orders still appear in the ranking; however, they will sort after those
        # with orders due to descending order_count.
        cursor = await db.execute(
            """
            SELECT s.id, s.name, COUNT(o.id) AS order_count
            FROM services s
            LEFT JOIN orders o ON o.service_id = s.id
            GROUP BY s.id
            ORDER BY order_count DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cursor.fetchall()


async def set_user_language(user_id, lang):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET language=? WHERE id=?", (lang, user_id))
        await db.commit()


async def block_user(user_id, blocked):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_blocked=? WHERE id=?", (blocked, user_id))
        await db.commit()


async def get_user_by_referral(ref_code):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE referral_code=?", (ref_code,))
        return await cursor.fetchone()


async def get_referral_count(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,))
        row = await cursor.fetchone()
        return row[0]


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
        return await cursor.fetchall()


async def get_user_count():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0]


# ORDERS

async def create_order(user_id, service_id, service_name, price, note="",
                       discount=0, final_price=None, coupon_code=None, bonus_used=0, quantity=1):
    if final_price is None:
        final_price = price * quantity - (price * quantity * discount // 100)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO orders (user_id, service_id, service_name, price, note, discount, final_price, coupon_code, bonus_used, quantity)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, service_id, service_name, price, note, discount, final_price, coupon_code, bonus_used, quantity),
        )
        await db.commit()
        return cursor.lastrowid


async def set_order_receipt(order_id, file_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET receipt_file_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (file_id, order_id),
        )
        await db.commit()


async def update_order_status(order_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, order_id),
        )
        await db.commit()


async def get_order(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        return await cursor.fetchone()


async def get_user_orders(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 10",
            (user_id,),
        )
        return await cursor.fetchall()


async def get_user_total_spent(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(final_price), 0) FROM orders WHERE user_id=? AND status='confirmed'",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] or 0


async def get_pending_orders():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT o.*, u.username, u.full_name FROM orders o "
            "LEFT JOIN users u ON o.user_id = u.id "
            "WHERE o.status='pending' ORDER BY o.created_at DESC"
        )
        return await cursor.fetchall()


async def get_all_orders(limit=50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT o.*, u.username, u.full_name FROM orders o "
            "LEFT JOIN users u ON o.user_id = u.id "
            "ORDER BY o.created_at DESC LIMIT ?",
            (limit,),
        )
        return await cursor.fetchall()


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        total_orders = (await (await db.execute("SELECT COUNT(*) FROM orders")).fetchone())[0]
        pending = (await (await db.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")).fetchone())[0]
        confirmed = (await (await db.execute("SELECT COUNT(*) FROM orders WHERE status='confirmed'")).fetchone())[0]
        rejected = (await (await db.execute("SELECT COUNT(*) FROM orders WHERE status='rejected'")).fetchone())[0]
        revenue_row = await (await db.execute("SELECT SUM(final_price) FROM orders WHERE status='confirmed'")).fetchone()
        revenue = revenue_row[0] or 0
        
        today_rev = await (await db.execute("SELECT SUM(final_price) FROM orders WHERE status='confirmed' AND date(created_at) = date('now', 'localtime')")).fetchone()
        today_revenue = today_rev[0] or 0
        
        conversion = round((confirmed / total_orders) * 100, 1) if total_orders > 0 else 0

        return {
            "users": users, "total_orders": total_orders, "pending": pending,
            "confirmed": confirmed, "rejected": rejected, "revenue": revenue,
            "today_revenue": today_revenue, "conversion": conversion,
        }


# REVIEWS

async def add_review(order_id, user_id, service_id, rating, comment=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reviews (order_id, user_id, service_id, rating, comment) VALUES (?, ?, ?, ?, ?)",
            (order_id, user_id, service_id, rating, comment),
        )
        await db.commit()


async def get_service_reviews(service_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT r.*, u.full_name, u.username FROM reviews r "
            "LEFT JOIN users u ON r.user_id = u.id "
            "WHERE r.service_id=? ORDER BY r.created_at DESC LIMIT 20",
            (service_id,),
        )
        return await cursor.fetchall()


async def get_service_avg_rating(service_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT AVG(rating), COUNT(*) FROM reviews WHERE service_id=?",
            (service_id,),
        )
        row = await cursor.fetchone()
        return round(row[0] or 0, 1), row[1] or 0


async def get_recent_reviews(limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT r.*, u.full_name, u.username, s.name as service_name FROM reviews r "
            "LEFT JOIN users u ON r.user_id = u.id "
            "LEFT JOIN services s ON r.service_id = s.id "
            "ORDER BY r.created_at DESC LIMIT ?",
            (limit,),
        )
        return await cursor.fetchall()


async def review_exists(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM reviews WHERE order_id=?", (order_id,))
        return await cursor.fetchone() is not None


# COUPONS

async def add_coupon(code, discount_percent, max_uses):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO coupons (code, discount_percent, max_uses) VALUES (?, ?, ?)",
            (code.upper(), discount_percent, max_uses),
        )
        await db.commit()
        return cursor.lastrowid


async def get_coupon(code):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM coupons WHERE code=? AND is_active=1 AND used_count < max_uses",
            (code.upper(),),
        )
        return await cursor.fetchone()


async def use_coupon(code):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE coupons SET used_count = used_count + 1 WHERE code=?",
            (code.upper(),),
        )
        await db.commit()


async def get_all_coupons():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM coupons ORDER BY id DESC")
        return await cursor.fetchall()


async def delete_coupon(coupon_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM coupons WHERE id=?", (coupon_id,))
        await db.commit()


# BONUS

async def add_bonus(user_id, amount, description=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET bonus_balance = bonus_balance + ? WHERE id=?",
            (amount, user_id),
        )
        await db.execute(
            "INSERT INTO bonus_log (user_id, amount, type, description) VALUES (?, ?, 'credit', ?)",
            (user_id, amount, description),
        )
        await db.commit()


async def use_bonus(user_id, amount, description=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET bonus_balance = MAX(0, bonus_balance - ?) WHERE id=?",
            (amount, user_id),
        )
        await db.execute(
            "INSERT INTO bonus_log (user_id, amount, type, description) VALUES (?, ?, 'debit', ?)",
            (user_id, amount, description),
        )
        await db.commit()


async def get_bonus_log(user_id, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM bonus_log WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        return await cursor.fetchall()


async def get_user_confirmed_orders_count(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE user_id=? AND status='confirmed'",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0]
async def get_active_service_promotions():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = """
            SELECT p.*, s.name as service_name, s.price 
            FROM service_promotions p 
            JOIN services s ON p.service_id = s.id 
            WHERE p.is_active = 1
            ORDER BY p.id DESC
        """
        cursor = await db.execute(sql)
        return await cursor.fetchall()


# BULK PRICING

async def get_bulk_prices(service_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM service_bulk_prices WHERE service_id=? ORDER BY min_quantity ASC", (service_id,))
        return await cursor.fetchall()

async def get_price_for_quantity(service_id: int, quantity: int, base_price: int):
    tiers = await get_bulk_prices(service_id)
    applicable_price = base_price
    for t in tiers:
        if quantity >= t["min_quantity"]:
            applicable_price = t["price_per_unit"]
    return applicable_price

async def add_bulk_price(service_id: int, min_qty: int, price: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO service_bulk_prices (service_id, min_quantity, price_per_unit) VALUES (?, ?, ?)", (service_id, min_qty, price))
        await db.execute("UPDATE service_bulk_prices SET price_per_unit=? WHERE service_id=? AND min_quantity=?", (price, service_id, min_qty))
        await db.commit()

async def delete_bulk_price(price_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM service_bulk_prices WHERE id = ?", (price_id,))
        await db.commit()

async def get_expiring_subscriptions(days: int = 3):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM subscriptions WHERE is_active = 1 "
            "AND date(end_date) = date('now', '+' || ? || ' days')", (days,)
        )
        return await cursor.fetchall()
