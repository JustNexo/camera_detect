import sqlite3

def create_database():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Cameras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL,
        name TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Colors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        lower_bound TEXT NOT NULL,
        upper_bound TEXT NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camera_id INTEGER NOT NULL,
        color_id INTEGER NOT NULL,
        access_granted BOOLEAN NOT NULL,
        UNIQUE(camera_id, color_id),
        FOREIGN KEY (camera_id) REFERENCES Cameras(id),
        FOREIGN KEY (color_id) REFERENCES Colors(id)
    )
    """)
    
    conn.commit()
    conn.close()

def add_camera(url, name):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Cameras (url, name) VALUES (?, ?)", (url, name))
    conn.commit()
    conn.close()
    
def update_camera_name(camera_id, new_name):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE Cameras SET name = ? WHERE id = ?", (new_name, camera_id))
    conn.commit()
    conn.close()
def delete_camera(camera_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Cameras WHERE id = ?", (camera_id,))
    conn.commit()
    conn.close()

def get_cameras():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Cameras")
    cameras = cursor.fetchall()
    conn.close()
    return cameras

def add_color(name, lower_bound, upper_bound):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Colors (name, lower_bound, upper_bound) VALUES (?, ?, ?)",
                   (name, str(lower_bound.tolist()), str(upper_bound.tolist())))
    conn.commit()
    conn.close()

def delete_color(color_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Colors WHERE id = ?", (color_id,))
    conn.commit()
    conn.close()

def add_rule(camera_id, color_id, access_granted):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO Rules (camera_id, color_id, access_granted)
    VALUES (?, ?, ?)
    ON CONFLICT(camera_id, color_id) DO UPDATE SET access_granted=excluded.access_granted
    """, (camera_id, color_id, access_granted))
    conn.commit()
    conn.close()

def delete_rule(rule_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()

def get_rule_for_camera(camera_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT access_granted, color_id FROM Rules WHERE camera_id = ?", (camera_id,))
    rule = cursor.fetchone()
    conn.close()
    return rule

def get_color_name(color_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM Colors WHERE id = ?", (color_id,))
    color = cursor.fetchone()
    conn.close()
    return color[0] if color else "Неизвестный цвет"

def get_colors():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM Colors")
    colors = cursor.fetchall()
    conn.close()
    return colors

def update_camera_url(camera_id, new_url):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE Cameras SET url = ? WHERE id = ?", (new_url, camera_id))
    conn.commit()
    conn.close()