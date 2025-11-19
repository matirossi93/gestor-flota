import datetime
import json
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session

# --- IMPORTAMOS EL PROGRAMADOR Y TU SCRIPT DE ALERTAS ---
from apscheduler.schedulers.background import BackgroundScheduler
import enviar_alertas

app = Flask(__name__)
# CAMBIA ESTA LLAVE POR ALGO MÁS SEGURO SI QUIERES
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
    return redirect(url_for('login'))

# ==========================================
#   FUNCIONES DE AYUDA
# ==========================================

def verificar_fecha(fecha_str):
    if not fecha_str: return "SIN DATOS"
    try:
        fecha_vencimiento = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
        hoy = datetime.date.today()
        diferencia = (fecha_vencimiento - hoy).days
        if diferencia < 0:
            return f"VENCIDO (hace {-diferencia} días)"
        elif diferencia <= 30:
            return f"PRÓXIMO (vence en {diferencia} días)"
        else:
            return "OK"
    except ValueError:
        return "ERROR"

def verificar_service(camion):
    try:
        km_actual = camion.get("km_actual", 0)
        km_ultimo = camion["service"]["ultimo_km"]
        km_intervalo = camion["service"]["intervalo_km"]
        km_proximo_service = km_ultimo + km_intervalo
        camion["km_proximo_service"] = km_proximo_service
        diferencia_km = km_proximo_service - km_actual
        if diferencia_km < 0:
            return f"VENCIDO (hace {-diferencia_km} km)"
        elif diferencia_km <= 2000:
            return f"PRÓXIMO (faltan {diferencia_km} km)"
        else:
            return "OK"
    except (KeyError, TypeError):
        return "ERROR"

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

def guardar_datos(datos):
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error crítico al guardar: {e}")

def buscar_camion_por_id(lista_camiones, id_camion):
    for camion in lista_camiones:
        if camion["id"] == id_camion:
            return camion
    return None

def get_proximo_id(lista_camiones):
    if not lista_camiones: return 1
    max_id = max(camion.get('id', 0) for camion in lista_camiones)
    return max_id + 1

# ==========================================
#   PROGRAMADOR AUTOMÁTICO (CRON)
# ==========================================
def iniciar_programador():
    try:
        scheduler = BackgroundScheduler()
        
        # 1. Alertas Diarias (Todos los días a las 8:00 AM)
        scheduler.add_job(enviar_alertas.tarea_diaria, 'cron', hour=8, minute=0)
        
        # 2. Copia de Seguridad (Todos los VIERNES a las 9:00 AM)
        # day_of_week='fri' significa Viernes (mon, tue, wed, thu, fri, sat, sun)
        scheduler.add_job(enviar_alertas.enviar_copia_seguridad, 'cron', day_of_week='fri', hour=9, minute=0)
        
        scheduler.start()
        print("⏰ Programador iniciado: Alertas (Diario 8AM) + Backup (Viernes 9AM)")
    except Exception as e:
        print(f"Error iniciando programador: {e}")

# Iniciamos el reloj al arrancar la app
iniciar_programador()

# ==========================================
#   RUTAS WEB (DASHBOARD Y GESTIÓN)
# ==========================================

@app.route('/')
@login_required
def dashboard():
    lista_camiones = cargar_datos()
    for camion in lista_camiones:
        camion['estado_service'] = verificar_service(camion)
        camion['vencimientos_con_estado'] = []
        
        # Procesamos todos los vencimientos (incluyendo el nuevo Comanry)
        for tipo, fecha in camion.get("vencimientos", {}).items():
            estado_fecha = verificar_fecha(fecha)
            # 'replace' sirve para quitar guiones bajos (filtro_comanry -> filtro comanry)
            camion['vencimientos_con_estado'].append({
                "tipo": tipo.replace('_', ' '), 
                "fecha": fecha,
                "estado": estado_fecha
            })
    return render_template('index.html', lista_de_camiones=lista_camiones)

@app.route('/camion/<int:camion_id>')
@login_required
def detalle_camion(camion_id):
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion: return "No encontrado", 404
        
    camion['estado_service'] = verificar_service(camion)
    camion['vencimientos_con_estado'] = []
    for tipo, fecha in camion.get("vencimientos", {}).items():
        estado_fecha = verificar_fecha(fecha)
        camion['vencimientos_con_estado'].append({
            "tipo": tipo, 
            "fecha": fecha,
            "estado": estado_fecha
        })
    
    camion['historial_ordenado'] = sorted(camion.get("historial", []), key=lambda x: x['fecha'], reverse=True)
    return render_template('camion_detalle.html', camion=camion)

@app.route('/camion/nuevo', methods=['GET', 'POST'])
@login_required
def agregar_camion():
    if request.method == 'POST':
        lista_camiones = cargar_datos()
        try:
            nuevo_camion = {
                "id": get_proximo_id(lista_camiones),
                "patente": request.form['patente'].upper(),
                "descripcion": request.form['descripcion'],
                "km_actual": int(request.form['km_actual']),
                "service": {
                    "ultimo_fecha": request.form['service_fecha'],
                    "ultimo_km": int(request.form['service_km']),
                    "intervalo_km": int(request.form['service_intervalo'])
                },
                "vencimientos": {
                    "desinfeccion": request.form['venc_desinfeccion'],
                    "seguro": request.form['venc_seguro'],
                    "vtv": request.form['venc_vtv'],
                    "filtro_comanry": request.form['venc_comanry'] # NUEVO CAMPO
                },
                "historial": []
            }
            lista_camiones.append(nuevo_camion)
            guardar_datos(lista_camiones)
            return redirect(url_for('dashboard'))
        except Exception as e:
            return f"Error: {e}", 400
    return render_template('camion_nuevo.html')

@app.route('/camion/update_simple/<int:camion_id>', methods=['POST'])
@login_required
def actualizar_camion_simple(camion_id):
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion: return "No encontrado", 404

    accion = request.form['accion']
    nuevo_valor = request.form['nuevo_valor']

    # Lógica para actualizar KM o Vencimientos
    if accion == 'km':
        camion['km_actual'] = int(nuevo_valor)
    elif accion in camion.get('vencimientos', {}).keys() or accion == 'filtro_comanry':
        # Si la clave no existe (camiones viejos), la crea
        if 'vencimientos' not in camion: camion['vencimientos'] = {}
        camion['vencimientos'][accion] = nuevo_valor

    guardar_datos(lista_camiones)
    return redirect(url_for('detalle_camion', camion_id=camion_id))

@app.route('/camion/update_core/<int:camion_id>', methods=['POST'])
@login_required
def actualizar_camion_core(camion_id):
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion: return "Error", 404
    
    camion['patente'] = request.form['patente'].upper()
    camion['descripcion'] = request.form['descripcion']
    
    guardar_datos(lista_camiones)
    return redirect(url_for('detalle_camion', camion_id=camion_id))

@app.route('/camion/update_service/<int:camion_id>', methods=['POST'])
@login_required
def registrar_service_completo(camion_id):
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion: return "Error", 404

    try:
        fecha = request.form['service_fecha']
        km = int(request.form['service_km'])
        
        # Actualizamos KM actual solo si el nuevo es mayor
        if km > camion.get('km_actual', 0):
             camion['km_actual'] = km
        
        camion['service']['ultimo_fecha'] = fecha
        camion['service']['ultimo_km'] = km
        
        nuevo_historial = {
            "fecha": fecha, 
            "tipo": "Trabajo", 
            "detalle": f"Service completo realizado a los {km} km."
        }
        camion['historial'].append(nuevo_historial)

    except (ValueError, TypeError):
        return "Error: Datos inválidos.", 400
        
    guardar_datos(lista_camiones)
    return redirect(url_for('detalle_camion', camion_id=camion_id))

@app.route('/camion/update_historial/<int:camion_id>', methods=['POST'])
@login_required
def agregar_historial_general(camion_id):
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion: return "Error", 404
        
    nuevo_historial = {
        "fecha": request.form['historial_fecha'],
        "tipo": request.form['historial_tipo'],
        "detalle": request.form['historial_detalle']
    }
    camion['historial'].append(nuevo_historial)
    guardar_datos(lista_camiones)
    return redirect(url_for('detalle_camion', camion_id=camion_id))

@app.route('/camion/delete/<int:camion_id>', methods=['POST'])
@login_required
def eliminar_camion(camion_id):
    lista_camiones = cargar_datos()
    lista_actualizada = [c for c in lista_camiones if c['id'] != camion_id]
    guardar_datos(lista_actualizada)
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    # Escuchar en el puerto 80 para EasyPanel
    app.run(debug=True, host='0.0.0.0', port=80)