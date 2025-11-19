import datetime
import json
import os
import smtplib 
from email.mime.text import MIMEText 
from email.utils import formataddr
from email.header import Header

# --- Configuración del Archivo de Datos ---
# Usamos ruta relativa para Docker
DATA_FILE = "data/flota_data.json"

# --- Funciones de Ayuda (Sin cambios) ---

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
                # Reemplazamos guiones bajos por espacios para que se lea mejor
                nombre_tipo = tipo.replace('_', ' ').capitalize()
                alertas_camion.append(f"  - {nombre_tipo}: {estado_fecha}")
        
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

# --- Envío de Email (MODIFICADO PARA LISTA) ---

def enviar_email(asunto, cuerpo, lista_destinatarios, config):
    """Envía el email a una lista de personas."""
    try:
        msg = MIMEText(cuerpo, 'plain', 'utf-8')
        msg['Subject'] = Header(asunto, 'utf-8')
        msg['From'] = formataddr((str(Header("Gestor de Flota", 'utf-8')), config['EMAIL_REMITENTE']))
        
        # Unimos los emails con comas para que se vea bonito en el encabezado "Para:"
        msg['To'] = ", ".join(lista_destinatarios)

        print(f"Conectando a {config['SMTP_SERVER']}...")
        server = smtplib.SMTP(config['SMTP_SERVER'], config['SMTP_PORT'])
        server.ehlo()
        server.starttls() 
        server.ehlo()
        
        print(f"Iniciando sesión como {config['EMAIL_REMITENTE']}...")
        server.login(config['EMAIL_REMITENTE'], config['EMAIL_PASSWORD'])
        
        print(f"Enviando email a: {lista_destinatarios}...")
        # Aquí pasamos la LISTA real al servidor para que entregue a todos
        server.sendmail(config['EMAIL_REMITENTE'], lista_destinatarios, msg.as_string())
        
        server.quit()
        print("¡Emails enviados con éxito!")
        
    except Exception as e:
        print(f"\n--- ¡ERROR AL ENVIAR EL EMAIL! ---")
        print(f"Error: {e}")

# --- FUNCIÓN PRINCIPAL AUTOMÁTICA ---

def tarea_diaria():
    print("--- ⏰ Iniciando chequeo de alertas programado ---")
    
    # TUS DATOS DE CONFIGURACIÓN
    configuracion = {
        "SMTP_SERVER": "smtp.gmail.com",
        "SMTP_PORT": 587,
        "EMAIL_REMITENTE": "datos@semilleroelmanantial.com",
        # Usa tu contraseña de aplicación de 16 letras aquí:
        "EMAIL_PASSWORD": "juaj iqmi saey zalp" 
    }
    
    # --- AQUÍ AGREGAS LOS CORREOS QUE QUIERAS ---
    EMAILS_DESTINO = [
        "datos@semilleroelmanantial.com",
        "gerencia@semilleroelmanantial.com.ar"
    ]
    
    # Generar y Enviar
    asunto_email = f"Alertas de Flota - {datetime.date.today().strftime('%d/%m/%Y')}"
    cuerpo_del_reporte = generar_reporte_alertas()
    
    if cuerpo_del_reporte:
        enviar_email(
            asunto_email, 
            cuerpo_del_reporte, 
            EMAILS_DESTINO,
            configuracion
        )
    else:
        print("Todo en orden. No hay alertas para enviar hoy.")

# --- Bloque Principal (Para probarlo manualmente en tu PC) ---
if __name__ == "__main__":
    tarea_diaria()