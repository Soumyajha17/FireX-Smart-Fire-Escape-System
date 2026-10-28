import mysql.connector

print("=" * 50)
print("🔍 Testing MySQL Connection")
print("=" * 50)

try:
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',  # Empty
        database='firex',
        port=3306
    )
    
    if connection.is_connected():
        print("✅ Connected to MySQL!")
        
        cursor = connection.cursor()
        
        # Check tables
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        print(f"✅ Tables: {[t[0] for t in tables]}")
        
        # Count data
        cursor.execute("SELECT COUNT(*) FROM rooms;")
        print(f"✅ Rooms: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM people;")
        print(f"✅ People: {cursor.fetchone()[0]}")
        
        # Show sample data
        cursor.execute("SELECT room_id, fire, person FROM rooms LIMIT 3;")
        rooms = cursor.fetchall()
        print("\n📊 Sample Rooms:")
        for room in rooms:
            print(f"   {room[0]}: Fire={room[1]}, Person={room[2]}")
        
        cursor.close()
        connection.close()
        
        print("\n" + "=" * 50)
        print("✅✅✅ CONNECTION SUCCESS! ✅✅✅")
        print("=" * 50)
        
except Exception as e:
    print(f"\n❌ ERROR: {e}\n")
    print("Troubleshooting:")
    print("  1. Is MySQL running in XAMPP?")
    print("  2. Is password empty in the code?")
    print("  3. Does 'firex' database exist?")
    print("=" * 50)