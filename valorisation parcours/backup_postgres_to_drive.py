import os
import datetime
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from models import db, Student, Attestation
from app import app

# === CONFIGURATION ===
CREDENTIALS_FILE = 'credentials_gdrive.json'
DRIVE_FOLDER_ID = '17XIrph3Lv7vcIxWtXKXR5tfLb6aGVsXv'

# === NOM DU FICHIER DE SAUVEGARDE ===
date_str = datetime.datetime.now().strftime("%Y-%m-%d")
backup_filename = f"sauvegarde_valoparc_{date_str}.csv"

# === EXTRACTION DES DONNÉES SQL VERS CSV ===
with app.app_context():
    print("📥 Récupération des attestations depuis la base...")
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
            'Fichier': a.fichier,
        })

    df = pd.DataFrame(data)
    df.to_csv(backup_filename, index=False, encoding='utf-8-sig')

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

print("🚀 Envoi du fichier vers Google Drive...")
uploaded_file = service.files().create(
    body=file_metadata,
    media_body=media,
    fields='id'
).execute()

print(f"✅ Sauvegarde envoyée avec succès ! Fichier ID : {uploaded_file['id']}")

# (Optionnel) Supprimer le fichier local
os.remove(backup_filename)
