"""
AIOps Sentinel - Database Architecture
SQLite initialization, schema management, and connection utilities.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from backend.config import config

def get_db_connection():
    """Returns a thread-safe connection to the SQLite database with row_factory."""
    conn = sqlite3.connect(str(config.DB_PATH), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

@contextmanager
def db_session():
    """Context manager for SQLite transactions with automatic commit and rollback."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize all relational tables and seed baseline data."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with db_session() as conn:
        cursor = conn.cursor()

        # 1. E-Commerce: Products
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                image TEXT,
                rating_rate REAL DEFAULT 4.5,
                rating_count INTEGER DEFAULT 100,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. E-Commerce: Cart Items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                price REAL NOT NULL,
                image TEXT,
                quantity INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );
        """)

        # 3. E-Commerce: Orders
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                session_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                total_amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                status TEXT DEFAULT 'PENDING',
                items_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. E-Commerce: Payments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT UNIQUE NOT NULL,
                order_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                card_last4 TEXT NOT NULL,
                response_time_ms REAL NOT NULL,
                gateway_code TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            );
        """)

        # 5. Auth / Users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'shopper',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 6. Observability: Service Metrics Timeseries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                service_name TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                status_code INTEGER NOT NULL,
                is_error INTEGER DEFAULT 0,
                cpu_percent REAL DEFAULT 0.0,
                memory_percent REAL DEFAULT 0.0,
                request_id TEXT
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_svc_time ON service_metrics(service_name, timestamp);")

        # 7. Adaptive Threshold Configurations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threshold_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT UNIQUE NOT NULL,
                metric_name TEXT DEFAULT 'latency_ms',
                mode TEXT DEFAULT 'hybrid',
                static_warning REAL NOT NULL,
                static_critical REAL NOT NULL,
                rolling_median REAL DEFAULT 0.0,
                rolling_mad REAL DEFAULT 0.0,
                dynamic_warning REAL DEFAULT 0.0,
                dynamic_critical REAL DEFAULT 0.0,
                min_samples INTEGER DEFAULT 8,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 8. Anomaly Detections (Threshold & ML)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                service_name TEXT NOT NULL,
                detection_method TEXT NOT NULL,
                anomaly_score REAL DEFAULT 0.0,
                metrics_json TEXT NOT NULL,
                explanation TEXT NOT NULL,
                is_incident INTEGER DEFAULT 0
            );
        """)

        # 9. Incidents
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                affected_service TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT DEFAULT 'ACTIVE',
                root_cause_summary TEXT,
                blast_radius_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolved_by TEXT,
                resolution_action TEXT
            );
        """)

        # 10. Incident Evidence (Explainable RCA)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incident_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                observed_value REAL,
                expected_baseline REAL,
                confidence REAL DEFAULT 0.8,
                description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
            );
        """)

        # 11. Deployment Events (CI/CD Git Correlation)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deployment_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                commit_hash TEXT UNIQUE NOT NULL,
                version TEXT NOT NULL,
                author TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT DEFAULT 'SUCCESS',
                deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                affected_services_json TEXT NOT NULL
            );
        """)

        # 12. AI-Assisted Runbooks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runbooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT UNIQUE NOT NULL,
                generated_by TEXT NOT NULL,
                markdown_content TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
            );
        """)

        # 13. Controlled Recovery Actions & Audit Log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recovery_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT UNIQUE NOT NULL,
                incident_id TEXT NOT NULL,
                action_name TEXT NOT NULL,
                target_service TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING_APPROVAL',
                requested_by TEXT DEFAULT 'Sentinel RCA Engine',
                approved_by TEXT,
                approved_at TIMESTAMP,
                executed_at TIMESTAMP,
                verified_at TIMESTAMP,
                pre_recovery_health TEXT,
                post_recovery_health TEXT,
                audit_log TEXT,
                FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
            );
        """)

        # 14. Evaluation & Benchmarking Records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_name TEXT NOT NULL,
                detection_method TEXT NOT NULL,
                mttd_seconds REAL NOT NULL,
                mttr_seconds REAL NOT NULL,
                rca_top1_correct INTEGER DEFAULT 1,
                rca_top3_correct INTEGER DEFAULT 1,
                false_positive INTEGER DEFAULT 0,
                recovery_successful INTEGER DEFAULT 1,
                evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Seed baseline users
        cursor.execute("SELECT COUNT(*) FROM users;")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO users (username, email, full_name, role)
                VALUES ('demo_shopper', 'shopper@sentinel.local', 'Sarah Jenkins', 'shopper'),
                       ('admin', 'sre-admin@sentinel.local', 'SRE Operations Lead', 'admin');
            """)

        # Seed initial threshold configs from config.py SLOs
        for svc_name, slo in config.SERVICE_SLOS.items():
            cursor.execute("""
                INSERT OR IGNORE INTO threshold_configs 
                (service_name, metric_name, mode, static_warning, static_critical, min_samples)
                VALUES (?, 'latency_ms', 'hybrid', ?, ?, ?);
            """, (svc_name, slo.static_latency_warning_ms, slo.static_latency_critical_ms, config.MIN_OBSERVATIONS_FOR_ADAPTIVE))

        # Seed initial deployments
        cursor.execute("SELECT COUNT(*) FROM deployment_events;")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO deployment_events (commit_hash, version, author, message, status, deployed_at, affected_services_json)
                VALUES 
                ('a1b2c3d', 'v2.4.0', 'Alex Rivera', 'Release v2.4.0: Core storefront microservices stability update', 'SUCCESS', datetime('now', '-45 minutes'), '["product-service", "cart-service", "order-service"]'),
                ('f9e8d7c', 'v2.4.1', 'Devin Vance', 'Release v2.4.1: Update payment service client pool & timeout config', 'SUCCESS', datetime('now', '-5 minutes'), '["payment-service", "order-service"]');
            """)

        # Seed baseline curated products (guarantees offline availability + instant cold starts)
        cursor.execute("SELECT COUNT(*) FROM products;")
        if cursor.fetchone()[0] == 0:
            seed_curated_products(cursor)

def seed_curated_products(cursor):
    """Seed high-quality catalog items matching Fake Store API schema."""
    sample_products = [
        (1, "Fjallraven - Foldsack No. 1 Backpack, Fits 15 Laptops", 109.95, 
         "Your perfect pack for everyday use and walks in the forest. Stash your laptop in the padded sleeve.", 
         "men's clothing", "https://fakestoreapi.com/img/81fPKd-2AYL._AC_SL1500_.jpg", 4.3, 120),
        (2, "Mens Casual Premium Slim Fit T-Shirts", 22.3, 
         "Slim-fitting style, contrast raglan long sleeve, three-button henley placket, light weight & soft fabric.", 
         "men's clothing", "https://fakestoreapi.com/img/71-3HjGNDUL._AC_SY879._SX._UX._SY._UY_.jpg", 4.1, 259),
        (3, "Mens Cotton Jacket", 55.99, 
         "Great outerwear jackets for Spring/Autumn/Winter, suitable for many occasions like hiking, cycling, traveling.", 
         "men's clothing", "https://fakestoreapi.com/img/71li-ujtlUL._AC_UX679_.jpg", 4.7, 500),
        (4, "Mens Casual Slim Fit", 15.99, 
         "The color could be slightly different between on the screen and in practice. Hand wash cold or machine wash.", 
         "men's clothing", "https://fakestoreapi.com/img/71YXzeOuslL._AC_UY879_.jpg", 4.2, 430),
        (5, "John Hardy Women's Legends Naga Gold & Silver Dragon Station Chain Bracelet", 695.0, 
         "From our Legends Collection, the Naga was inspired by the mythical water dragon that protects the ocean's pearl.", 
         "jewelery", "https://fakestoreapi.com/img/71pWzhdJNwL._AC_UL640_QL65_ML3_.jpg", 4.6, 400),
        (6, "Solid Gold Petite Micropave", 168.0, 
         "Satisfaction Guaranteed. Return or exchange any order within 30 days. Designed and sold exclusively.", 
         "jewelery", "https://fakestoreapi.com/img/61sbMiUnoGL._AC_UL640_QL65_ML3_.jpg", 3.9, 70),
        (7, "White Gold Plated Princess Ring", 9.99, 
         "Classic Created Wedding Engagement Solitaire Diamond Promise Ring for Her. Gifts to spoil your love more.", 
         "jewelery", "https://fakestoreapi.com/img/71YAIFU48IL._AC_UL640_QL65_ML3_.jpg", 3.0, 400),
        (8, "Pierced Owl Rose Gold Plated Stainless Steel Double Flared Tunnel Plug Earrings", 10.99, 
         "Rose Gold Plated Double Flared Tunnel Plug Earrings. Made of 316L Stainless Steel.", 
         "jewelery", "https://fakestoreapi.com/img/51UDEzMJVpL._AC_UL640_QL65_ML3_.jpg", 4.8, 100),
        (9, "WD 2TB Elements Portable External Hard Drive - USB 3.0", 64.0, 
         "USB 3.0 and USB 2.0 Compatibility Fast data transfers Improve PC Performance High Capacity.", 
         "electronics", "https://fakestoreapi.com/img/61IBBVJvSDL._AC_SY879_.jpg", 3.3, 203),
        (10, "SanDisk SSD PLUS 1TB Internal SSD - SATA III 6 Gb/s", 109.0, 
         "Easy upgrade for faster boot up, shutdown, application load and response. Boosts burst write performance.", 
         "electronics", "https://fakestoreapi.com/img/61U7T1koQqL._AC_SX679_.jpg", 4.5, 470),
        (11, "Silicon Power 256GB SSD 3D NAND A55 SLC Cache Performance Boost SATA III", 109.0, 
         "3D NAND flash are applied to deliver high transfer speeds. Remarkable transfer speeds that enable faster bootup.", 
         "electronics", "https://fakestoreapi.com/img/71kWymZ+c+L._AC_SX679_.jpg", 4.8, 319),
        (12, "WD 4TB Gaming Drive Works with Playstation 4 Portable External Hard Drive", 114.0, 
         "Expand your PS4 gaming experience, Play anywhere Fast and easy setup, Sleek design with high capacity.", 
         "electronics", "https://fakestoreapi.com/img/61mtL65D4cL._AC_SX679_.jpg", 4.8, 400),
        (13, "Acer SB220Q bi 21.5 inches Full HD (1920 x 1080) IPS Ultra-Thin", 599.0, 
         "21. 5 inches Full HD widescreen IPS display And Radeon free Sync technology. No compatibility for VESA Mount.", 
         "electronics", "https://fakestoreapi.com/img/81QpkIctqPL._AC_SX679_.jpg", 4.0, 250),
        (14, "Samsung 49-Inch CHG90 144Hz Curved Gaming Monitor", 999.99, 
         "49 INCH SUPER ULTRAWIDE 32:9 CURVED GAMING MONITOR with dual 27 inch screen side by side.", 
         "electronics", "https://fakestoreapi.com/img/81Zt42ioCgL._AC_SX679_.jpg", 4.4, 140),
        (15, "BIYLACLESEN Women's 3-in-1 Snowboard Jacket Winter Coats", 56.99, 
         "Note:The Jackets is US standard size, Please choose size as your usual wear. Material: 100% Polyester.", 
         "women's clothing", "https://fakestoreapi.com/img/51Y5NI-I5jL._AC_UX679_.jpg", 4.6, 235),
        (16, "Lock and Love Women's Removable Hooded Faux Leather Moto Biker Jacket", 29.95, 
         "100% POLYURETHANE (shell) 100% POLYESTER (lining) 75% POLYESTER 25% COTTON (SWEATER), Faux leather material.", 
         "women's clothing", "https://fakestoreapi.com/img/81XH0e8fefL._AC_UY879_.jpg", 3.9, 340),
        (17, "Rain Jacket Women Windbreaker Striped Climbing Raincoats", 39.99, 
         "Lightweight, skin-friendly, comfortable and breathable. Perfect for casual, outdoor, climbing, running, cycling.", 
         "women's clothing", "https://fakestoreapi.com/img/71HblAHs5xL._AC_UY879_-2.jpg", 4.8, 679),
        (18, "MBJ Women's Solid Short Sleeve Boat Neck V Neck", 9.85, 
         "95% RAYON 5% SPANDEX, Made in USA or Imported, Pull On closure, Machine Wash. Lightweight fabric with great stretch.", 
         "women's clothing", "https://fakestoreapi.com/img/71z3kpMAYUL._AC_UY879_.jpg", 4.7, 130),
        (19, "Opna Women's Short Sleeve Moisture", 7.95, 
         "100% Polyester, Machine wash, 100% cationic polyester interlock, Lightweight, roomy and highly breathable.", 
         "women's clothing", "https://fakestoreapi.com/img/51eg55uWmdL._AC_UX679_.jpg", 4.5, 146),
        (20, "DANVOUY Womens T Shirt Casual Cotton Short", 12.99, 
         "95%Cotton,5%Spandex, Features: Casual, Short Sleeve, Letter Print,V-Neck,Fashion Tees, The fabric is soft.", 
         "women's clothing", "https://fakestoreapi.com/img/61pHAEJ4NML._AC_UX679_.jpg", 3.6, 145)
    ]
    cursor.executemany("""
        INSERT INTO products (id, title, price, description, category, image, rating_rate, rating_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, sample_products)
