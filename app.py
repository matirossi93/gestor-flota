import datetime
import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash

# --- IMPORTAMOS EL PROGRAMADOR Y TU SCRIPT DE ALERTAS ---
from apscheduler.schedulers.background import BackgroundScheduler
import enviar_alertas

app = Flask(__name__)
app.secret_key = 'tu_llave_secreta_aqui'
# Importante: Ruta completa para que no falle al arrancar desde otros lados
DATA_FILE = "/opt/mi_flota_web/data/flota_data.json"

# ==========================================
#   FUNCIONES DE AYUDA
# ==========================================

def verificar_fecha(fecha_str):
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
        return "ERROR (Formato de fecha incorrecto)"

def verificar_service(camion):
    try:
        km_actual = camion["km_actual"]
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
        return "ERROR (Datos de service incompletos)"

def cargar_datos():
    if not os.path.exists(DATA_FILE):
        # Intentamos crear la carpeta si no existe
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        print(f"Aviso: No se encontró '{DATA_FILE}'. Creando lista vacía.")
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error al leer el archivo de datos: {e}")
        return []

def guardar_datos(datos):
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"¡Error crítico! No se pudieron guardar los datos: {e}")

def buscar_camion_por_id(lista_camiones, id_camion):
    for camion in lista_camiones:
        if camion["id"] == id_camion:
            return camion
    return None

def get_proximo_id(lista_camiones):
    if not lista_camiones:
        return 1
    max_id = max(camion.get('id', 0) for camion in lista_camiones)
    return max_id + 1

# ==========================================
#   CONFIGURACIÓN DEL RELOJ AUTOMÁTICO
# ==========================================

def iniciar_programador():
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(enviar_alertas.tarea_diaria, 'cron', hour=8, minute=0)
        scheduler.start()
        print("⏰ Programador de alertas iniciado (8:00 AM diariamente)")
    except Exception as e:
        print(f"Error al iniciar el programador: {e}")

iniciar_programador()

# ==========================================
#   RUTAS DE LA PÁGINA WEB
# ==========================================

@app.route('/')
def dashboard():
    lista_camiones = cargar_datos()
    
    for camion in lista_camiones:
        camion['estado_service'] = verificar_service(camion)
        camion['vencimientos_con_estado'] = []
        for tipo, fecha in camion.get("vencimientos", {}).items():
            estado_fecha = verificar_fecha(fecha)
            camion['vencimientos_con_estado'].append({
                "tipo": tipo.capitalize(),
                "fecha": fecha,
                "estado": estado_fecha
            })
    return render_template('index.html', lista_de_camiones=lista_camiones)

@app.route('/camion/<int:camion_id>')
def detalle_camion(camion_id):
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion:
        return "Error: Camión no encontrado", 404
        
    camion['estado_service'] = verificar_service(camion)
    camion['vencimientos_con_estado'] = []
    for tipo, fecha in camion.get("vencimientos", {}).items():
        estado_fecha = verificar_fecha(fecha)
        camion['vencimientos_con_estado'].append({
            "tipo": tipo.capitalize(),
            "fecha": fecha,
            "estado": estado_fecha
        })
    
    camion['historial_ordenado'] = sorted(camion.get("historial", []), key=lambda x: x['fecha'], reverse=True)

    return render_template('camion_detalle.html', camion=camion)

@app.route('/camion/nuevo', methods=['GET', 'POST'])
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
                    "vtv": request.form['venc_vtv']
                },
                "historial": []
            }
            lista_camiones.append(nuevo_camion)
            guardar_datos(lista_camiones)
            return redirect(url_for('dashboard'))
        except (KeyError, ValueError) as e:
            return f"Error: Faltan datos o son incorrectos. {e}", 400

    return render_template('camion_nuevo.html')

@app.route('/camion/update_simple/<int:camion_id>', methods=['POST'])
def actualizar_camion_simple(camion_id):
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion:
        return "Error: Camión no encontrado", 404

    accion = request.form['accion']
    nuevo_valor = request.form['nuevo_valor']

    try:
        if accion == 'km':
            camion['km_actual'] = int(nuevo_valor)
        elif accion == 'vtv':
            camion['vencimientos']['vtv'] = nuevo_valor
        elif accion == 'seguro':
            camion['vencimientos']['seguro'] = nuevo_valor
        elif accion == 'desinfeccion':
            camion['vencimientos']['desinfeccion'] = nuevo_valor
    except (ValueError, TypeError):
        return "Error: Valor inválido.", 400

    guardar_datos(lista_camiones)
    return redirect(url_for('detalle_camion', camion_id=camion_id))

@app.route('/camion/update_core/<int:camion_id>', methods=['POST'])
def actualizar_camion_core(camion_id):
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion:
        return "Error: Camión no encontrado", 404
        
    camion['patente'] = request.form['patente'].upper()
    camion['descripcion'] = request.form['descripcion']
    
    guardar_datos(lista_camiones)
    return redirect(url_for('detalle_camion', camion_id=camion_id))

@app.route('/camion/update_service/<int:camion_id>', methods=['POST'])
def registrar_service_completo(camion_id):
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion:
        return "Error: Camión no encontrado", 404

    try:
        fecha = request.form['service_fecha']
        km = int(request.form['service_km'])
        
        if km > camion['km_actual']:
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
        return "Error: Datos de service inválidos.", 400
        
    guardar_datos(lista_camiones)
    return redirect(url_for('detalle_camion', camion_id=camion_id))

@app.route('/camion/update_historial/<int:camion_id>', methods=['POST'])
def agregar_historial_general(camion_id):
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion:
        return "Error: Camión no encontrado", 404
        
    try:
        nuevo_historial = {
            "fecha": request.form['historial_fecha'],
            "tipo": request.form['historial_tipo'],
            "detalle": request.form['historial_detalle']
        }
        if not all(nuevo_historial.values()):
             return "Error: Faltan datos.", 400
             
        camion['historial'].append(nuevo_historial)
        guardar_datos(lista_camiones)
        
    except (KeyError):
        return "Error: Datos de historial inválidos.", 400
        
    return redirect(url_for('detalle_camion', camion_id=camion_id))

@app.route('/camion/delete/<int:camion_id>', methods=['POST'])
def eliminar_camion(camion_id):
    lista_camiones = cargar_datos()
    lista_actualizada = [c for c in lista_camiones if c['id'] != camion_id]
    
    if len(lista_actualizada) == len(lista_camiones):
        return "Error: Camión no encontrado", 404
        
    guardar_datos(lista_actualizada)
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=9000)