#!/usr/bin/env python3
"""Create RSS feed tokens for all existing customers for the admin user"""

import sqlite3
import secrets

db_path = "data/db/intelligence.db"

def generate_token():
    return secrets.token_urlsafe(32)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get admin user
cursor.execute("SELECT id, email FROM users WHERE role='platform_admin' LIMIT 1")
admin = cursor.fetchone()
if not admin:
    print("No admin user found!")
    exit(1)

admin_id, admin_email = admin
print(f"Admin user: {admin_email} (id: {admin_id})")

# Get all customers
cursor.execute("SELECT id, name FROM customers")
customers = cursor.fetchall()

print(f"\nFound {len(customers)} customers")

# Create tokens for each customer
created = 0
for customer_id, customer_name in customers:
    # Check if token already exists for this customer/user combo
    cursor.execute(
        "SELECT id FROM rss_feed_tokens WHERE customer_id=? AND user_id=?",
        (customer_id, admin_id)
    )
    if cursor.fetchone():
        print(f"  Skipping {customer_name} - token already exists")
        continue

    token = generate_token()
    cursor.execute(
        """INSERT INTO rss_feed_tokens
           (token, customer_id, user_id, name, is_active, created_at)
           VALUES (?, ?, ?, ?, 1, datetime('now'))""",
        (token, customer_id, admin_id, f"{customer_name} RSS Feed")
    )
    created += 1
    print(f"  Created token for {customer_name}")

conn.commit()

# Show all tokens
print(f"\n--- Created {created} new tokens ---\n")
print("All RSS tokens:")
cursor.execute("""
    SELECT t.id, c.name, t.token
    FROM rss_feed_tokens t
    JOIN customers c ON t.customer_id = c.id
    WHERE t.user_id = ?
""", (admin_id,))

for token_id, customer_name, token in cursor.fetchall():
    print(f"\n{customer_name}:")
    print(f"  /api/rss/feed?token={token}")

conn.close()
print("\nDone!")
