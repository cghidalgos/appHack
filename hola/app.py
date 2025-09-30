from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from dotenv import load_dotenv

# Cargar variables de entorno (solo si el archivo .env existe)
try:
    load_dotenv()
except:
    pass  # En producción las variables se configuran directamente en el servidor

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')

# Configuración de base de datos con ruta absoluta
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def init_database():
    """Inicializa la base de datos si no existe"""
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
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
        print(f"Base de datos inicializada en: {DATABASE}")

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if password == '12345':
            session['username'] = username
            session['role'] = request.form['role']
            if session['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Contraseña incorrecta')
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

@app.route('/user')
def user_dashboard():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    return render_template('user_dashboard.html')

# Aquí irán las rutas para cargar documentos, extraer info, buscar usuarios, etc.
# Ruta para cargar documento y extraer información
from werkzeug.utils import secure_filename
from openai import OpenAI
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image

# Configura el cliente de OpenAI usando variable de entorno
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def extract_text_from_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf':
        reader = PdfReader(filepath)
        text = "\n".join(page.extract_text() or '' for page in reader.pages)
        return text
    elif ext in ['.doc', '.docx']:
        doc = Document(filepath)
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext in ['.png', '.jpg', '.jpeg']:
        try:
            import pytesseract
            img = Image.open(filepath)
            return pytesseract.image_to_string(img)
        except Exception:
            return "No se pudo extraer texto de la imagen."
    return ""

def extract_info_with_openai(text):
    prompt = f"Extrae el nombre y la cédula de la siguiente historia clínica. Si no hay, responde 'No encontrado'.\n\n{text}"
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error al extraer información: {e}"

@app.route('/admin/upload', methods=['GET', 'POST'])
def admin_upload():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            text = extract_text_from_file(filepath)
            info = extract_info_with_openai(text)
            # Extraer nombre y cédula del resultado de OpenAI
            nombre, cedula = None, None
            import re
            match = re.search(r"nombre[:\s]*([\w\s]+).*cedula[:\s]*([\w\d]+)", info, re.I|re.S)
            if match:
                nombre = match.group(1).strip()
                cedula = match.group(2).strip()
            else:
                # Intentar encontrar por líneas
                for line in info.splitlines():
                    if 'nombre' in line.lower():
                        nombre = line.split(':')[-1].strip()
                    if 'cedula' in line.lower():
                        cedula = line.split(':')[-1].strip()
            if nombre and cedula:
                db = get_db()
                user = db.execute('SELECT * FROM usuarios WHERE cedula = ?', (cedula,)).fetchone()
                if not user:
                    db.execute('INSERT INTO usuarios (nombre, cedula) VALUES (?, ?)', (nombre, cedula))
                    db.commit()
                    user = db.execute('SELECT * FROM usuarios WHERE cedula = ?', (cedula,)).fetchone()
                db.execute('INSERT INTO historias (usuario_id, contenido, archivo) VALUES (?, ?, ?)', (user['id'], text, filename))
                db.commit()
                db.close()
                flash('Documento cargado y datos extraídos correctamente.')
            else:
                flash('No se pudo extraer nombre y cédula.')
            return redirect(url_for('admin_upload'))
    return render_template('admin_upload.html')

# Ruta para buscar usuario (admin)
@app.route('/admin/search', methods=['GET'])
def admin_search():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    cedula = request.args.get('cedula')
    nombre = request.args.get('nombre')
    db = get_db()
    usuario = None
    if cedula:
        usuario = db.execute('SELECT * FROM usuarios WHERE cedula = ?', (cedula,)).fetchone()
    elif nombre:
        usuario = db.execute('SELECT * FROM usuarios WHERE nombre LIKE ?', (f'%{nombre}%',)).fetchone()
    historias = []
    if usuario:
        historias = db.execute('SELECT * FROM historias WHERE usuario_id = ?', (usuario['id'],)).fetchall()
    db.close()
    return render_template('admin_result.html', usuario=usuario, historias=historias)

# Ruta para buscar historia clínica (usuario)
@app.route('/user/search', methods=['GET'])
def user_search():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    cedula = request.args.get('cedula')
    nombre = request.args.get('nombre')
    db = get_db()
    usuario = None
    if cedula:
        usuario = db.execute('SELECT * FROM usuarios WHERE cedula = ?', (cedula,)).fetchone()
    elif nombre:
        usuario = db.execute('SELECT * FROM usuarios WHERE nombre LIKE ?', (f'%{nombre}%',)).fetchone()
    historias = []
    if usuario:
        historias = db.execute('SELECT * FROM historias WHERE usuario_id = ?', (usuario['id'],)).fetchall()
    db.close()
    return render_template('user_result.html', usuario=usuario, historias=historias)

if __name__ == '__main__':
    # Inicializar base de datos al arrancar
    init_database()
    
    # Configuración para producción en Render
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
