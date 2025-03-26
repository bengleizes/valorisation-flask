from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
import os
import pandas as pd
import hashlib

app = Flask(__name__)
app.secret_key = 'mon_super_secret'

# 🔧 Configuration base de données (Render ou local)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)

# 📁 Fichiers CSV utilisés en complément
STUDENT_CREDENTIALS_FILE = 'students.csv'
RESULTS_FILE = 'results.csv'
INFOS_FILE = 'infos_etudiants.csv'
UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static', exist_ok=True)

# 🔐 Hashage des mots de passe
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 🎯 Barème des points
def calculate_points(main_category, sub_category):
    points_dict = {
        "Cursus Médecine": {"UE supplémentaire facultative": 10},
        "Cursus Hors Médecine": {"Année(s) de formation": 10, "Master 1": 40, "Master 2": 60, "Thèse d'université": 60, "Publication d'articles": 10},
        "Engagement Étudiant": {"UE d'engagement associatif": 40, "UE d'engagement pédagogique": 40, "UE d'engagement social et civique": 40},
        "Expérience Professionnelle": {"70h": 10, "140h": 20},
        "Mobilité": {"Stage court hors subdivision": 15, "Stage court international": 20, "Stage Erasmus 1 semestre": 40, "Stage Erasmus 2 semestres": 60},
        "Linguistique": {"Niveau de langue B2": 10, "Niveau de langue C1": 20, "Niveau de langue C2": 30}
    }
    return points_dict.get(main_category, {}).get(sub_category, 0)

# 🧠 Modèles BDD (pour usage futur ou mixte)
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_etudiant = db.Column(db.String, unique=True)
    nom = db.Column(db.String)
    prenom = db.Column(db.String)
    email = db.Column(db.String)
    promotion = db.Column(db.String)
    mot_de_passe = db.Column(db.String)

class Attestation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    categorie = db.Column(db.String)
    sous_categorie = db.Column(db.String)
    points = db.Column(db.Integer)
    fichier = db.Column(db.String)
    validation = db.Column(db.String)
    commentaire = db.Column(db.String)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        student_number = request.form['student_number']
        password = hash_password(request.form['password'])
        if os.path.exists(STUDENT_CREDENTIALS_FILE):
            df = pd.read_csv(STUDENT_CREDENTIALS_FILE, encoding='utf-8-sig')
        else:
            df = pd.DataFrame(columns=['Numéro Étudiant', 'Mot de Passe'])
        if student_number in df['Numéro Étudiant'].values:
            flash('Ce numéro est déjà enregistré')
            return redirect(url_for('student_register'))
        df.loc[len(df)] = [student_number, password]
        df.to_csv(STUDENT_CREDENTIALS_FILE, index=False, encoding='utf-8-sig')
        flash('Inscription réussie')
        return redirect(url_for('student_login'))
    return render_template('student_register.html')

@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        student_number = request.form['student_number']
        password = hash_password(request.form['password'])
        try:
            df = pd.read_csv(STUDENT_CREDENTIALS_FILE, encoding='utf-8-sig')
        except pd.errors.EmptyDataError:
            flash('Erreur avec le fichier étudiant')
            return redirect(url_for('student_login'))
        user = df[df['Numéro Étudiant'] == student_number]
        if not user.empty and user.iloc[0]['Mot de Passe'] == password:
            session['student'] = student_number
            return redirect(url_for('student_dashboard'))
        flash('Identifiants incorrects')
    return render_template('student_login.html')

@app.route('/student_dashboard')
def student_dashboard():
    if 'student' not in session:
        return redirect(url_for('student_login'))

    infos_ok = False
    if os.path.exists(INFOS_FILE):
        df_infos = pd.read_csv(INFOS_FILE, encoding='utf-8-sig')
        infos_ok = not df_infos[df_infos['Numéro Étudiant'] == session['student']].empty

    if os.path.exists(RESULTS_FILE):
        df = pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
        student_data = df[df['Numéro Étudiant'] == session['student']]
    else:
        student_data = pd.DataFrame()

    return render_template('student_dashboard.html',
                           attestations=student_data.to_dict(orient='records'),
                           infos_ok=infos_ok)

@app.route('/student_profile', methods=['GET', 'POST'])
def student_profile():
    if 'student' not in session:
        return redirect(url_for('student_login'))

    if os.path.exists(INFOS_FILE):
        df_infos = pd.read_csv(INFOS_FILE, encoding='utf-8-sig')
    else:
        df_infos = pd.DataFrame(columns=['Numéro Étudiant', 'Nom', 'Prénom', 'Promotion', 'Email'])

    etudiant_infos = df_infos[df_infos['Numéro Étudiant'] == session['student']]

    if request.method == 'POST':
        nom = request.form['nom']
        prenom = request.form['prenom']
        promotion = request.form['promotion']
        email = request.form['email']
        df_infos = df_infos[df_infos['Numéro Étudiant'] != session['student']]
        nouvelle_ligne = pd.DataFrame([{
            'Numéro Étudiant': session['student'],
            'Nom': nom,
            'Prénom': prenom,
            'Promotion': promotion,
            'Email': email
        }])
        df_infos = pd.concat([df_infos, nouvelle_ligne], ignore_index=True)
        df_infos.to_csv(INFOS_FILE, index=False, encoding='utf-8-sig')
        flash("Informations mises à jour avec succès.")
        return redirect(url_for('student_profile'))

    if not etudiant_infos.empty:
        etudiant = etudiant_infos.iloc[0]
        return render_template('student_profile.html', etudiant=etudiant, deja_renseigne=True)
    else:
        return render_template('student_profile.html', deja_renseigne=False)

@app.route('/upload', methods=['POST'])
def upload():
    if 'student' not in session:
        return redirect(url_for('student_login'))

    try:
        df_infos = pd.read_csv(INFOS_FILE, encoding='utf-8-sig')
        etudiant = df_infos[df_infos['Numéro Étudiant'] == session['student']].iloc[0]
    except:
        flash("Veuillez remplir vos informations personnelles.")
        return redirect(url_for('student_profile'))

    dossier_etudiant = os.path.join(UPLOAD_FOLDER, f"{etudiant['Nom']}_{etudiant['Prénom']}")
    os.makedirs(dossier_etudiant, exist_ok=True)

    categorie = request.form['mainCategory']
    sous_categorie = request.form['categorie']
    fichier = request.files['file']
    points = calculate_points(categorie, sous_categorie)
    filename = fichier.filename
    filepath = os.path.join(dossier_etudiant, filename)
    fichier.save(filepath)

# === 🔄 Sauvegarde sur Google Drive ===
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Charger les credentials
creds = service_account.Credentials.from_service_account_file(
    'credentials_gdrive.json',
    scopes=['https://www.googleapis.com/auth/drive']
)
service = build('drive', 'v3', credentials=creds)

# Nom du dossier Drive = "Nom_Prenom"
nom_dossier_drive = f"{etudiant['Nom']}_{etudiant['Prénom']}"

# 1. Chercher si le dossier existe déjà
query = f"name = '{nom_dossier_drive}' and mimeType = 'application/vnd.google-apps.folder'"
results = service.files().list(q=query, fields="files(id)").execute()
dossiers = results.get('files', [])

# 2. Créer le dossier s’il n’existe pas
if not dossiers:
    folder_metadata = {
        'name': nom_dossier_drive,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': ['17XIrph3Lv7vcIxWtXKXR5tfLb6aGVsXv']  # ID de ton dossier Google Drive Racine
    }
    dossier_drive = service.files().create(body=folder_metadata, fields='id').execute()
    dossier_id = dossier_drive.get('id')
else:
    dossier_id = dossiers[0]['id']

# 3. Envoyer le fichier
media = MediaFileUpload(filepath, resumable=True)
fichier_metadata = {'name': filename, 'parents': [dossier_id]}
service.files().create(body=fichier_metadata, media_body=media, fields='id').execute()

new_row = pd.DataFrame([{
        "Nom": etudiant['Nom'],
        "Prénom": etudiant['Prénom'],
        "Numéro Étudiant": session['student'],
        "Catégorie": categorie,
        "Sous-catégorie": sous_categorie,
        "Points": points,
        "Fichier": f"{etudiant['Nom']}_{etudiant['Prénom']}/{filename}",
        "Validation": "En attente",
        "Commentaire": ""
}])

if os.path.exists(RESULTS_FILE):
        df = pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
        df = pd.concat([df, new_row], ignore_index=True)
else:
        df = new_row

df.to_csv(RESULTS_FILE, index=False, encoding='utf-8-sig')

flash("Document soumis avec succès.")
   return redirect(url_for('student_dashboard'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def logout():
    session.pop('student', None)
    session.pop('admin', None)
    return redirect(url_for('index'))

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/')

@app.route('/admin_login', methods=['POST'])
def admin_login():
    if request.form['admin_code'] == 'admin123':
        session['admin'] = True
        return redirect('/admin')
    return redirect('/')

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/')
    df = pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
    return render_template('admin.html', attestations=df.to_dict(orient='records'))

@app.route('/validate', methods=['POST'])
def validate_attestation():
    if not session.get('admin'):
        return redirect('/')
    index = int(request.form['index'])
    df = pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
    df.loc[index, 'Validation'] = 'Validée'
    df.to_csv(RESULTS_FILE, index=False, encoding='utf-8-sig')
    return redirect(url_for('admin'))

@app.route('/reject', methods=['POST'])
def reject_attestation():
    if not session.get('admin'):
        return redirect('/')
    index = int(request.form['index'])
    commentaire = request.form['commentaire']
    df = pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
    df.loc[index, 'Validation'] = 'Refusée'
    df.loc[index, 'Commentaire'] = commentaire
    df.to_csv(RESULTS_FILE, index=False, encoding='utf-8-sig')
    return redirect(url_for('admin'))

@app.route('/export')
def export():
    df = pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
    export_file = 'export_admin.xlsx'
    df.to_excel(export_file, index=False)
    return send_file(export_file, as_attachment=True)

@app.route('/admin/etudiant/<numero_etudiant>')
def admin_etudiant(numero_etudiant):
    if not session.get('admin'):
        return redirect('/')
    df = pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
    etudiant_docs = df[df['Numéro Étudiant'] == numero_etudiant]
    return render_template('admin_etudiant.html', numero=numero_etudiant, attestations=etudiant_docs.to_dict(orient='records'))

# 🔁 Export pour d'autres scripts

from flask_sqlalchemy import SQLAlchemy




if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
