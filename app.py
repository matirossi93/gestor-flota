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
USERS_FILE = os.path.join(BASE_DIR, "data", "users.json")
AUDIT_FILE = os.path.join(BASE_DIR, "data", "audit_log.json")

# --- HELPERS ---
def cargar_json(archivo):
    if not os.path.exists(archivo):
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        return [] if archivo in (DATA_FILE, AUDIT_FILE) else {}
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return [] if archivo in (DATA_FILE, AUDIT_FILE) else {}

def guardar_json(archivo, datos):
    try:
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
        return True
    except:
        return False

# --- AUDIT LOG ---
def log_audit(user, action, details=""):
    logs = cargar_json(AUDIT_FILE)
    if not isinstance(logs, list):
        logs = []
    logs.insert(0, {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user,
        "action": action,
        "details": details
    })
    if len(logs) > 500:
        logs = logs[:500]
    guardar_json(AUDIT_FILE, logs)

# --- USER MANAGEMENT ---
def cargar_usuarios():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    # Migration: create users.json from env vars on first run
    users = [
        {
            "username": "admin",
            "password_hash": generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin123')),
            "role": "admin"
        },
        {
            "username": "invitado",
            "password_hash": generate_password_hash(os.environ.get('GUEST_PASSWORD', 'invitado')),
            "role": "lector"
        }
    ]
    guardar_json(USERS_FILE, users)
    return users

def buscar_usuario(username):
    for u in cargar_usuarios():
        if u['username'] == username:
            return u
    return None

# --- DECORADORES DE SEGURIDAD ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_actual' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"error": "No autorizado"}), 401
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

# --- AUTH ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        u = buscar_usuario(user)
        if u and check_password_hash(u['password_hash'], pwd):
            session['usuario_actual'] = user
            session['rol_usuario'] = u['role']
            log_audit(user, "login", "Inicio de sesión")
            return redirect(url_for('dashboard'))
        else:
            error = 'Usuario o contraseña incorrectos'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    user = session.get('usuario_actual', '?')
    log_audit(user, "logout", "Cierre de sesión")
    session.clear()
    return redirect(url_for('login'))

# --- SCHEDULER ---
def iniciar_programador():
    try:
        s = BackgroundScheduler()
        if hasattr(enviar_alertas, 'tarea_diaria'):
            s.add_job(enviar_alertas.tarea_diaria, 'cron', hour=8, minute=0)
        if hasattr(enviar_alertas, 'enviar_copia_seguridad'):
            s.add_job(enviar_alertas.enviar_copia_seguridad, 'cron', day_of_week='fri', hour=9, minute=0)
        s.start()
    except:
        pass
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
    body = request.json
    # Support audit metadata: {flota: [...], audit: {action, details}}
    if isinstance(body, dict) and 'flota' in body:
        flota = body['flota']
        audit = body.get('audit', {})
    else:
        flota = body
        audit = {}
    if guardar_json(DATA_FILE, flota):
        if audit:
            log_audit(session.get('usuario_actual', '?'), audit.get('action', ''), audit.get('details', ''))
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

@app.route('/api/config', methods=['GET'])
@login_required
def api_get_config():
    c = cargar_json(CONFIG_FILE)
    if not c:
        c = {"diasAviso": 30, "emailAlertas": "datos@semilleroelmanantial.com"}
    return jsonify(c)

@app.route('/api/cleanup', methods=['POST'])
@login_required
@admin_required
def api_cleanup():
    """Elimina camiones que no estén en la lista de patentes válidas"""
    body = request.json
    patentes_validas = [p.strip().upper() for p in body.get('patentes', [])]
    if not patentes_validas:
        return jsonify({"status": "error", "message": "Enviar lista de patentes válidas"}), 400
    flota = cargar_json(DATA_FILE)
    antes = len(flota)
    flota = [c for c in flota if c.get('patente', '').upper() in patentes_validas]
    despues = len(flota)
    guardar_json(DATA_FILE, flota)
    eliminados = antes - despues
    log_audit(session.get('usuario_actual', '?'), "cleanup", f"Limpieza: {eliminados} unidades eliminadas, {despues} conservadas")
    return jsonify({"status": "success", "eliminados": eliminados, "conservados": despues})

@app.route('/api/toggle_activo/<int:truck_id>', methods=['POST'])
@login_required
@admin_required
def api_toggle_activo(truck_id):
    """Activa/desactiva un camión (no genera alertas si está inactivo)"""
    flota = cargar_json(DATA_FILE)
    truck = next((c for c in flota if c.get('id') == truck_id), None)
    if not truck:
        return jsonify({"status": "error", "message": "Unidad no encontrada"}), 404
    truck['activo'] = not truck.get('activo', True)
    guardar_json(DATA_FILE, flota)
    estado = "activada" if truck['activo'] else "desactivada"
    log_audit(session.get('usuario_actual', '?'), "toggle_activo", f"{truck.get('patente','')} {estado}")
    return jsonify({"status": "success", "activo": truck['activo']})

@app.route('/api/guardar_config', methods=['POST'])
@login_required
@admin_required
def api_save_config():
    if guardar_json(CONFIG_FILE, request.json):
        log_audit(session.get('usuario_actual', '?'), "update_config", "Configuración actualizada")
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

# --- AUDIT API ---
@app.route('/api/audit_log', methods=['GET'])
@login_required
@admin_required
def api_get_audit():
    return jsonify(cargar_json(AUDIT_FILE))

# --- USER API ---
@app.route('/api/users', methods=['GET'])
@login_required
@admin_required
def api_get_users():
    users = cargar_usuarios()
    return jsonify([{"username": u["username"], "role": u["role"]} for u in users])

@app.route('/api/users', methods=['POST'])
@login_required
@admin_required
def api_create_user():
    body = request.json
    username = body.get('username', '').strip().lower()
    password = body.get('password', '')
    role = body.get('role', 'lector')
    if not username or not password:
        return jsonify({"status": "error", "message": "Usuario y contraseña requeridos"}), 400
    if role not in ('admin', 'lector'):
        return jsonify({"status": "error", "message": "Rol inválido"}), 400
    users = cargar_usuarios()
    if any(u['username'] == username for u in users):
        return jsonify({"status": "error", "message": "El usuario ya existe"}), 400
    users.append({
        "username": username,
        "password_hash": generate_password_hash(password),
        "role": role
    })
    guardar_json(USERS_FILE, users)
    log_audit(session.get('usuario_actual', '?'), "create_user", f"Usuario creado: {username} ({role})")
    return jsonify({"status": "success"})

@app.route('/api/users/<username>', methods=['PUT'])
@login_required
@admin_required
def api_update_user(username):
    body = request.json
    users = cargar_usuarios()
    user = next((u for u in users if u['username'] == username), None)
    if not user:
        return jsonify({"status": "error", "message": "Usuario no encontrado"}), 404
    if body.get('role') and body['role'] in ('admin', 'lector'):
        user['role'] = body['role']
    if body.get('password'):
        user['password_hash'] = generate_password_hash(body['password'])
    guardar_json(USERS_FILE, users)
    log_audit(session.get('usuario_actual', '?'), "update_user", f"Usuario actualizado: {username}")
    return jsonify({"status": "success"})

@app.route('/api/users/<username>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_user(username):
    if username == session.get('usuario_actual'):
        return jsonify({"status": "error", "message": "No podés eliminar tu propio usuario"}), 400
    users = cargar_usuarios()
    users = [u for u in users if u['username'] != username]
    guardar_json(USERS_FILE, users)
    log_audit(session.get('usuario_actual', '?'), "delete_user", f"Usuario eliminado: {username}")
    return jsonify({"status": "success"})

# --- STATIC ---
@app.route('/<path:path>')
@login_required
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
