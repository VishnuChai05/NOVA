import os
import sqlalchemy as sa
import sys

URL = "postgresql+psycopg://postgres.eemyxinvimdfmukpfagk:VikiChai56%24@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"

print("Testing Supabase connection pooler on port 5432...")
try:
    engine = sa.create_engine(URL, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        res = conn.execute(sa.text("SELECT 1")).scalar()
        print(f"Success! DB response: {res}")
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)
