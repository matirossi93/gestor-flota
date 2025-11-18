import datetime
import json
import os
import smtplib # Librería para enviar emails (Simple Mail Transfer Protocol)
from email.mime.text import MIMEText # Librería para construir el email
from email.utils import formataddr
from email.header import Header

# --- Configuración del Archivo de Datos ---
# (Asegúrate que este script esté en la misma carpeta que el JSON)
DATA_FILE = "flota_data.json"

# --- Lógica "Reciclada" de app.py (El Cerebro) ---
# (Copiamos y pegamos nuestras funciones de verificación)

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

# --- Nueva Lógica: Generador de Reporte ---

def generar_reporte_alertas():
    """Lee los datos y genera un string con el resumen de alertas."""
    
    lista_camiones = cargar_datos()
    if lista_camiones is None:
        return None # No se pudieron cargar los datos
        
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
        
        # Si este camión tuvo alertas, las agregamos al reporte
        if alertas_camion:
            alertas_generales.append(f"\nCamión: {patente} ({camion.get('descripcion', 'N/A')})")
            alertas_generales.extend(alertas_camion)

    if not alertas_generales:
        print("Reporte generado: Todo en orden. No hay alertas.")
        return None # No hay nada que reportar
    
    # Si hubo alertas, construimos el cuerpo del email
    cuerpo_email = "¡Atención! Se encontraron los siguientes vencimientos:\n"
    cuerpo_email += "\n==================================================\n"
    cuerpo_email += "\n".join(alertas_generales)
    cuerpo_email += "\n\n=================================================="
    cuerpo_email += "\nEste es un reporte automático del Gestor de Flota."
    
    return cuerpo_email

# --- Nueva Lógica: Envío de Email ---

def enviar_email(asunto, cuerpo, destinatario, config):
    """Se conecta al servidor SMTP y envía el email."""
    
    try:
        # Creamos el objeto email
        msg = MIMEText(cuerpo, 'plain', 'utf-8')
        
        # Usamos formataddr y Header para evitar problemas con tildes
        msg['Subject'] = Header(asunto, 'utf-8')
        msg['From'] = formataddr((str(Header("Gestor de Flota", 'utf-8')), config['EMAIL_REMITENTE']))
        msg['To'] = destinatario

        # Conexión al servidor
        print(f"Conectando a {config['SMTP_SERVER']}:{config['SMTP_PORT']}...")
        server = smtplib.SMTP(config['SMTP_SERVER'], config['SMTP_PORT'])
        server.ehlo()
        server.starttls() # Iniciar conexión segura
        server.ehlo()
        
        # Login
        print(f"Iniciando sesión como {config['EMAIL_REMITENTE']}...")
        server.login(config['EMAIL_REMITENTE'], config['EMAIL_PASSWORD'])
        
        # Envío
        print(f"Enviando email a {destinatario}...")
        server.sendmail(config['EMAIL_REMITENTE'], [destinatario], msg.as_string())
        
        server.quit()
        print("¡Email enviado con éxito!")
        
    except smtplib.SMTPAuthenticationError:
        print("\n--- ¡ERROR DE AUTENTICACIÓN! ---")
        print("Verifica tu email y contraseña (¿Usaste una 'Contraseña de Aplicación'?).")
    except Exception as e:
        print(f"\n--- ¡ERROR AL ENVIAR EL EMAIL! ---")
        print(f"Error: {e}")

# --- Bloque Principal de Ejecución ---

if __name__ == "__main__":
    
    # --- 1. CONFIGURACIÓN (¡DEBES RELLENAR ESTO!) ---
    configuracion = {
        # Configuración para GMAIL
        "SMTP_SERVER": "smtp.gmail.com",
        "SMTP_PORT": 587,
        
        # Tu email (el que envía)
        "EMAIL_REMITENTE": "datos@semilleroelmanantial.com",
        
        # La "Contraseña de Aplicación" de 16 letras que generaste
        "EMAIL_PASSWORD": "juaj iqmi saey zalp"
    }
    
    # El email que recibe las alertas (puede ser el mismo o uno distinto)
    EMAIL_DESTINATARIO = "datos@semilleroelmanantial.com" 
    
    print("Iniciando script de alertas...")
    
    # --- 2. Generar Reporte ---
    asunto_email = f"Alertas de Flota - {datetime.date.today().strftime('%d/%m/%Y')}"
    cuerpo_del_reporte = generar_reporte_alertas()
    
    # --- 3. Enviar Email (Solo si hay algo que reportar) ---
    if cuerpo_del_reporte:
        enviar_email(
            asunto_email, 
            cuerpo_del_reporte, 
            EMAIL_DESTINATARIO,
            configuracion
        )
    else:
        print("Fin del script. No fue necesario enviar email.")