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

# --- RUTAS ---
DATA_FILE = "data/flota_data.json"
CONFIG_FILE = "data/config.json"

# --- SMTP ---
SMTP_CONFIG = {
    "SERVER": "smtp.gmail.com",
    "PORT": 587,
    "EMAIL": "datos@semilleroelmanantial.com",
    "PASSWORD": "juaj iqmi saey zalp" 
}

# --- CARGA ---
def cargar_datos():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def cargar_configuracion():
    config_default = {"diasAviso": 30, "emailAlertas": "datos@semilleroelmanantial.com"}
    if not os.path.exists(CONFIG_FILE): return config_default
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            datos = json.load(f)
            return datos
    except: return config_default

def obtener_destinatarios(config):
    raw = config.get("emailAlertas", "")
    lista = [e.strip() for e in raw.split(',') if e.strip()]
    return lista if lista else ["datos@semilleroelmanantial.com"]

# --- LÓGICA INTELIGENTE ---

def es_momento_de_avisar(fecha_str, dias_config):
    """Retorna True solo si es un día clave para molestar al usuario"""
    if not fecha_str: return False
    try:
        venc = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
        hoy = datetime.date.today()
        dias_restantes = (venc - hoy).days

        # CASO 1: Ya venció (Avisar SIEMPRE)
        if dias_restantes < 0:
            return True, f"VENCIDO (hace {abs(dias_restantes)} días)"
        
        # CASO 2: Zona Roja (Faltan 3 días o menos -> Avisar SIEMPRE)
        if dias_restantes <= 3:
            return True, f"URGENTE (vence en {dias_restantes} días)"

        # CASO 3: Hitos de Recordatorio (Solo avisar en días específicos)
        # Avisamos el día que empieza el periodo (ej: 30), a la mitad (15) y una semana antes (7)
        hitos = [dias_config, 15, 7] 
        if dias_restantes in hitos:
            return True, f"Recordatorio (vence en {dias_restantes} días)"
            
        return False, ""
    except: return False, ""

def verificar_service(camion):
    try:
        actual = camion.get("km_actual", 0)
        prox = camion["service"]["ultimo_km"] + camion["service"]["intervalo_km"]
        diff = prox - actual
        
        if diff < 0: return True, f"VENCIDO (hace {abs(diff)} km)"
        if diff <= 1000: return True, f"URGENTE (falta {diff} km)" # Solo avisa si falta poco
        return False, ""
    except: return False, ""

def generar_reporte_alertas(dias_aviso):
    lista = cargar_datos()
    if not lista: return None
    alertas_gral = []
    
    for c in lista:
        alertas_c = []
        patente = c.get('patente', 'Unidad')
        
        # Service
        avisar_srv, msg_srv = verificar_service(c)
        if avisar_srv: alertas_c.append(f"  - Service: {msg_srv}")
            
        # Vencimientos
        vencs = c.get("vencimientos", {})
        if isinstance(vencs, dict):
            for tipo, fecha in vencs.items():
                if not fecha or tipo == 'filtro_comanry': continue 
                avisar, msg = es_momento_de_avisar(fecha, dias_aviso)
                if avisar:
                    alertas_c.append(f"  - {tipo.replace('_',' ').capitalize()}: {msg}")
        
        if alertas_c:
            alertas_gral.append(f"\nUnidad: {patente} ({c.get('descripcion','')})")
            alertas_gral.extend(alertas_c)
            
    if not alertas_gral: return None
    return "Informe de Alertas (Semillero):\n==========================\n" + "\n".join(alertas_gral)

# --- ENVÍO ---
def enviar_email_simple(asunto, cuerpo, dest):
    if not dest: return
    try:
        msg = MIMEText(cuerpo, 'plain', 'utf-8')
        msg['Subject'] = Header(asunto, 'utf-8')
        msg['From'] = formataddr((str(Header("Gestor Flota", 'utf-8')), SMTP_CONFIG['EMAIL']))
        msg['To'] = ", ".join(dest)
        server = smtplib.SMTP(SMTP_CONFIG['SERVER'], SMTP_CONFIG['PORT'])
        server.starttls()
        server.login(SMTP_CONFIG['EMAIL'], SMTP_CONFIG['PASSWORD'])
        server.sendmail(SMTP_CONFIG['EMAIL'], dest, msg.as_string())
        server.quit()
        print("Alertas enviadas.")
    except Exception as e: print(f"Error mail: {e}")

def enviar_copia_seguridad():
    print("--- Backup ---")
    config = cargar_configuracion()
    dest = obtener_destinatarios(config)
    try:
        msg = MIMEMultipart()
        msg['Subject'] = Header(f"Backup Flota - {datetime.date.today()}", 'utf-8')
        msg['From'] = formataddr((str(Header("Gestor Backup", 'utf-8')), SMTP_CONFIG['EMAIL']))
        msg['To'] = ", ".join(dest)
        msg.attach(MIMEText("Copia de seguridad adjunta.", 'plain'))
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename=backup_{datetime.date.today()}.json")
            msg.attach(part)
            server = smtplib.SMTP(SMTP_CONFIG['SERVER'], SMTP_CONFIG['PORT'])
            server.starttls()
            server.login(SMTP_CONFIG['EMAIL'], SMTP_CONFIG['PASSWORD'])
            server.sendmail(SMTP_CONFIG['EMAIL'], dest, msg.as_string())
            server.quit()
            print("Backup enviado.")
    except Exception as e: print(f"Error backup: {e}")

def tarea_diaria():
    print("--- Chequeando Alertas Inteligentes ---")
    config = cargar_configuracion()
    dias = int(config.get("diasAviso", 30))
    dest = obtener_destinatarios(config)
    reporte = generar_reporte_alertas(dias)
    if reporte: enviar_email_simple(f"Aviso Flota - {datetime.date.today().strftime('%d/%m')}", reporte, dest)
    else: print("Hoy no hay alertas importantes.")

if __name__ == "__main__":
    tarea_diaria()
