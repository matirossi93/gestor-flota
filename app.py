import datetime
import json
import os
from dotenv import load_dotenv
load_dotenv()
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
import enviar_alertas

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'cambiar-en-produccion')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "flota_data.json")
CONFIG_FILE = os.path.join(BASE_DIR, "data", "config.json")

# --- GESTIÓN DE USUARIOS ---
USUARIOS = {
    "admin": {
        "pass": generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin123')),
        "rol": "admin"
    },
    "invitado": {
        "pass": generate_password_hash(os.environ.get('GUEST_PASSWORD', 'invitado')),
        "rol": "lector"
    }
}

# --- DECORADORES DE SEGURIDAD ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_actual' not in session:
            if request.path.startswith('/api/'): return jsonify({"error": "No autorizado"}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('rol_usuario') != 'admin':
            return jsonify({"status": "error", "message": "Permisos insuficientes (Modo Lectura)"}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']

        if user in USUARIOS and check_password_hash(USUARIOS[user]['pass'], pwd):
            session['usuario_actual'] = user
            session['rol_usuario'] = USUARIOS[user]['rol']
            return redirect(url_for('dashboard'))
        else:
            error = 'Usuario o contraseña incorrectos'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- HELPERS ---
def cargar_json(archivo):
    if not os.path.exists(archivo): os.makedirs(os.path.dirname(archivo), exist_ok=True); return [] if archivo == DATA_FILE else {}
    try:
        with open(archivo, 'r', encoding='utf-8') as f: return json.load(f)
    except: return [] if archivo == DATA_FILE else {}

def guardar_json(archivo, datos):
    try:
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        with open(archivo, 'w', encoding='utf-8') as f: json.dump(datos, f, indent=4, ensure_ascii=False)
        return True
    except: return False

# --- SCHEDULER ---
def iniciar_programador():
    try:
        s = BackgroundScheduler()
        if hasattr(enviar_alertas, 'tarea_diaria'): s.add_job(enviar_alertas.tarea_diaria, 'cron', hour=8, minute=0)
        if hasattr(enviar_alertas, 'enviar_copia_seguridad'): s.add_job(enviar_alertas.enviar_copia_seguridad, 'cron', day_of_week='fri', hour=9, minute=0)
        s.start()
    except: pass
iniciar_programador()

# --- RUTAS ---
@app.route('/')
@login_required
def dashboard():
    return render_template('index.html', rol=session.get('rol_usuario'))

@app.route('/api/flota', methods=['GET'])
@login_required
def api_get_flota():
    return jsonify(cargar_json(DATA_FILE))

@app.route('/api/guardar_flota', methods=['POST'])
@login_required
@admin_required
def api_save_flota():
    if guardar_json(DATA_FILE, request.json): return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

@app.route('/api/config', methods=['GET'])
@login_required
def api_get_config():
    c = cargar_json(CONFIG_FILE)
    if not c: c = {"diasAviso": 30, "emailAlertas": "datos@semilleroelmanantial.com"}
    return jsonify(c)

@app.route('/api/guardar_config', methods=['POST'])
@login_required
@admin_required
def api_save_config():
    if guardar_json(CONFIG_FILE, request.json): return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

@app.route('/<path:path>')
@login_required
def serve_static(path): return send_from_directory('.', path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
