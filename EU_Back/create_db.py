import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

try:
    # 기본 postgres DB에 붙어서 새로운 DB 생성
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="qkrcks78",
        host="localhost",
        port="5432"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE eu_ai_db;")
    print("Database eu_ai_db created successfully.")
    cursor.close()
    conn.close()
except psycopg2.errors.DuplicateDatabase:
    print("Database eu_ai_db already exists.")
except Exception as e:
    print(f"Error: {e}")
