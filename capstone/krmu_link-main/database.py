import json
import os
from contextlib import contextmanager
from pathlib import Path

import mysql.connector


BASE_DIR = Path(__file__).resolve().parent
LEGACY_TICKETS_FILE = BASE_DIR / "maintenance_db.json"
LEGACY_TECHS_FILE = BASE_DIR / "techs.json"

TICKET_FIELDS = (
    "ticket_id",
    "full_name",
    "email",
    "phone",
    "block",
    "floor",
    "room",
    "date",
    "category",
    "priority",
    "location",
    "description",
    "image",
    "status",
    "qr_code",
    "timestamp",
)
TICKET_COLUMNS = {field: field for field in TICKET_FIELDS}


@contextmanager
def _connection():
    database = os.environ.get("MYSQL_DATABASE")
    user = os.environ.get("MYSQL_USER")
    if not database or not user:
        raise RuntimeError(
            "MySQL is not configured. MYSQL_DATABASE and MYSQL_USER are required; "
            "MYSQL_HOST, MYSQL_PORT, and MYSQL_PASSWORD may also be set."
        )

    connection = mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        database=database,
        user=user,
        password=os.environ.get("MYSQL_PASSWORD", ""),
        connection_timeout=10,
        charset="utf8mb4",
    )
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _read_legacy_list(path):
    with path.open("r", encoding="utf-8") as legacy_file:
        data = json.load(legacy_file)
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise ValueError(f"Expected a JSON array of objects in {path}")
    return data


def _decode_json(value):
    return json.loads(value) if isinstance(value, str) else value


def _insert_ticket(cursor, ticket):
    if ticket.get("ticket_id") is None:
        raise ValueError("A legacy ticket is missing its ticket_id")

    present_fields = [field for field in TICKET_FIELDS if field in ticket]
    extra_data = {
        key: value for key, value in ticket.items() if key not in TICKET_FIELDS
    }
    columns = [TICKET_COLUMNS[field] for field in TICKET_FIELDS]
    columns.extend(("present_fields", "extra_data"))
    values = [ticket.get(field) for field in TICKET_FIELDS]
    values.extend((json.dumps(present_fields), json.dumps(extra_data)))
    placeholders = ", ".join("%s" for _ in columns)
    cursor.execute(
        f"INSERT IGNORE INTO tickets (`{'`, `'.join(columns)}`) "
        f"VALUES ({placeholders})",
        values,
    )


def initialize_database():
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id VARCHAR(64) PRIMARY KEY,
                    full_name VARCHAR(255),
                    email VARCHAR(320),
                    phone VARCHAR(64),
                    block VARCHAR(100),
                    floor VARCHAR(50),
                    room VARCHAR(50),
                    `date` VARCHAR(32),
                    category VARCHAR(255),
                    priority VARCHAR(50),
                    location VARCHAR(255),
                    description TEXT,
                    image LONGTEXT,
                    status VARCHAR(100),
                    qr_code LONGTEXT,
                    `timestamp` BIGINT,
                    present_fields TEXT NOT NULL,
                    extra_data LONGTEXT NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS technicians (
                    id VARCHAR(64) PRIMARY KEY,
                    category VARCHAR(255) NOT NULL,
                    email VARCHAR(320) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS migration_state (
                    name VARCHAR(100) PRIMARY KEY
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            cursor.execute(
                "SELECT 1 FROM migration_state WHERE name = %s",
                ("legacy_tickets",),
            )
            if cursor.fetchone() is None and LEGACY_TICKETS_FILE.exists():
                for ticket in _read_legacy_list(LEGACY_TICKETS_FILE):
                    _insert_ticket(cursor, ticket)
                cursor.execute(
                    "INSERT INTO migration_state (name) VALUES (%s)",
                    ("legacy_tickets",),
                )

            cursor.execute(
                "SELECT 1 FROM migration_state WHERE name = %s",
                ("legacy_technicians",),
            )
            if cursor.fetchone() is None and LEGACY_TECHS_FILE.exists():
                for tech in _read_legacy_list(LEGACY_TECHS_FILE):
                    required_fields = ("id", "category", "email")
                    if not all(tech.get(field) is not None for field in required_fields):
                        raise ValueError(
                            f"A legacy technician in {LEGACY_TECHS_FILE} "
                            "is missing its id, category, or email"
                        )
                    cursor.execute(
                        """
                        INSERT IGNORE INTO technicians (id, category, email)
                        VALUES (%s, %s, %s)
                        """,
                        (str(tech["id"]), tech["category"], tech["email"]),
                    )
                cursor.execute(
                    "INSERT INTO migration_state (name) VALUES (%s)",
                    ("legacy_technicians",),
                )


def _ticket_from_row(row):
    if row is None:
        return None
    ticket = {
        field: row[TICKET_COLUMNS[field]]
        for field in _decode_json(row["present_fields"])
    }
    ticket.update(_decode_json(row["extra_data"]))
    return ticket


def _select_ticket(cursor, ticket_id):
    cursor.execute(
        "SELECT * FROM tickets WHERE ticket_id = %s",
        (ticket_id,),
    )
    return cursor.fetchone()


def create_ticket(ticket):
    if ticket.get("ticket_id") is None:
        raise ValueError("A ticket must have a ticket_id")
    present_fields = [field for field in TICKET_FIELDS if field in ticket]
    extra_data = {
        key: value for key, value in ticket.items() if key not in TICKET_FIELDS
    }
    columns = [TICKET_COLUMNS[field] for field in TICKET_FIELDS]
    columns.extend(("present_fields", "extra_data"))
    values = [ticket.get(field) for field in TICKET_FIELDS]
    values.extend((json.dumps(present_fields), json.dumps(extra_data)))
    placeholders = ", ".join("%s" for _ in columns)
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO tickets (`{'`, `'.join(columns)}`) "
                f"VALUES ({placeholders})",
                values,
            )


def get_tickets():
    with _connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM tickets ORDER BY `timestamp`, ticket_id")
            rows = cursor.fetchall()
    return [_ticket_from_row(row) for row in rows]


def update_ticket_status(ticket_id, new_status):
    with _connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            row = _select_ticket(cursor, ticket_id)
            if row is None:
                return None
            ticket = _ticket_from_row(row)
            old_status = ticket.get("status")
            ticket["status"] = new_status
            present_fields = list(
                dict.fromkeys([*_decode_json(row["present_fields"]), "status"])
            )
            cursor.execute(
                """
                UPDATE tickets
                SET status = %s, present_fields = %s
                WHERE ticket_id = %s
                """,
                (new_status, json.dumps(present_fields), ticket_id),
            )
    return old_status, ticket


def delete_ticket(ticket_id):
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM tickets WHERE ticket_id = %s", (ticket_id,))
            return cursor.rowcount > 0


def get_technicians():
    with _connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT id, category, email FROM technicians ORDER BY id"
            )
            return cursor.fetchall()


def add_technician(tech):
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO technicians (id, category, email)
                VALUES (%s, %s, %s)
                """,
                (tech["id"], tech["category"], tech["email"]),
            )


def get_technician(tech_id):
    with _connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT id, category, email FROM technicians WHERE id = %s",
                (tech_id,),
            )
            return cursor.fetchone()


def update_technician(tech_id, category, email):
    with _connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(
                "UPDATE technicians SET category = %s, email = %s WHERE id = %s",
                (category, email, tech_id),
            )
            cursor.execute(
                "SELECT id, category, email FROM technicians WHERE id = %s",
                (tech_id,),
            )
            return cursor.fetchone()


def delete_technician(tech_id):
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM technicians WHERE id = %s", (tech_id,))
            return cursor.rowcount > 0
