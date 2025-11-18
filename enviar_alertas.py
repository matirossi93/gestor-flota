import datetime
import json
import os
import smtplib 
from email.mime.text import MIMEText 
from email.utils import formataddr
from email.header import Header

# --- Configuración del Archivo de Datos ---
DATA_FILE = "/datos_flota/flota.json"

# --- Funciones de Ayuda (Sin cambios) ---

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
        print(f"Error: No se encontró '{DATA_FILE}'.")
        return None
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error al leer datos: {e}")
        return None

# --- Generador de Reporte ---

def generar_reporte_alertas():
    lista_camiones = cargar_datos()
    if lista_camiones is None:
        return None 
        
    alertas_generales = []
    
    for camion in lista_camiones:
        alertas_camion = []
        patente = camion.get('patente', 'ID ' + str(camion.get('id', '??')))
        
        # 1. Chequear Service
        estado_service = verificar_service(camion)
        if "VENCIDO" in estado_service or "PRÓXIMO" in estado_service:
            alertas_camion.append(f"  - Service: {estado_service}")

        # 2. Chequear Vencimientos por fecha
        for tipo, fecha in camion.get("vencimientos", {}).items():
            estado_fecha = verificar_fecha(fecha)
            if "VENCIDO" in estado_fecha or "PRÓXIMO" in estado_fecha:
                alertas_camion.append(f"  - {tipo.capitalize()}: {estado_fecha}")
        
        if alertas_camion:
            alertas_generales.append(f"\nCamión: {patente} ({camion.get('descripcion', 'N/A')})")
            alertas_generales.extend(alertas_camion)

    if not alertas_generales:
        return None 
    
    cuerpo_email = "¡Atención! Se encontraron los siguientes vencimientos:\n"
    cuerpo_email += "\n==================================================\n"
    cuerpo_email += "\n".join(alertas_generales)
    cuerpo_email += "\n\n=================================================="
    cuerpo_email += "\nEste es un reporte automático del Gestor de Flota."
    
    return cuerpo_email

# --- Envío de Email ---

def enviar_email(asunto, cuerpo, destinatario, config):
    try:
        msg = MIMEText(cuerpo, 'plain', 'utf-8')
        msg['Subject'] = Header(asunto, 'utf-8')
        msg['From'] = formataddr((str(Header("Gestor de Flota", 'utf-8')), config['EMAIL_REMITENTE']))
        msg['To'] = destinatario

        print(f"Conectando a {config['SMTP_SERVER']}:{config['SMTP_PORT']}...")
        server = smtplib.SMTP(config['SMTP_SERVER'], config['SMTP_PORT'])
        server.ehlo()
        server.starttls() 
        server.ehlo()
        
        print(f"Iniciando sesión como {config['EMAIL_REMITENTE']}...")
        server.login(config['EMAIL_REMITENTE'], config['EMAIL_PASSWORD'])
        
        print(f"Enviando email a {destinatario}...")
        server.sendmail(config['EMAIL_REMITENTE'], [destinatario], msg.as_string())
        
        server.quit()
        print("¡Email enviado con éxito!")
        
    except Exception as e:
        print(f"\n--- ¡ERROR AL ENVIAR EL EMAIL! ---")
        print(f"Error: {e}")

# --- NUEVA FUNCIÓN: Esta es la que llamará el sistema automático ---

def tarea_diaria():
    print("--- ⏰ Iniciando chequeo de alertas programado ---")
    
    # TUS DATOS DE CONFIGURACIÓN (Ya incluidos)
    configuracion = {
        "SMTP_SERVER": "smtp.gmail.com",
        "SMTP_PORT": 587,
        "EMAIL_REMITENTE": "datos@semilleroelmanantial.com",
        "EMAIL_PASSWORD": "juaj iqmi saey zalp"
    }
    
    EMAIL_DESTINATARIO = "datos@semilleroelmanantial.com" 
    
    # Generar y Enviar
    asunto_email = f"Alertas de Flota - {datetime.date.today().strftime('%d/%m/%Y')}"
    cuerpo_del_reporte = generar_reporte_alertas()
    
    if cuerpo_del_reporte:
        enviar_email(
            asunto_email, 
            cuerpo_del_reporte, 
            EMAIL_DESTINATARIO,
            configuracion
        )
    else:
        print("Todo en orden. No hay alertas para enviar hoy.")

# --- Bloque Principal (Para probarlo manualmente) ---
if __name__ == "__main__":
    tarea_diaria()