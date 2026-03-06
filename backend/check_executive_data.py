"""
Diagnostic script: Check what executive data exists in the database.
Run inside the backend container: python check_executive_data.py
"""

from app.core.database import SessionLocal
from app.models.database import Customer, IntelligenceItem
from sqlalchemy import func, or_
from datetime import datetime, timedelta

db = SessionLocal()

print("=" * 70)
print("EXECUTIVE DASHBOARD DATA DIAGNOSTIC")
print("=" * 70)

# 1. Customers and their linkedin_user_profiles
print("\n── CUSTOMERS & CONFIGURED EXECUTIVES ──")
customers = db.query(Customer).all()
if not customers:
    print("  NO CUSTOMERS FOUND!")
else:
    for c in customers:
        config = c.config or {}
        profiles = config.get('linkedin_user_profiles', [])
        print(f"\n  Customer #{c.id}: {c.name}")
        print(f"    Keywords: {c.keywords}")
        if profiles:
            for p in profiles:
                print(f"    👤 {p.get('name', '?')} | {p.get('role', '?')}")
                print(f"       URL: {p.get('profile_url', 'none')}")
        else:
            print("    ⚠  No linkedin_user_profiles configured!")

# 2. Source types and counts
print("\n── INTELLIGENCE ITEMS BY SOURCE TYPE ──")
counts = db.query(
    Customer.name,
    IntelligenceItem.source_type,
    func.count(IntelligenceItem.id)
).join(Customer).group_by(
    Customer.name, IntelligenceItem.source_type
).order_by(Customer.name, IntelligenceItem.source_type).all()

for cust_name, src_type, cnt in counts:
    print(f"  {cust_name:30s} | {src_type:20s} | {cnt:5d} items")

# 3. Recent items (last 90 days)
cutoff = datetime.utcnow() - timedelta(days=90)
recent_count = db.query(func.count(IntelligenceItem.id)).filter(
    IntelligenceItem.published_date >= cutoff
).scalar()
total_count = db.query(func.count(IntelligenceItem.id)).scalar()
print("\n── ITEM FRESHNESS ──")
print(f"  Total items: {total_count}")
print(f"  Items in last 90 days: {recent_count}")

# 4. Search for "guy scott"
print("\n── SEARCH: 'guy scott' IN TITLES/CONTENT ──")
guy_items = db.query(IntelligenceItem).filter(
    or_(
        IntelligenceItem.title.ilike('%guy%scott%'),
        IntelligenceItem.content.ilike('%guy%scott%'),
    )
).limit(10).all()
if guy_items:
    for item in guy_items:
        print(f"  [{item.source_type}] {item.title[:80]}")
else:
    print("  No items found mentioning 'guy scott'")

# 5. Search for all configured executive names in intelligence
print("\n── EXECUTIVE NAME MENTIONS IN INTELLIGENCE ──")
for c in customers:
    config = c.config or {}
    profiles = config.get('linkedin_user_profiles', [])
    for p in profiles:
        name = p.get('name', '')
        if not name:
            continue
        name_pattern = f"%{name}%"
        mention_count = db.query(func.count(IntelligenceItem.id)).filter(
            IntelligenceItem.customer_id == c.id,
            IntelligenceItem.published_date >= cutoff,
            or_(
                IntelligenceItem.title.ilike(name_pattern),
                IntelligenceItem.content.ilike(name_pattern),
            )
        ).scalar()
        status = f"{mention_count} mentions (90d)" if mention_count else "⚠  0 mentions"
        print(f"  {name:30s} @ {c.name:20s} → {status}")

# 6. Sample linkedin_user items
print("\n── SAMPLE LINKEDIN_USER ITEMS ──")
li_items = db.query(IntelligenceItem).filter(
    IntelligenceItem.source_type == 'linkedin_user'
).order_by(IntelligenceItem.published_date.desc()).limit(5).all()
if li_items:
    for item in li_items:
        print(f"  [{item.published_date}] {item.title[:80]}")
        print(f"    Customer: {item.customer_id} | URL: {(item.url or '')[:60]}")
else:
    print("  No linkedin_user items found")

db.close()
print("\n" + "=" * 70)
print("DONE")
