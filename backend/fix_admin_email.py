#!/usr/bin/env python3
"""Quick script to fix the admin email typo"""

import sqlite3

db_path = "data/db/intelligence.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Show current users
print("Current users:")
cursor.execute("SELECT id, email, role FROM users")
for row in cursor.fetchall():
    print(f"  {row}")

# Delete the typo user
cursor.execute("DELETE FROM users WHERE email='nmerett@gmail.com'")
deleted = cursor.rowcount
conn.commit()

print(f"\nDeleted {deleted} user(s) with typo email")

# Show remaining users
print("\nRemaining users:")
cursor.execute("SELECT id, email, role FROM users")
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
print("\nDone! Fix your .env FIRST_ADMIN_EMAIL and restart the backend.")
