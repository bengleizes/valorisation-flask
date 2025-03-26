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
    __tablename__ = 'student'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    numero_etudiant = db.Column(db.String, unique=True)
    nom = db.Column(db.String)
    prenom = db.Column(db.String)
    email = db.Column(db.String)
    promotion = db.Column(db.String)
    mot_de_passe = db.Column(db.String)

with app.app_context():
    db.create_all()

class StudentInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_etudiant = db.Column(db.String, db.ForeignKey('student.numero_etudiant'), unique=True)
    nom = db.Column(db.String)
    prenom = db.Column(db.String)
    promotion = db.Column(db.String)
    email = db.Column(db.String)

with app.app_context():
    db.create_all()

class Attestation(db.Model):
    __tablename__ = 'attestation'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    student = db.relationship('Student', backref='attestations')
    categorie = db.Column(db.String)
    sous_categorie = db.Column(db.String)
    points = db.Column(db.Integer)
    fichier = db.Column(db.String)
    validation = db.Column(db.String)
    commentaire = db.Column(db.String)

with app.app_context():
    db.create_all()

class StudentProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_etudiant = db.Column(db.String, db.ForeignKey('student.numero_etudiant'), unique=True)
    nom = db.Column(db.String)
    prenom = db.Column(db.String)
    email = db.Column(db.String)
    promotion = db.Column(db.String)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        student_number = request.form['student_number']
        password = hash_password(request.form['password'])

        # Vérifie d'abord si l'étudiant est déjà dans la base
        existing_student = Student.query.filter_by(numero_etudiant=student_number).first()
        if existing_student:
            flash('Ce numéro est déjà enregistré')
            return redirect(url_for('student_register'))

        # Sauvegarde dans le fichier CSV (optionnel mais conservé)
        if os.path.exists(STUDENT_CREDENTIALS_FILE):
            df = pd.read_csv(STUDENT_CREDENTIALS_FILE, encoding='utf-8-sig')
        else:
            df = pd.DataFrame(columns=['Numéro Étudiant', 'Mot de Passe'])

        df.loc[len(df)] = [student_number, password]
        df.to_csv(STUDENT_CREDENTIALS_FILE, index=False, encoding='utf-8-sig')

        # ➕ Ajoute aussi dans la base de données
        new_student = Student(numero_etudiant=student_number, mot_de_passe=password)
        db.session.add(new_student)
        db.session.commit()

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

    student = Student.query.filter_by(numero_etudiant=session['student']).first()
    if not student:
        flash("Étudiant introuvable.")
        return redirect(url_for('student_login'))

    infos_ok = all([student.nom, student.prenom, student.email, student.promotion])

    # Récupération des attestations en BDD
    attestations = Attestation.query.filter_by(student_id=student.id).all()

    return render_template('student_dashboard.html',
                           attestations=attestations,
                           infos_ok=infos_ok,
                           etudiant=student)


@app.route('/student_profile', methods=['GET', 'POST'])
def student_profile():
    if 'student' not in session:
        return redirect(url_for('student_login'))

    numero_etudiant = session['student']
    profile = StudentProfile.query.filter_by(numero_etudiant=numero_etudiant).first()

    if request.method == 'POST':
        nom = request.form['nom']
        prenom = request.form['prenom']
        promotion = request.form['promotion']
        email = request.form['email']

        if profile:
            # Mise à jour
            profile.nom = nom
            profile.prenom = prenom
            profile.promotion = promotion
            profile.email = email
        else:
            # Nouveau profil
            profile = StudentProfile(
                numero_etudiant=numero_etudiant,
                nom=nom,
                prenom=prenom,
                promotion=promotion,
                email=email
            )
            db.session.add(profile)

        db.session.commit()
        flash("Informations mises à jour avec succès.")
        return redirect(url_for('student_profile'))

    deja_renseigne = profile is not None
    return render_template('student_profile.html', etudiant=profile, deja_renseigne=deja_renseigne)


@app.route('/upload', methods=['POST'])
def upload():
    if 'student' not in session:
        return redirect(url_for('student_login'))

    # Récupération des infos de l'étudiant
    student = Student.query.filter_by(numero_etudiant=session['student']).first()
    if not student:
        flash("Étudiant non trouvé. Merci de vérifier votre compte.")
        return redirect(url_for('student_profile'))

    # Création du dossier de stockage local
    dossier_etudiant = os.path.join(UPLOAD_FOLDER, f"{student.nom}_{student.prenom}")
    os.makedirs(dossier_etudiant, exist_ok=True)

    # Récupération des infos du formulaire
    categorie = request.form['mainCategory']
    sous_categorie = request.form['categorie']
    fichier = request.files['file']
    filename = fichier.filename
    points = calculate_points(categorie, sous_categorie)

    # Sauvegarde du fichier en local
    filepath = os.path.join(dossier_etudiant, filename)
    fichier.save(filepath)

    # Enregistrement dans la base de données PostgreSQL
    nouvelle_attestation = Attestation(
        student_id=student.id,
        categorie=categorie,
        sous_categorie=sous_categorie,
        points=points,
        fichier=f"{student.nom}_{student.prenom}/{filename}",
        validation="En attente",
        commentaire=""
    )
    db.session.add(nouvelle_attestation)
    db.session.commit()

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

    attestations = Attestation.query.join(Student).add_columns(
        Student.numero_etudiant,
        Student.nom,
        Student.prenom,
        Attestation.categorie,
        Attestation.sous_categorie,
        Attestation.points,
        Attestation.fichier,
        Attestation.validation,
        Attestation.commentaire
    ).all()

    # Reformater les résultats pour le template
    formatted_attestations = [{
        'Numéro Étudiant': a.numero_etudiant,
        'Nom': a.nom,
        'Prénom': a.prenom,
        'Catégorie': a.categorie,
        'Sous-catégorie': a.sous_categorie,
        'Points': a.points,
        'Fichier': a.fichier,
        'Validation': a.validation,
        'Commentaire': a.commentaire
    } for a in attestations]

    return render_template('admin.html', attestations=formatted_attestations)


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
