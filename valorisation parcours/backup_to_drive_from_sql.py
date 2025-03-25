import os
import datetime
import pandas as pd
from app import app, db, Student, Attestation
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === CONFIG ===
CREDENTIALS_FILE = 'credentials_gdrive.json'
DRIVE_FOLDER_ID = '17XIrph3Lv7vcIxWtXKXR5tfLb6aGVsXv'
date_str = datetime.datetime.now().strftime("%Y-%m-%d")
backup_filename = f"sauvegarde_valoparc_{date_str}.csv"

with app.app_context():
    print("📥 Récupération des données...")
    attestations = Attestation.query.all()
    data = []

    for a in attestations:
        student = Student.query.get(a.student_id)
        data.append({
            'Numéro étudiant': student.numero_etudiant,
            'Nom': student.nom,
            'Prénom': student.prenom,
            'Catégorie': a.categorie,
            'Sous-catégorie': a.sous_categorie,
            'Points': a.points,
            'Validation': a.validation,
            'Commentaire': a.commentaire,
            'Fichier': a.fichier
        })

    df = pd.DataFrame(data)
    df.to_csv(backup_filename, index=False, encoding='utf-8-sig')

# === Upload vers Google Drive
print("☁️ Envoi vers Google Drive...")
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

uploaded_file = service.files().create(
    body=file_metadata,
    media_body=media,
    fields='id'
).execute()

print(f"✅ Fichier sauvegardé sur Google Drive : ID {uploaded_file['id']}")

os.remove(backup_filename)
