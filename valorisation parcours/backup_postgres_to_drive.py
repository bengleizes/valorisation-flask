import os
import datetime
import subprocess
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === CONFIGURATION ===
DATABASE_URL = os.environ.get("DATABASE_URL")
CREDENTIALS_FILE = 'credentials_gdrive.json'
DRIVE_FOLDER_ID = '17XIrph3Lv7vcIxWtXKXR5tfLb6aGVsXv'

# === NOM DU FICHIER DE SAUVEGARDE ===
date_str = datetime.datetime.now().strftime("%Y-%m-%d")
backup_filename = f"sauvegarde_valoparc_{date_str}.sql"

# === UTILISER pg_dump POUR EXPORTER LA BASE ===
print("📦 Export de la base PostgreSQL...")
command = f'pg_dump "{DATABASE_URL}" > {backup_filename}'
exit_code = os.system(command)

if exit_code != 0:
    print("❌ Échec de l'export avec pg_dump.")
    exit(1)

# === ENVOI VERS GOOGLE DRIVE ===
print("☁️ Connexion à Google Drive...")
creds = service_account.Credentials.from_service_account_file(
    CREDENTIALS_FILE,
    scopes=['https://www.googleapis.com/auth/drive.file']
)
service = build('drive', 'v3', credentials=creds)

file_metadata = {
    'name': backup_filename,
    'parents': [DRIVE_FOLDER_ID]
}
media = MediaFileUpload(backup_filename, resumable=True)

print("🚀 Envoi de la sauvegarde...")
uploaded_file = service.files().create(
    body=file_metadata,
    media_body=media,
    fields='id'
).execute()

print(f"✅ Sauvegarde envoyée avec succès ! Fichier ID : {uploaded_file['id']}")

# (Optionnel) Supprimer le fichier local après envoi
os.remove(backup_filename)
