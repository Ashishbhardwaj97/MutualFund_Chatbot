import sqlite3

try:
    conn = sqlite3.connect("data/vectordb/chroma.sqlite3")
    cursor = conn.cursor()
    
    # List all tables in the SQLite database
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tables in ChromaDB:", tables)
    
    # If collections table exists, print its contents
    if "collections" in tables:
        cursor.execute("SELECT * FROM collections;")
        rows = cursor.fetchall()
        print("\nCollections Table:")
        for r in rows:
            print(r)
            
    # If segments table exists, print its contents
    if "segments" in tables:
        cursor.execute("SELECT * FROM segments;")
        rows = cursor.fetchall()
        print("\nSegments Table:")
        for r in rows:
            print(r)
            
    conn.close()
except Exception as e:
    print("Error reading SQLite database:", str(e))
