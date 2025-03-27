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
# STUDENT_CREDENTIALS_FILE = 'students.csv'
# RESULTS_FILE = 'results.csv'
# INFOS_FILE = 'infos_etudiants.csv'
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

        # Vérifier si le compte existe déjà
        existing = Student.query.filter_by(numero_etudiant=student_number).first()
        if existing:
            flash("Ce numéro est déjà enregistré.")
            return redirect(url_for('student_register'))

        # Créer et enregistrer
        new_student = Student(
            numero_etudiant=student_number,
            mot_de_passe=password,
            nom="",
            prenom="",
            email="",
            promotion=""
        )
        db.session.add(new_student)
        db.session.commit()

        flash("Inscription réussie.")
        return redirect(url_for('student_login'))

    return render_template('student_register.html')



@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        student_number = request.form['student_number']
        password = hash_password(request.form['password'])

        # Recherche en base
        student = Student.query.filter_by(numero_etudiant=student_number).first()

        if student and student.mot_de_passe == password:
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

        profile = StudentProfile.query.filter_by(numero_etudiant=numero_etudiant).first()

        flash("Informations mises à jour avec succès.")
        return redirect(url_for('student_profile'))

    deja_renseigne = profile is not None
    return render_template('student_profile.html', etudiant=profile, deja_renseigne=deja_renseigne)


@app.route('/upload', methods=['POST'])
def upload():
    if 'student' not in session:
        return redirect(url_for('student_login'))

    student = Student.query.filter_by(numero_etudiant=session['student']).first()
    if not student:
        flash("Étudiant non trouvé.")
        return redirect(url_for('student_profile'))

    categorie = request.form['mainCategory']
    sous_categorie = request.form['categorie']
    fichier = request.files['file']
    filename = fichier.filename
    points = calculate_points(categorie, sous_categorie)

    # Création du dossier local
    dossier_etudiant = os.path.join(UPLOAD_FOLDER, f"{student.nom}_{student.prenom}")
    os.makedirs(dossier_etudiant, exist_ok=True)
    filepath = os.path.join(dossier_etudiant, filename)
    fichier.save(filepath)

    # Enregistrement dans la base
    attestation = Attestation(
        student_id=student.id,
        categorie=categorie,
        sous_categorie=sous_categorie,
        points=points,
        fichier=f"{student.nom}_{student.prenom}/{filename}",
        validation="En attente",
        commentaire=""
    )
    db.session.add(attestation)
    db.session.commit()

    # 🔁 Sauvegarde sur Google Drive
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = service_account.Credentials.from_service_account_file(
        'credentials_gdrive.json',
        scopes=['https://www.googleapis.com/auth/drive']
    )
    service = build('drive', 'v3', credentials=creds)
    nom_dossier_drive = f"{student.nom}_{student.prenom}"

    query = f"name = '{nom_dossier_drive}' and mimeType = 'application/vnd.google-apps.folder'"
    results = service.files().list(q=query, fields="files(id)").execute()
    dossiers = results.get('files', [])

    if not dossiers:
        folder_metadata = {
            'name': nom_dossier_drive,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': ['17XIrph3Lv7vcIxWtXKXR5tfLb6aGVsXv']
        }
        dossier_drive = service.files().create(body=folder_metadata, fields='id').execute()
        dossier_id = dossier_drive.get('id')
    else:
        dossier_id = dossiers[0]['id']

    media = MediaFileUpload(filepath, resumable=True)
    fichier_metadata = {'name': filename, 'parents': [dossier_id]}
    service.files().create(body=fichier_metadata, media_body=media, fields='id').execute()

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

    attestations = Attestation.query.join(Student).all()
    return render_template('admin.html', attestations=attestations)


@app.route('/validate', methods=['POST'])
def validate_attestation():
    if not session.get('admin'):
        return redirect('/')

    attestation_id = request.form['attestation_id']
    attestation = Attestation.query.get(attestation_id)
    if attestation:
        attestation.validation = 'Validée'
        db.session.commit()
        flash("Attestation validée avec succès.")
    return redirect(url_for('admin'))


@app.route('/reject', methods=['POST'])
def reject_attestation():
    if not session.get('admin'):
        return redirect('/')

    attestation_id = request.form['attestation_id']
    commentaire = request.form['commentaire']
    attestation = Attestation.query.get(attestation_id)
    if attestation:
        attestation.validation = 'Refusée'
        attestation.commentaire = commentaire
        db.session.commit()
        flash("Attestation refusée avec commentaire.")
    return redirect(url_for('admin'))

@app.route('/export')
def export():
    # df = pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
    export_file = 'export_admin.xlsx'
    df.to_excel(export_file, index=False)
    return send_file(export_file, as_attachment=True)

@app.route('/admin/etudiant/<numero_etudiant>')
def admin_etudiant(numero_etudiant):
    if not session.get('admin'):
        return redirect('/')

    student = Student.query.filter_by(numero_etudiant=numero_etudiant).first()
    if not student:
        flash("Étudiant introuvable.")
        return redirect(url_for('admin'))

    attestations = Attestation.query.filter_by(student_id=student.id).all()

    return render_template('admin_etudiant.html',
                           numero=numero_etudiant,
                           attestations=attestations)


# 🔁 Export pour d'autres scripts

from flask_sqlalchemy import SQLAlchemy

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
