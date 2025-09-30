from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

app = Flask(__name__)

app.secret_key = 'supersecretkey'
DATABASE = 'database.db'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Cargar variables de entorno desde .env y mostrar la API key
from dotenv import load_dotenv
load_dotenv()
import os
print("API KEY:", os.getenv('OPENAI_API_KEY'))

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
import openai
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()
print("API KEY:", os.getenv('OPENAI_API_KEY'))
openai.api_key = os.getenv('OPENAI_API_KEY')

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
    prompt = (
        "Extrae toda la información relevante de la siguiente historia clínica en formato JSON, "
        "incluyendo nombre y cédula del paciente, edad, diagnóstico, antecedentes, tratamientos, fecha, y cualquier otro dato importante. "
        "Si algún dato no está presente, pon el valor como null.\n\nHistoria clínica:\n\n" + text + "\n\nEjemplo de respuesta:\n{\n  'nombre': 'Juan Perez',\n  'cedula': '123456789',\n  'edad': 45,\n  'diagnostico': 'Hipertensión',\n  'antecedentes': 'Ninguno',\n  'tratamientos': 'Enalapril',\n  'fecha': '2023-09-30',\n  ...otros campos...\n}"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message['content']
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
            # Intentar parsear JSON de la respuesta de OpenAI
            import json
            nombre, cedula = None, None
            datos_extraidos = {}
            try:
                # Reemplazar comillas simples por dobles para parsear JSON
                info_json = info.replace("'", '"')
                datos_extraidos = json.loads(info_json)
                nombre = datos_extraidos.get('nombre')
                cedula = datos_extraidos.get('cedula')
            except Exception:
                # Si no es JSON, intentar extraer manualmente
                import re
                match = re.search(r"nombre[:\s]*([\w\s]+).*cedula[:\s]*([\w\d]+)", info, re.I|re.S)
                if match:
                    nombre = match.group(1).strip()
                    cedula = match.group(2).strip()
                else:
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
                # Guardar toda la info extraída en la historia clínica
                db.execute('INSERT INTO historias (usuario_id, contenido, archivo) VALUES (?, ?, ?)', (user['id'], json.dumps(datos_extraidos, ensure_ascii=False), filename))
                db.commit()
                db.close()
                flash('Documento cargado y datos extraídos correctamente.')
                return redirect(url_for('admin_upload'))
            else:
                flash('No se pudo extraer nombre y cédula. Respuesta OpenAI: {}'.format(info))
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
    app.run(debug=True, host="0.0.0.0")
