import datetime
import json
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory

from apscheduler.schedulers.background import BackgroundScheduler
import enviar_alertas 

app = Flask(__name__) 
app.secret_key = 'mathias123' 

DATA_FILE = "data/flota_data.json"

# --- AQUI RESTAURAMOS TU CONTRASEÑA REAL ---
USUARIO_ADMIN = "admin"
PASSWORD_ADMIN = "Elmanantial445." 

# --- LOGIN ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_logueado' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"error": "No autorizado"}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form['username']
        password = request.form['password']
        if usuario == USUARIO_ADMIN and password == PASSWORD_ADMIN:
            session['usuario_logueado'] = True
            return redirect(url_for('dashboard'))
        else:
            error = 'Usuario o contraseña incorrectos'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('usuario_logueado', None)
    # ESTO CORRIGE EL ERROR DEL .HTML
    return redirect(url_for('login')) 

# --- HELPERS ---
def cargar_datos():
    if not os.path.exists(DATA_FILE):
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def guardar_datos_en_archivo(datos):
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
        return True
    except IOError:
        return False

# --- SCHEDULER ---
def iniciar_programador():
    try:
        scheduler = BackgroundScheduler()
        if hasattr(enviar_alertas, 'tarea_diaria'):
            scheduler.add_job(enviar_alertas.tarea_diaria, 'cron', hour=8, minute=0)
        if hasattr(enviar_alertas, 'enviar_copia_seguridad'):
            scheduler.add_job(enviar_alertas.enviar_copia_seguridad, 'cron', day_of_week='fri', hour=9, minute=0)
        scheduler.start()
    except Exception as e:
        print(f"Advertencia: {e}")

iniciar_programador()

# --- RUTAS ---

@app.route('/')
@login_required
def dashboard():
    return render_template('index.html')

@app.route('/api/flota', methods=['GET'])
@login_required
def api_get_flota():
    return jsonify(cargar_datos())

@app.route('/api/guardar_flota', methods=['POST'])
@login_required
def api_save_flota():
    nuevos_datos = request.json
    if guardar_datos_en_archivo(nuevos_datos):
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error"}), 500

@app.route('/<path:path>')
@login_required
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)