import os
import psycopg2
from dotenv import load_dotenv
from app.auth import hash_password

load_dotenv()


def seed_registrar():
    """
    One-time script to create the initial registrar account.
    Run once during deployment setup, then delete or disable this script.
    """
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()

    email = "registrar@afit.edu.ng"
    password = "ChangeMe@2026"  # registrar changes these on first login

    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        print(f"Registrar {email} already exists")
        conn.close()
        return

    hashed = hash_password(password)
    cursor.execute(
        "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)",
        (email, hashed, "registrar"),
    )
    conn.commit()
    print(f"Registrar created: {email} / {password}")
    print("Change this password immediately after first login.")
    conn.close()


def delete_my_account():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()

    # Target your specific email
    email = "exceliyoha103@gmail.com"

    try:
        cursor.execute("DELETE FROM users WHERE email = %s", (email,))
        conn.commit()

        if cursor.rowcount > 0:
            print(f"Successfully deleted {email} from the database.")
        else:
            print(f"Account {email} not found.")

    except Exception as e:
        conn.rollback()
        print(f"Error deleting account: {e}")

    finally:
        cursor.close()
        conn.close()


def verify_seed_registrar_created():
    """Checks to see if truly the suoer admin is alrady created"""
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()

    # Check for the account
    email = "registrar@afit.edu.ng"
    cursor.execute("SELECT email, role FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user:
        print(f"SUCCESS: Account found! Email: {user[0]}, Role: {user[1]}")
    else:
        print("FAILED: Account not found in the database.")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    seed_registrar()
    verify_seed_registrar_created()