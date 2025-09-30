import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    cedula TEXT UNIQUE
)
''')
c.execute('''
CREATE TABLE IF NOT EXISTS historias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    contenido TEXT,
    archivo TEXT,
    FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
)
''')
conn.commit()
conn.close()
