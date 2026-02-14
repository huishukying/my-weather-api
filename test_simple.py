from database import SessionLocal
from sqlalchemy import text

print("Testing database connection...")

db = SessionLocal()

result = db.execute(text("SELECT * FROM users"))
users = result.fetchall()

print(f"Found {len(users)} users:")
for user in users:
    print(f"  - {user[1]} ({user[2]})")

db.close()
print("✅ Database works!")
