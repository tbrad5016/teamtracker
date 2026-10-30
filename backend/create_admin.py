# create_admin.py  (TeamTracker.gg, Phase 5)
# ------------------------------------------------------------------
# Creates an administrator account.
#
# Why a script? The admin password must NOT be written in the code or in a
# SQL file. This script asks for it in a hidden prompt, hashes it, and stores
# only the hash in the database.
#
# Run it once from the project root, after the database is running:
#     python backend/create_admin.py
# ------------------------------------------------------------------

import argparse
import getpass
import sys

import psycopg2
import psycopg2.errors

import database as db


def main():
    parser = argparse.ArgumentParser(description="Create a TeamTracker admin account.")
    parser.add_argument("--username", help="admin username (asked for if left out)")
    parser.add_argument("--email", help="admin email (asked for if left out)")
    args = parser.parse_args()

    username = (args.username or input("Admin username: ")).strip()
    email = (args.email or input("Admin email: ")).strip()
    password = getpass.getpass("Admin password (typing is hidden): ")
    confirm = getpass.getpass("Type the password again: ")

    if not username or not email:
        sys.exit("Username and email are required.")
    if len(password) < 8:
        sys.exit("The password must be at least 8 characters.")
    if password != confirm:
        sys.exit("The two passwords do not match.")

    try:
        db.add_user(username, email, password, role="admin")
    except psycopg2.errors.UniqueViolation:
        sys.exit("That username or email is already registered.")
    except psycopg2.OperationalError:
        sys.exit("Cannot reach the database. Is Docker running? Try: docker compose up -d")
    print(f"Admin account '{username}' created. You can log in at /login.")


if __name__ == "__main__":
    main()
