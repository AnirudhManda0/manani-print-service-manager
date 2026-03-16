-- Core schema for ManAni Print & Service Manager

CREATE TABLE IF NOT EXISTS print_jobs (
    id INTEGER PRIMARY KEY,
    operator_id TEXT NOT NULL DEFAULT 'ADMIN',
    computer_name TEXT NOT NULL,
    printer_name TEXT NOT NULL,
    document_name TEXT,
    pages INTEGER NOT NULL CHECK (pages >= 1),
    print_type TEXT NOT NULL CHECK (print_type IN ('black_and_white', 'color')),
    paper_size TEXT NOT NULL DEFAULT 'Unknown',
    price_per_page REAL NOT NULL,
    total_cost REAL NOT NULL,
    timestamp DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS services_catalog (
    id INTEGER PRIMARY KEY,
    service_name TEXT NOT NULL UNIQUE,
    default_price REAL NOT NULL CHECK (default_price >= 0)
);

CREATE TABLE IF NOT EXISTS service_records (
    id INTEGER PRIMARY KEY,
    service_id INTEGER NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),
    timestamp DATETIME NOT NULL,
    FOREIGN KEY (service_id) REFERENCES services_catalog (id)
);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    bw_price_per_page REAL NOT NULL CHECK (bw_price_per_page >= 0),
    color_price_per_page REAL NOT NULL CHECK (color_price_per_page >= 0),
    currency TEXT NOT NULL,
    retention_mode TEXT NOT NULL DEFAULT 'retain_all',
    retention_days INTEGER NOT NULL DEFAULT 30,
    backup_enabled INTEGER NOT NULL DEFAULT 1,
    backup_folder TEXT NOT NULL DEFAULT 'backup',
    last_backup_date TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_print_jobs_timestamp ON print_jobs (timestamp);
CREATE INDEX IF NOT EXISTS idx_service_records_timestamp ON service_records (timestamp);
CREATE INDEX IF NOT EXISTS idx_service_records_service_id ON service_records (service_id);

INSERT OR IGNORE INTO settings (
    id,
    bw_price_per_page,
    color_price_per_page,
    currency
)
VALUES (1, 2.0, 10.0, 'INR');

INSERT OR IGNORE INTO services_catalog (service_name, default_price) VALUES ('PAN Card', 120.0);
INSERT OR IGNORE INTO services_catalog (service_name, default_price) VALUES ('Exam Registration', 80.0);
INSERT OR IGNORE INTO services_catalog (service_name, default_price) VALUES ('Scanning', 20.0);
INSERT OR IGNORE INTO services_catalog (service_name, default_price) VALUES ('Lamination', 30.0);
INSERT OR IGNORE INTO services_catalog (service_name, default_price) VALUES ('Photo Printing', 50.0);
