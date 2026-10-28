from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
from collections import deque
import time

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': ' ',
    'database': 'firex',
    'port': 3306
}

# Updated room connections - Backyard and EXIT_LIVING_ROOM are both exits
ROOM_CONNECTIONS = {
    'Kitchen': ['Living Room', 'Backyard'],
    'Living Room': ['Kitchen', 'Bedroom 1', 'Bedroom 2', 'EXIT_LIVING_ROOM'],
    'Bedroom 1': ['Living Room', 'Wash Room 1'],
    'Bedroom 2': ['Living Room', 'Wash Room 2'],
    'Backyard': [],  # Backyard is an exit
    'Wash Room 1': ['Bedroom 1'],
    'Wash Room 2': ['Bedroom 2'],
    'EXIT_LIVING_ROOM': []  # Living Room exit
}

# Define which rooms are exits
EXIT_ROOMS = {'Backyard', 'EXIT_LIVING_ROOM'}

person_movements = {}

def get_db_connection():
    """Connect to MySQL database"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"❌ Database Error: {e}")
        return None

def find_safest_path(start_room, rooms_with_fire):
    """
    BFS algorithm to find shortest path avoiding fire to nearest exit
    Returns path to closest safe exit
    """
    if start_room in EXIT_ROOMS:
        return [start_room], 0, start_room
    
    if not start_room or start_room == 'Unknown':
        return None, None, None
    
    queue = deque([(start_room, [start_room])])
    visited = {start_room}
    
    while queue:
        current, path = queue.popleft()
        
        # Check if we reached any exit
        if current in EXIT_ROOMS:
            return path, len(path) - 1, current
        
        for neighbor in ROOM_CONNECTIONS.get(current, []):
            if neighbor in visited:
                continue
            # Allow passing through exits, but not through fire
            if neighbor in rooms_with_fire and neighbor not in EXIT_ROOMS:
                continue
                
            visited.add(neighbor)
            queue.append((neighbor, path + [neighbor]))
    
    return None, None, None

def calculate_all_escape_routes(rooms_data):
    """Calculate escape routes for all rooms to nearest exit"""
    rooms_with_fire = set(room['room_id'] for room in rooms_data if room['fire'])
    
    escape_routes = {}
    
    for room in rooms_data:
        if room['room_id'] in EXIT_ROOMS:
            escape_routes[room['room_id']] = {
                'path': [room['room_id']],
                'distance': 0,
                'safe': True,
                'has_fire': False,
                'has_person': room.get('person', False),
                'exit_used': room['room_id']
            }
        else:
            path, distance, exit_used = find_safest_path(room['room_id'], rooms_with_fire)
            
            escape_routes[room['room_id']] = {
                'path': path,
                'distance': distance,
                'safe': path is not None,
                'has_fire': room['fire'],
                'has_person': room.get('person', False),
                'exit_used': exit_used
            }
    
    return escape_routes

@app.route('/')
def home():
    return jsonify({
        'status': 'running',
        'message': '🔥 Fire Detection API',
        'database': DB_CONFIG['database'],
        'exits': ['Backyard', 'EXIT_LIVING_ROOM']
    })

@app.route('/api/rooms', methods=['GET'])
def get_rooms():
    """Get all rooms including exits"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM rooms ORDER BY room_id")
        rooms = cursor.fetchall()
        
        for room in rooms:
            room['fire'] = bool(room['fire'])
            room['person'] = bool(room['person'])
            room['created_at'] = str(room['created_at'])
            room['updated_at'] = str(room['updated_at'])
        
        # Add virtual exit room for Living Room exit
        exit_rooms = [
            {
                'room_id': 'EXIT_LIVING_ROOM',
                'fire': False,
                'person': False,
                'created_at': str(time.time()),
                'updated_at': str(time.time())
            }
        ]
        
        existing_ids = [r['room_id'] for r in rooms]
        for exit_room in exit_rooms:
            if exit_room['room_id'] not in existing_ids:
                rooms.append(exit_room)
        
        cursor.close()
        conn.close()
        return jsonify(rooms)
    except Error as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/people', methods=['GET'])
def get_people():
    """Get all people with their escape routes and movement progress"""
    if person_movements:
        update_all_movements()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM people ORDER BY person_id")
        people = cursor.fetchall()
        
        cursor.execute("SELECT * FROM rooms")
        rooms = cursor.fetchall()
        rooms_with_fire = set(room['room_id'] for room in rooms if room['fire'])
        
        for person in people:
            person['created_at'] = str(person['created_at'])
            person['updated_at'] = str(person['updated_at'])
            
            movement_key = str(person['person_id'])
            if movement_key in person_movements:
                person['is_moving'] = True
                person['current_position'] = person_movements[movement_key]['current_position']
                person['movement_progress'] = person_movements[movement_key]['progress']
                person['target_room'] = person_movements[movement_key]['target_room']
                person['remaining_path'] = person_movements[movement_key]['remaining_path']
            else:
                person['is_moving'] = False
                person['current_position'] = person['room_id']
                person['movement_progress'] = 0
                person['target_room'] = None
                person['remaining_path'] = []
            
            if person['room_id']:
                if person['room_id'] in EXIT_ROOMS:
                    person['escape_route'] = {
                        'path': ['Already Outside'],
                        'distance': 0,
                        'safe': True,
                        'exit_used': person['room_id']
                    }
                else:
                    path, distance, exit_used = find_safest_path(person['room_id'], rooms_with_fire)
                    person['escape_route'] = {
                        'path': path,
                        'distance': distance,
                        'safe': path is not None,
                        'exit_used': exit_used
                    }
            else:
                person['escape_route'] = {
                    'path': ['Unknown Location'],
                    'distance': 0,
                    'safe': False,
                    'exit_used': None
                }
        
        cursor.close()
        conn.close()
        return jsonify(people)
    except Error as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/escape-routes', methods=['GET'])
def get_escape_routes():
    """Get escape routes for all rooms"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM rooms")
        rooms = cursor.fetchall()
        
        for room in rooms:
            room['fire'] = bool(room['fire'])
            room['person'] = bool(room.get('person', False))
        
        rooms.append({'room_id': 'EXIT_LIVING_ROOM', 'fire': False, 'person': False})
        
        escape_routes = calculate_all_escape_routes(rooms)
        
        cursor.close()
        conn.close()
        return jsonify(escape_routes)
    except Error as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/start-evacuation/<int:person_id>', methods=['POST'])
def start_evacuation(person_id):
    """Start moving a person along their escape route"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM people WHERE person_id = %s", (person_id,))
        person = cursor.fetchone()
        
        if not person:
            return jsonify({'error': 'Person not found'}), 404
        
        if not person['room_id'] or person['room_id'] == 'Unknown':
            return jsonify({'error': 'Cannot evacuate from unknown location'}), 400
        
        if person['room_id'] in EXIT_ROOMS:
            return jsonify({'error': 'Person is already outside'}), 400
        
        cursor.execute("SELECT * FROM rooms")
        rooms = cursor.fetchall()
        rooms_with_fire = set(room['room_id'] for room in rooms if room['fire'])
        
        path, distance, exit_used = find_safest_path(person['room_id'], rooms_with_fire)
        
        if not path:
            return jsonify({'error': 'No safe escape route available'}), 400
        
        person_movements[str(person_id)] = {
            'person_id': person_id,
            'escape_path': path,
            'current_step': 0,
            'current_position': person['room_id'],
            'target_room': path[1] if len(path) > 1 else path[0],
            'remaining_path': path[1:],
            'progress': 0,
            'started_at': time.time(),
            'last_update': time.time()
        }
        
        cursor.close()
        conn.close()
        
        print(f"✅ Started evacuation for person {person_id}: {path} → {exit_used}")
        
        return jsonify({
            'success': True,
            'person_id': person_id,
            'escape_path': path,
            'exit_used': exit_used
        })
    except Error as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/movement-progress', methods=['GET'])
def get_movement_progress():
    """Get current movement progress"""
    update_all_movements()
    return jsonify(person_movements)

def update_all_movements():
    """Update all person movements"""
    if not person_movements:
        return
        
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        movements_to_remove = []
        
        for person_key, movement in list(person_movements.items()):
            current_time = time.time()
            elapsed_since_update = current_time - movement['last_update']
            
            if elapsed_since_update >= 5:
                if len(movement['remaining_path']) > 0:
                    next_room = movement['remaining_path'][0]
                    movement['current_position'] = next_room
                    movement['remaining_path'] = movement['remaining_path'][1:]
                    movement['last_update'] = current_time
                    movement['progress'] = 0
                    
                    if len(movement['remaining_path']) > 0:
                        movement['target_room'] = movement['remaining_path'][0]
                    else:
                        movement['target_room'] = None
                    
                    cursor.execute(
                        "UPDATE people SET room_id = %s, updated_at = CURRENT_TIMESTAMP WHERE person_id = %s",
                        (next_room, movement['person_id'])
                    )
                    conn.commit()
                    
                    print(f"✅ Person {movement['person_id']} moved to {next_room}")
                    
                    if next_room in EXIT_ROOMS:
                        cursor.execute(
                            "UPDATE people SET status = 'Safe' WHERE person_id = %s",
                            (movement['person_id'],)
                        )
                        conn.commit()
                        movements_to_remove.append(person_key)
                        print(f"✅ Person {movement['person_id']} reached exit: {next_room}")
                    else:
                        cursor.execute("SELECT * FROM rooms")
                        rooms = cursor.fetchall()
                        rooms_with_fire = set(room['room_id'] for room in rooms if room['fire'])
                        
                        new_path, _, new_exit = find_safest_path(next_room, rooms_with_fire)
                        
                        if new_path and len(new_path) > 1:
                            movement['remaining_path'] = new_path[1:]
                            movement['target_room'] = new_path[1] if len(new_path) > 1 else None
                            print(f"🔄 Recalculated path for person {movement['person_id']}: {new_path} → {new_exit}")
                        else:
                            movements_to_remove.append(person_key)
                            print(f"⚠️ No safe path for person {movement['person_id']}")
                else:
                    movements_to_remove.append(person_key)
            else:
                step_progress = (elapsed_since_update / 5) * 100
                movement['progress'] = min(100, step_progress)
        
        for person_key in movements_to_remove:
            if person_key in person_movements:
                del person_movements[person_key]
        
        cursor.close()
        conn.close()
        return jsonify(person_movements)
    except Error as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get active fire alerts"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT room_id, fire, person, updated_at 
            FROM rooms 
            WHERE fire = TRUE
            ORDER BY updated_at DESC
        """)
        alerts = cursor.fetchall()
        
        for alert in alerts:
            alert['fire'] = bool(alert['fire'])
            alert['person'] = bool(alert['person'])
            alert['updated_at'] = str(alert['updated_at'])
        
        cursor.close()
        conn.close()
        return jsonify(alerts)
    except Error as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-room', methods=['POST'])
def update_room():
    """Update room status"""
    data = request.json
    room_id = data.get('room_id')
    fire = data.get('fire')
    person = data.get('person')
    
    if not room_id:
        return jsonify({'error': 'room_id is required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        if fire is not None and person is not None:
            cursor.execute(
                "UPDATE rooms SET fire = %s, person = %s WHERE room_id = %s",
                (fire, person, room_id)
            )
        elif fire is not None:
            cursor.execute(
                "UPDATE rooms SET fire = %s WHERE room_id = %s",
                (fire, room_id)
            )
        elif person is not None:
            cursor.execute(
                "UPDATE rooms SET person = %s WHERE room_id = %s",
                (person, room_id)
            )
        
        if fire:
            cursor.execute(
                "UPDATE people SET status = 'Not Safe' WHERE room_id = %s",
                (room_id,)
            )
        else:
            cursor.execute(
                "UPDATE people SET status = 'Safe' WHERE room_id = %s AND room_id NOT IN ('Backyard', 'EXIT_LIVING_ROOM')",
                (room_id,)
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Updated {room_id}: fire={fire}, person={person}")
        return jsonify({'success': True, 'message': f'Room {room_id} updated'})
    except Error as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-all-fires', methods=['POST'])
def clear_all_fires():
    """Clear all fires"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE rooms SET fire = FALSE")
        cursor.execute("UPDATE people SET status = 'Safe'")
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ All fires cleared")
        return jsonify({'success': True, 'message': 'All fires cleared'})
    except Error as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/simulate-emergency', methods=['POST'])
def simulate_emergency():
    """Simulate emergency - fires in ALL rooms except exits"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE rooms SET fire = TRUE 
            WHERE room_id NOT IN ('Backyard', 'EXIT_LIVING_ROOM')
        """)
        cursor.execute("""
            UPDATE people SET status = 'Not Safe' 
            WHERE room_id IS NOT NULL 
            AND room_id NOT IN ('Backyard', 'EXIT_LIVING_ROOM')
        """)
        conn.commit()
        cursor.close()
        conn.close()
        
        print("⚠️ FULL EMERGENCY simulated!")
        return jsonify({'success': True, 'message': 'Emergency simulated in ALL rooms!'})
    except Error as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset-people-locations', methods=['POST'])
def reset_people_locations():
    """Reset people to their original rooms"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE people SET room_id = 'Bedroom 1', status = 'Safe' WHERE name = 'Amrita'")
        cursor.execute("UPDATE people SET room_id = 'Bedroom 2', status = 'Safe' WHERE name = 'Misha'")
        cursor.execute("UPDATE people SET room_id = 'Kitchen', status = 'Safe' WHERE name = 'Jatin'")
        cursor.execute("UPDATE people SET room_id = 'Living Room', status = 'Safe' WHERE name = 'Ayush'")
        cursor.execute("UPDATE people SET room_id = NULL, status = 'Safe' WHERE name = 'Harry'")
        conn.commit()
        
        global person_movements
        person_movements.clear()
        
        cursor.close()
        conn.close()
        
        print("✅ People locations reset!")
        return jsonify({'success': True, 'message': 'People locations reset to original rooms!'})
    except Error as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("="*70)
    print("🔥 FIRE DETECTION API")
    print("="*70)
    print("\n✅ TWO EXITS: Backyard & Living Room Exit")
    print("✅ Movement updates every 5 seconds")
    print("\n📡 Starting server on: http://localhost:5000")
    print("="*70)
    
    app.run(host='0.0.0.0', port=5000, debug=True)