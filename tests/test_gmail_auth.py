from __future__ import print_function
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pathlib


# Scopes mínimos (lectura + modificar etiquetas)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def main():
    creds = None
    BASE_DIR = pathlib.Path(__file__).resolve().parent.parent  # sube a la raíz del proyecto
    cred_path = BASE_DIR / "config" / "credentials" / "gmail_credentials.json"
    token_path = BASE_DIR / "config" / "credentials" / "token.json"

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)

    # Prueba: listar los últimos 5 correos de la bandeja de entrada
    results = service.users().messages().list(userId='me', maxResults=5).execute()
    messages = results.get('messages', [])

    if not messages:
        print("No hay correos.")
    else:
        print("Últimos 5 correos:")
        for msg in messages:
            print(f"- ID: {msg['id']}")

if __name__ == '__main__':
    main()
