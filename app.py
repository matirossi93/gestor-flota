import datetime
import json
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory

# --- IMPORTAMOS EL PROGRAMADOR Y TU SCRIPT DE ALERTAS ---
from apscheduler.schedulers.background import BackgroundScheduler
import enviar_alertas

app = Flask(__name__, template_folder='.') # Importante: busca templates en la raíz
app.secret_key = 'mathias123' 

# Ruta del archivo de datos (Coincide con el volumen /app/data de Easypanel)
DATA_FILE = "data/flota_data.json"

# --- CREDENCIALES DE ACCESO ---
USUARIO_ADMIN = "admin"
PASSWORD_ADMIN = "Elmanantial445." 

# ==========================================
#   SEGURIDAD (LOGIN)
# ==========================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_logueado' not in session:
            # Si intenta entrar a la API sin login, error 401
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
    # Usamos un template simple de login o el que ya tenías
    # Si no tienes login.html, avísame y te paso uno integrado
    if os.path.exists('login.html'):
        return render_template('login.html', error=error)
    else:
        return '''
        <form method="post">
            <p><input type=text name=username placeholder="Usuario"></p>
            <p><input type=password name=password placeholder="Contraseña"></p>
            <p><input type=submit value=Login></p>
            <p style="color:red">''' + (error or '') + '''</p>
        </form>
        '''

@app.route('/logout')
def logout():
    session.pop('usuario_logueado', None)
    return redirect(url_for('login'))

# ==========================================
#   FUNCIONES DE AYUDA (BACKEND)
# ==========================================

def cargar_datos():
    if not os.path.exists(DATA_FILE):
        # Intentamos crear la carpeta si no existe
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error al leer datos: {e}")
        return []

def guardar_datos_en_archivo(datos):
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"Error crítico al guardar: {e}")
        return False

# ==========================================
#   PROGRAMADOR AUTOMÁTICO (CRON)
# ==========================================
def iniciar_programador():
    try:
        scheduler = BackgroundScheduler()
        
        # 1. Alertas Diarias (Todos los días a las 8:00 AM)
        scheduler.add_job(enviar_alertas.tarea_diaria, 'cron', hour=8, minute=0)
        
        # 2. Copia de Seguridad (Todos los VIERNES a las 9:00 AM)
        scheduler.add_job(enviar_alertas.enviar_copia_seguridad, 'cron', day_of_week='fri', hour=9, minute=0)
        
        scheduler.start()
        print("⏰ Programador iniciado: Alertas (Diario 8AM) + Backup (Viernes 9AM)")
    except Exception as e:
        print(f"Error iniciando programador: {e}")

# Iniciamos el reloj al arrancar la app
iniciar_programador()

# ==========================================
#   RUTAS PRINCIPALES (APP MODERNA)
# ==========================================

@app.route('/')
@login_required
def dashboard():
    # Sirve el nuevo index.html (React-style)
    # Asegúrate de que el archivo se llame 'index.html' y esté en la misma carpeta
    return send_from_directory('.', 'index.html')

# ==========================================
#   API JSON (CONEXIÓN CON EL NUEVO DISEÑO)
# ==========================================

@app.route('/api/flota', methods=['GET'])
@login_required
def api_get_flota():
    """Devuelve el JSON crudo para que el JS lo procese"""
    datos = cargar_datos()
    return jsonify(datos)

@app.route('/api/guardar_flota', methods=['POST'])
@login_required
def api_save_flota():
    """Recibe el JSON completo modificado por el JS y lo guarda"""
    nuevos_datos = request.json
    if not isinstance(nuevos_datos, list):
        return jsonify({"status": "error", "message": "Formato de datos incorrecto"}), 400
    
    if guardar_datos_en_archivo(nuevos_datos):
        return jsonify({"status": "success", "message": "Guardado correctamente"})
    else:
        return jsonify({"status": "error", "message": "Error de escritura en servidor"}), 500

# Configuración para servir archivos estáticos si hiciera falta (imágenes, etc)
@app.route('/<path:path>')
@login_required
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    # Escuchar en el puerto 80 para EasyPanel
    app.run(debug=True, host='0.0.0.0', port=80)