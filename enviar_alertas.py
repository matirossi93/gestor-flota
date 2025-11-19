import datetime
import json
import os
import smtplib 
from email.mime.text import MIMEText 
from email.mime.multipart import MIMEMultipart # <--- NUEVO: Para adjuntos
from email.mime.base import MIMEBase         # <--- NUEVO: Para adjuntos
from email import encoders                   # <--- NUEVO: Para adjuntos
from email.utils import formataddr
from email.header import Header

# Ruta relativa para Docker
DATA_FILE = "data/flota_data.json"

# --- CONFIGURACIÓN (Tus datos) ---
CONFIG = {
    "SMTP_SERVER": "smtp.gmail.com",
    "SMTP_PORT": 587,
    "EMAIL_REMITENTE": "datos@semilleroelmanantial.com",
    "EMAIL_PASSWORD": "juaj iqmi saey zalp" 
}

EMAILS_DESTINO = [
    "datos@semilleroelmanantial.com",
    "gerencia@semilleroelmanantial.com.ar"
]

# --- Funciones de Ayuda (Sin cambios) ---
def verificar_fecha(fecha_str):
    if not fecha_str: return "SIN DATOS"
    try:
        fecha_vencimiento = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
        hoy = datetime.date.today()
        diferencia = (fecha_vencimiento - hoy).days
        if diferencia < 0: return f"VENCIDO (hace {-diferencia} días)"
        elif diferencia <= 30: return f"PRÓXIMO (vence en {diferencia} días)"
        else: return "OK"
    except ValueError: return "ERROR"

def verificar_service(camion):
    try:
        km_actual = camion.get("km_actual", 0)
        km_ultimo = camion["service"]["ultimo_km"]
        km_intervalo = camion["service"]["intervalo_km"]
        km_proximo_service = km_ultimo + km_intervalo
        diferencia_km = km_proximo_service - km_actual
        if diferencia_km < 0: return f"VENCIDO (hace {-diferencia_km} km)"
        elif diferencia_km <= 2000: return f"PRÓXIMO (faltan {diferencia_km} km)"
        else: return "OK"
    except (KeyError, TypeError): return "ERROR"

def cargar_datos():
    if not os.path.exists(DATA_FILE): return None
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return None

def generar_reporte_alertas():
    lista_camiones = cargar_datos()
    if not lista_camiones: return None
    alertas_generales = []
    for camion in lista_camiones:
        alertas_camion = []
        patente = camion.get('patente', 'ID ' + str(camion.get('id', '??')))
        estado_service = verificar_service(camion)
        if "VENCIDO" in estado_service or "PRÓXIMO" in estado_service:
            alertas_camion.append(f"  - Service: {estado_service}")
        for tipo, fecha in camion.get("vencimientos", {}).items():
            estado_fecha = verificar_fecha(fecha)
            if "VENCIDO" in estado_fecha or "PRÓXIMO" in estado_fecha:
                alertas_camion.append(f"  - {tipo.replace('_', ' ').capitalize()}: {estado_fecha}")
        if alertas_camion:
            alertas_generales.append(f"\nCamión: {patente} ({camion.get('descripcion', 'N/A')})")
            alertas_generales.extend(alertas_camion)
    if not alertas_generales: return None
    return "¡Atención! Vencimientos detectados:\n================================\n" + "\n".join(alertas_generales)

# --- FUNCIÓN 1: Enviar Alerta Simple (Texto) ---
def enviar_email_simple(asunto, cuerpo):
    try:
        msg = MIMEText(cuerpo, 'plain', 'utf-8')
        msg['Subject'] = Header(asunto, 'utf-8')
        msg['From'] = formataddr((str(Header("Gestor Flota", 'utf-8')), CONFIG['EMAIL_REMITENTE']))
        msg['To'] = ", ".join(EMAILS_DESTINO)

        server = smtplib.SMTP(CONFIG['SMTP_SERVER'], CONFIG['SMTP_PORT'])
        server.starttls()
        server.login(CONFIG['EMAIL_REMITENTE'], CONFIG['EMAIL_PASSWORD'])
        server.sendmail(CONFIG['EMAIL_REMITENTE'], EMAILS_DESTINO, msg.as_string())
        server.quit()
        print("¡Alerta enviada!")
    except Exception as e:
        print(f"Error enviando alerta: {e}")

# --- FUNCIÓN 2: Enviar Copia de Seguridad (Con Adjunto) ---
def enviar_copia_seguridad():
    print("--- 💾 Iniciando Copia de Seguridad Automática ---")
    try:
        # Crear email con adjuntos (Multipart)
        msg = MIMEMultipart()
        msg['Subject'] = Header(f"Backup Flota - {datetime.date.today()}", 'utf-8')
        msg['From'] = formataddr((str(Header("Gestor Flota Backup", 'utf-8')), CONFIG['EMAIL_REMITENTE']))
        msg['To'] = ", ".join(EMAILS_DESTINO)

        # Cuerpo del mensaje
        msg.attach(MIMEText("Se adjunta la copia de seguridad semanal de la base de datos.", 'plain'))

        # Adjuntar el archivo JSON
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= flota_data_{datetime.date.today()}.json",
            )
            msg.attach(part)
        else:
            print("Error: No se encontró el archivo de datos para respaldar.")
            return

        # Enviar
        server = smtplib.SMTP(CONFIG['SMTP_SERVER'], CONFIG['SMTP_PORT'])
        server.starttls()
        server.login(CONFIG['EMAIL_REMITENTE'], CONFIG['EMAIL_PASSWORD'])
        server.sendmail(CONFIG['EMAIL_REMITENTE'], EMAILS_DESTINO, msg.as_string())
        server.quit()
        print("¡Copia de seguridad enviada con éxito!")

    except Exception as e:
        print(f"Error enviando backup: {e}")

# --- Tarea Diaria de Alertas ---
def tarea_diaria():
    print("--- ⏰ Chequeando alertas... ---")
    asunto = f"Alertas Flota - {datetime.date.today().strftime('%d/%m/%Y')}"
    reporte = generar_reporte_alertas()
    if reporte:
        enviar_email_simple(asunto, reporte)
    else:
        print("Sin alertas hoy.")

if __name__ == "__main__":
    # Prueba manual: Ejecuta ambas cosas si corres el script directo
    tarea_diaria()
    enviar_copia_seguridad()