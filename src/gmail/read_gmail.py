"""
================================================================================
read_gmail.py
================================================================================
PROPOSITO:
Este script se conecta a la API de Gmail y obtiene correos electronicos segun el
modo de ejecucion elegido:
  - (--last): obtiene el ultimo correo recibido.
  - (--id <msg_id>): obtiene un correo especifico por su ID (util para n8n).

Sirve como modulo de ENTRADA del sistema de automatizacion del despacho. 
Descarga el contenido estructurado del correo y lo guarda en formato JSON 
en la carpeta `data/incoming/`, para que otros modulos (por ejemplo 
`process_email.py`) puedan procesarlo, aplicar OCR, clasificarlo, etc.

USOS TIPICOS:
1. Manual:  python read_gmail.py --last
2. Con n8n: python read_gmail.py --id={{gmail.id}}

FUNCIONALIDADES:
- Conexion segura con Gmail API (modo solo lectura).
- Extraccion de metadatos: remitente, asunto, fecha, labels.
- Lectura del cuerpo del correo (texto plano).
- Deteccion y listado de adjuntos (sin descargarlos todavia).
- Guardado en formato JSON dentro de `data/incoming/`.

ESTRUCTURA MODULAR:
- load_credentials(): carga las credenciales OAuth.
- get_gmail_service(): inicializa el cliente Gmail API.
- fetch_last_email(): obtiene el correo mas reciente.
- fetch_email_by_id(): obtiene un correo especifico por ID.
- parse_email(): extrae y organiza la informacion del correo.
- save_email_json(): guarda el resultado en data/incoming/.
- main(): punto de entrada, gestiona los argumentos y flujo principal.

NOTAS:
- No modifica el estado del buzon (no marca como leido ni elimina nada).
- Preparado para integrarse en flujos de automatizacion con n8n.
- Compatible con los archivos `config/credentials/gmail_credentials.json` 
  y `config/credentials/token.json`.

Version: 1.2 — Octubre 2025
================================================================================
"""

import os
import json
import base64
import argparse
import pathlib
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Configuracion general
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
CRED_DIR = BASE_DIR / "config" / "credentials"
DATA_DIR = BASE_DIR / "data" / "incoming"
TOKEN_PATH = CRED_DIR / "token.json"
CREDENTIALS_PATH = CRED_DIR / "gmail_credentials.json"


# ------------------------------------------------------------------------------
# Funcion: Cargar credenciales
# ------------------------------------------------------------------------------
def load_credentials():
    """
    Carga las credenciales OAuth2 desde el archivo token.json generado
    previamente al autorizar la aplicacion en Gmail.
    """
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(f"No se encontro {TOKEN_PATH}. Ejecuta la autorizacion primero.")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    return creds


# ------------------------------------------------------------------------------
# Funcion: Inicializar el servicio de Gmail API
# ------------------------------------------------------------------------------
def get_gmail_service():
    """Devuelve un objeto service listo para interactuar con Gmail API."""
    creds = load_credentials()
    service = build("gmail", "v1", credentials=creds)
    return service


# ------------------------------------------------------------------------------
# Funcion: Obtener el ultimo correo
# ------------------------------------------------------------------------------
def fetch_last_email(service):
    """
    Recupera el correo mas reciente del buzon.
    Devuelve el ID del mensaje mas nuevo o None si no hay correos.
    """
    results = service.users().messages().list(userId="me", maxResults=1, labelIds=["INBOX"]).execute()
    messages = results.get("messages", [])
    if not messages:
        print("No se encontraron correos en la bandeja de entrada.")
        return None
    return messages[0]["id"]


# ------------------------------------------------------------------------------
# Funcion: Obtener un correo por ID
# ------------------------------------------------------------------------------
def fetch_email_by_id(service, msg_id):
    """
    Obtiene la informacion completa de un correo especifico usando su ID.
    Devuelve el objeto completo del mensaje.
    """
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    return msg


# ------------------------------------------------------------------------------
# Funcion: Analizar el correo y extraer informacion relevante
# ------------------------------------------------------------------------------
def parse_email(msg):
    """
    Procesa un mensaje de Gmail y devuelve un diccionario con:
    - id, remitente, asunto, fecha, etiquetas
    - cuerpo del correo (texto plano)
    - lista de adjuntos (nombres o IDs)
    """
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])

    data = {
        "id": msg["id"],
        "fecha_extraccion": datetime.now(timezone.utc).isoformat(),
    }

    # Extraer encabezados clave
    for h in headers:
        name, value = h["name"].lower(), h["value"]
        if name == "from":
            data["remitente"] = value
        elif name == "subject":
            data["asunto"] = value
        elif name == "date":
            data["fecha_correo"] = value

    # Extraer cuerpo de texto
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                try:
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                    break
                except Exception:
                    continue
    else:
        try:
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        except Exception:
            body = ""

    data["body"] = body.strip()
    data["snippet"] = msg.get("snippet", "")
    data["labels"] = msg.get("labelIds", [])

    # Detectar adjuntos (solo nombres e IDs, sin descargarlos aun)
    attachments = []
    if "parts" in payload:
        for part in payload["parts"]:
            filename = part.get("filename")
            if filename:
                attachments.append(filename)
    data["adjuntos"] = attachments

    return data


# ------------------------------------------------------------------------------
# Funcion: Guardar el correo como JSON en /data/incoming
# ------------------------------------------------------------------------------
def save_email_json(data):
    """
    Guarda la informacion del correo en un archivo JSON con nombre:
    mail_<id>.json dentro de data/incoming/.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    correo_id = data.get("id", f"sin_id_{datetime.now(timezone.utc).timestamp()}")
    path = DATA_DIR / f"mail_{correo_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Correo guardado: {path}")
    return path


# ------------------------------------------------------------------------------
# Funcion principal (punto de entrada)
# ------------------------------------------------------------------------------
def main():
    """
    Controla el flujo general del script:
    - Analiza argumentos (ultimo correo o ID especifico)
    - Conecta con Gmail API
    - Obtiene, parsea y guarda el correo
    """
    parser = argparse.ArgumentParser(description="Lee un correo de Gmail y lo guarda en data/incoming/")
    parser.add_argument("--last", action="store_true", help="Leer el ultimo correo recibido")
    parser.add_argument("--id", type=str, help="Leer un correo especifico por su ID (modo n8n)")
    args = parser.parse_args()

    service = get_gmail_service()

    # Seleccion de modo
    if args.id:
        msg_id = args.id
        print(f"Leyendo correo con ID: {msg_id}")
    elif args.last:
        msg_id = fetch_last_email(service)
        if not msg_id:
            return
        print(f"Ultimo correo detectado: {msg_id}")
    else:
        print("Usa --last o --id para especificar el modo de lectura.")
        return

    # Procesar el correo
    msg = fetch_email_by_id(service, msg_id)
    parsed = parse_email(msg)
    save_email_json(parsed)
    print("Proceso finalizado correctamente.")


# ------------------------------------------------------------------------------
# Ejecucion directa
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
