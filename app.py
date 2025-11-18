import datetime
import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash

# --- IMPORTAMOS EL PROGRAMADOR Y TU SCRIPT DE ALERTAS ---
from apscheduler.schedulers.background import BackgroundScheduler
import enviar_alertas  # Importamos el archivo enviar_alertas.py

app = Flask(__name__)
app.secret_key = 'tu_llave_secreta_aqui' 
DATA_FILE = "data/flota_data.json"

# ... (MANTÉN AQUÍ TODAS TUS FUNCIONES DE SIEMPRE: verificar_fecha, verificar_service, etc.) ...
# ... (Copia y pega tus funciones cargar_datos, guardar_datos, buscar_camion, etc.) ...
# ... (Copia y pega las funciones verificar_fecha y verificar_service que ya tenías) ...
# ... (Resumiendo: No borres la lógica que ya tenías, solo agrega lo de abajo) ...

# ==========================================
#   CONFIGURACIÓN DEL RELOJ AUTOMÁTICO
# ==========================================

def iniciar_programador():
    # Creamos el reloj
    scheduler = BackgroundScheduler()
    
    # Le decimos: "Ejecuta la funcion 'tarea_diaria' del archivo 'enviar_alertas'
    # todos los días a las 8:00 AM (hora del servidor)"
    scheduler.add_job(enviar_alertas.tarea_diaria, 'cron', hour=8, minute=0)
    
    # Arrancamos el reloj
    scheduler.start()
    print("⏰ Programador de alertas iniciado (8:00 AM diariamente)")

# Iniciamos el programador apenas arranca la app
iniciar_programador()

# ==========================================

# ... (MANTÉN AQUÍ TODAS TUS RUTAS: @app.route...) ...

if __name__ == '__main__':
    # IMPORTANTE: host='0.0.0.0' y port=80 para que funcione en Docker
    app.run(debug=True, host='0.0.0.0', port=80)