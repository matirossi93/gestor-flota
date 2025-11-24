import datetime
import json
import os
import smtplib 
from email.mime.text import MIMEText 
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from email.header import Header

# --- RUTAS DE ARCHIVOS ---
DATA_FILE = "data/flota_data.json"
CONFIG_FILE = "data/config.json"

# --- CREDENCIALES SMTP (Estas quedan fijas porque son del servidor de envío) ---
# Nota: Los destinatarios ahora se leen desde config.json
SMTP_CONFIG = {
    "SERVER": "smtp.gmail.com",
    "PORT": 587,
    "EMAIL": "datos@semilleroelmanantial.com",
    "PASSWORD": "juaj iqmi saey zalp" 
}

# --- FUNCIONES DE CARGA ---

def cargar_datos():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def cargar_configuracion():
    """Lee la configuración guardada desde el Panel Web"""
    config_default = {"diasAviso": 30, "emailAlertas": "datos@semilleroelmanantial.com"}
    
    if not os.path.exists(CONFIG_FILE):
        return config_default
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            datos = json.load(f)
            # Asegurar que existan las claves por si el archivo está incompleto
            if "diasAviso" not in datos: datos["diasAviso"] = 30
            if "emailAlertas" not in datos: datos["emailAlertas"] = ""
            return datos
    except:
        return config_default

def obtener_destinatarios(config):
    """Convierte el string 'mail1, mail2' en una lista real"""
    raw_emails = config.get("emailAlertas", "")
    # Separa por comas y quita espacios en blanco
    lista = [e.strip() for e in raw_emails.split(',') if e.strip()]
    
    # Si la lista está vacía, usamos un default de seguridad
    if not lista:
        return ["datos@semilleroelmanantial.com"]
    return lista

# --- LÓGICA DE NEGOCIO ---

def verificar_fecha(fecha_str, dias_aviso):
    if not fecha_str: return "SIN DATOS"
    try:
        fecha_vencimiento = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
        hoy = datetime.date.today()
        diferencia = (fecha_vencimiento - hoy).days
        
        if diferencia < 0: 
            return f"VENCIDO (hace {-diferencia} días)"
        elif diferencia <= dias_aviso: 
            return f"PRÓXIMO (vence en {diferencia} días)"
        else: 
            return "OK"
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

def generar_reporte_alertas(dias_aviso):
    lista_camiones = cargar_datos()
    if not lista_camiones: return None
    
    alertas_generales = []
    
    for camion in lista_camiones:
        alertas_camion = []
        patente = camion.get('patente', 'ID ' + str(camion.get('id', '??')))
        
        # 1. Verificar Service
        estado_service = verificar_service(camion)
        if "VENCIDO" in estado_service or "PRÓXIMO" in estado_service:
            alertas_camion.append(f"  - Service: {estado_service}")
            
        # 2. Verificar Vencimientos (Usando días dinámicos)
        # Aseguramos que 'vencimientos' exista como objeto
        vencimientos = camion.get("vencimientos", {})
        if isinstance(vencimientos, dict):
            for tipo, fecha in vencimientos.items():
                # Ignoramos campos que no son fechas o el filtro comanry si no es relevante
                if not fecha or tipo == 'filtro_comanry': continue 
                
                estado_fecha = verificar_fecha(fecha, dias_aviso)
                if "VENCIDO" in estado_fecha or "PRÓXIMO" in estado_fecha:
                    alertas_camion.append(f"  - {tipo.replace('_', ' ').capitalize()}: {estado_fecha}")
        
        if alertas_camion:
            alertas_generales.append(f"\nCamión: {patente} ({camion.get('descripcion', 'N/A')})")
            alertas_generales.extend(alertas_camion)
            
    if not alertas_generales: return None
    
    header = f"Reporte de Alertas (Configuración: aviso {dias_aviso} días antes)\n"
    return header + "================================\n" + "\n".join(alertas_generales)

# --- ENVÍO DE EMAILS ---

def enviar_email_simple(asunto, cuerpo, destinatarios):
    if not destinatarios:
        print("No hay destinatarios configurados.")
        return

    try:
        msg = MIMEText(cuerpo, 'plain', 'utf-8')
        msg['Subject'] = Header(asunto, 'utf-8')
        msg['From'] = formataddr((str(Header("Gestor Flota", 'utf-8')), SMTP_CONFIG['EMAIL']))
        msg['To'] = ", ".join(destinatarios)

        server = smtplib.SMTP(SMTP_CONFIG['SERVER'], SMTP_CONFIG['PORT'])
        server.starttls()
        server.login(SMTP_CONFIG['EMAIL'], SMTP_CONFIG['PASSWORD'])
        server.sendmail(SMTP_CONFIG['EMAIL'], destinatarios, msg.as_string())
        server.quit()
        print(f"¡Alerta enviada a {len(destinatarios)} destinatarios!")
    except Exception as e:
        print(f"Error enviando alerta: {e}")

def enviar_copia_seguridad():
    print("--- 💾 Iniciando Copia de Seguridad Automática ---")
    
    # Cargar configuración fresca al momento de enviar
    config = cargar_configuracion()
    destinatarios = obtener_destinatarios(config)
    
    try:
        msg = MIMEMultipart()
        msg['Subject'] = Header(f"Backup Flota - {datetime.date.today()}", 'utf-8')
        msg['From'] = formataddr((str(Header("Gestor Flota Backup", 'utf-8')), SMTP_CONFIG['EMAIL']))
        msg['To'] = ", ".join(destinatarios)

        msg.attach(MIMEText("Se adjunta la copia de seguridad semanal de la base de datos.", 'plain'))

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
            print("Error: No se encontró el archivo de datos.")
            return

        server = smtplib.SMTP(SMTP_CONFIG['SERVER'], SMTP_CONFIG['PORT'])
        server.starttls()
        server.login(SMTP_CONFIG['EMAIL'], SMTP_CONFIG['PASSWORD'])
        server.sendmail(SMTP_CONFIG['EMAIL'], destinatarios, msg.as_string())
        server.quit()
        print("¡Copia de seguridad enviada con éxito!")

    except Exception as e:
        print(f"Error enviando backup: {e}")

# --- TAREA PRINCIPAL ---

def tarea_diaria():
    print("--- ⏰ Chequeando alertas (Configuración Dinámica)... ---")
    
    # 1. Leer configuración actual
    config = cargar_configuracion()
    dias_aviso = int(config.get("diasAviso", 30))
    destinatarios = obtener_destinatarios(config)
    
    # 2. Generar reporte usando los días configurados
    asunto = f"Alertas Flota - {datetime.date.today().strftime('%d/%m/%Y')}"
    reporte = generar_reporte_alertas(dias_aviso)
    
    # 3. Enviar si hay novedades
    if reporte:
        enviar_email_simple(asunto, reporte, destinatarios)
    else:
        print("Sin alertas hoy.")

if __name__ == "__main__":
    # Prueba manual
    tarea_diaria()
    # enviar_copia_seguridad() # Descomentar para probar backup
