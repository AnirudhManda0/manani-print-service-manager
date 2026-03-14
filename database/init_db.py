import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.database import Database


def main() -> None:
    db_path = os.path.join(ROOT, "database", "cybercafe.db")
    schema_path = os.path.join(ROOT, "database", "schema.sql")
    db = Database(db_path=db_path, schema_path=schema_path)
    db.close()
    print(f"Database initialized at: {db_path}")


if __name__ == "__main__":
    main()
