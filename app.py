import datetime
import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
# Necesitamos una 'secret_key' para que funcionen los mensajes flash
app.secret_key = 'tu_llave_secreta_aqui' 
DATA_FILE = "flota_data.json"

# --- Lógica de Verificación (Sin Cambios) ---
# (verificar_fecha, verificar_service, cargar_datos, guardar_datos)

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
        print(f"ERROR FATAL: No se encontró '{DATA_FILE}'.")
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error al leer el archivo de datos: {e}")
        return []

def guardar_datos(datos):
    try:
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
    """Encuentra el ID más alto y le suma 1 para el nuevo camión."""
    if not lista_camiones:
        return 1
    max_id = max(camion.get('id', 0) for camion in lista_camiones)
    return max_id + 1

# --- Rutas de Flask (Sección Principal) ---

@app.route('/')
def dashboard():
    """Dashboard principal. Carga y procesa todos los camiones."""
    lista_camiones = cargar_datos()
    
    for camion in lista_camiones:
        camion['estado_service'] = verificar_service(camion)
        # (Opcional: procesar vencimientos. Lo quitamos para que cargue más rápido)
        # (El HTML ahora puede hacer esta lógica si es necesario)

    return render_template('index.html', lista_de_camiones=lista_camiones)

@app.route('/camion/<int:camion_id>')
def detalle_camion(camion_id):
    """Página de detalles para un camión (Formularios de edición)."""
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion:
        return "Error: Camión no encontrado", 404
        
    # Procesamos los datos de vencimiento aquí, solo para este camión
    camion['estado_service'] = verificar_service(camion)
    camion['vencimientos_con_estado'] = []
    for tipo, fecha in camion["vencimientos"].items():
        estado_fecha = verificar_fecha(fecha)
        camion['vencimientos_con_estado'].append({
            "tipo": tipo.capitalize(),
            "fecha": fecha,
            "estado": estado_fecha
        })
    
    # Ordenamos el historial por fecha (el más nuevo primero)
    camion['historial_ordenado'] = sorted(camion["historial"], key=lambda x: x['fecha'], reverse=True)

    return render_template('camion_detalle.html', camion=camion)

# --- Rutas de Flask (Sección de Lógica de "Agregar") ---

@app.route('/camion/nuevo', methods=['GET', 'POST'])
def agregar_camion():
    """Muestra el formulario para agregar un camión (GET)
    o procesa ese formulario (POST)."""
    
    if request.method == 'POST':
        lista_camiones = cargar_datos()
        
        try:
            # Creamos el nuevo objeto camión desde el formulario
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
                "historial": [] # Empieza vacío
            }
        except (KeyError, ValueError):
            # flash('Error: Faltan datos o son incorrectos.', 'error')
            return "Error: Faltan datos o son incorrectos.", 400

        lista_camiones.append(nuevo_camion)
        guardar_datos(lista_camiones)
        
        # Redirigimos al dashboard para ver el nuevo camión
        return redirect(url_for('dashboard'))

    # Si es GET, solo mostramos la página del formulario
    return render_template('camion_nuevo.html')


# --- Rutas de Flask (Sección de Lógica de "Actualizar") ---

@app.route('/camion/update_simple/<int:camion_id>', methods=['POST'])
def actualizar_camion_simple(camion_id):
    """Procesa los formularios SIMPLES (KM, VTV, Seguro, etc.)"""
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
    """Actualiza la Patente y Descripción."""
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
    """Registra un service completo: actualiza service, km y añade al historial."""
    lista_camiones = cargar_datos()
    camion = buscar_camion_por_id(lista_camiones, camion_id)
    if not camion:
        return "Error: Camión no encontrado", 404

    try:
        fecha = request.form['service_fecha']
        km = int(request.form['service_km'])
        
        # 1. Actualizar el KM actual del camión
        if km > camion['km_actual']:
             camion['km_actual'] = km
        
        # 2. Actualizar los datos del service
        camion['service']['ultimo_fecha'] = fecha
        camion['service']['ultimo_km'] = km
        
        # 3. Añadir al historial
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
    """Agrega un repuesto o trabajo al historial."""
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
        
        # Validar que los campos no estén vacíos
        if not all(nuevo_historial.values()):
             return "Error: Faltan datos en el formulario de historial.", 400
             
        camion['historial'].append(nuevo_historial)
        guardar_datos(lista_camiones)
        
    except (KeyError):
        return "Error: Datos de historial inválidos.", 400
        
    return redirect(url_for('detalle_camion', camion_id=camion_id))

# --- Rutas de Flask (Sección de Lógica de "Eliminar") ---

@app.route('/camion/delete/<int:camion_id>', methods=['POST'])
def eliminar_camion(camion_id):
    """Elimina un camión de la base de datos."""
    lista_camiones = cargar_datos()
    
    # Creamos una NUEVA lista excluyendo el camión con ese ID
    lista_actualizada = [c for c in lista_camiones if c['id'] != camion_id]
    
    if len(lista_actualizada) == len(lista_camiones):
        # No se encontró el camión
        return "Error: Camión no encontrado", 404
        
    guardar_datos(lista_actualizada)
    
    # Redirigimos al dashboard
    return redirect(url_for('dashboard'))

# --- Ejecutar el servidor ---
if __name__ == '__main__':
    app.run(debug=True)