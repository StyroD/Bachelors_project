import pandas as pd
from datetime import date, datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import subprocess
import requests
from io import StringIO

def download_changes_tsv():
    url = "https://raw.githubusercontent.com/cpicpgx/cpic-data/main/data.tsv"
    response = requests.get(url)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text), sep="\t")

def get_connection():
    """Return a new PostgreSQL connection."""
    if not ensure_db_running():
        raise RuntimeError("PostgreSQL is not running. Please start the service.")
    return psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="789#",
        database="pharmacogenomic_data"
    )

def ensure_db_running():
    """Check if PostgreSQL is running; if not, try to start it."""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="789#",
            database="pharmacogenomic_data"
        )
        conn.close()
        return True
    except psycopg2.OperationalError:
        try:
            subprocess.run(
                ["sudo", "systemctl", "start", "postgresql"],
                check=True
            )
            return True
        except Exception:
            return False

def get_last_synced_date():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT value FROM sync_state WHERE key = 'last_synced';")
    row = cur.fetchone()  # returns a single dict or None
    cur.close()
    conn.close()

    if row is None:
        return date(1970, 1, 1)  # fallback if table is empty
    print(datetime.strptime(row['value'], "%Y-%m-%d").date())
    return datetime.strptime(row['value'], "%Y-%m-%d").date()

last_synced = get_last_synced_date()  # from DB or file


df = download_changes_tsv()
df["Date of Change"] = pd.to_datetime(df["Date of Change"], errors="coerce")
new_changes = df[df["Date of Change"] > pd.Timestamp(last_synced)]
print(new_changes)
