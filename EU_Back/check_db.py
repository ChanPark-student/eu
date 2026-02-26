import psycopg2
try:
    conn = psycopg2.connect(dbname='eu_ai_db', user='postgres', password='qkrcks78', host='localhost', port='5432')
    cur = conn.cursor()
    cur.execute('SELECT * FROM verify_reports;')
    rows = cur.fetchall()
    print("ROWS IN DB:")
    for row in rows:
        print(row)
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
