from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, send_file
import os
import pandas as pd
import hashlib
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from flask_sqlalchemy import SQLAlchemy
from models import db, Student, Attestation


app = Flask(__name__)
import os
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

app.secret_key = 'mon_super_secret'
UPLOAD_FOLDER = 'uploads'
STUDENT_CREDENTIALS_FILE = 'students.csv'
RESULTS_FILE = 'results.csv'
INFOS_FILE = 'infos_etudiants.csv'
SERVICE_ACCOUNT_FILE = '/etc/secrets/credentials_gdrive.json'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static', exist_ok=True)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        student_number = request.form['student_number']
        password = hash_password(request.form['password'])

        # Vérifie s'il existe déjà
        existing = Student.query.filter_by(numero_etudiant=student_number).first()
        if existing:
            flash('Ce numéro est déjà enregistré')
            return redirect(url_for('student_register'))

        # Crée l'étudiant
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

        student = Student.query.filter_by(numero_etudiant=student_number).first()

        if student and student.mot_de_passe == password:
            session['student'] = student.numero_etudiant
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

    attestations = Attestation.query.filter_by(student_id=student.id).all()

    # Vérifie s’il a bien rempli ses infos
    infos_ok = all([student.nom, student.prenom, student.email, student.promotion])

    return render_template('student_dashboard.html',
                           attestations=attestations,
                           infos_ok=infos_ok,
                           etudiant=student)


@app.route('/student_profile', methods=['GET', 'POST'])
def student_profile():
    if 'student' not in session:
        return redirect(url_for('student_login'))

    student = Student.query.filter_by(numero_etudiant=session['student']).first()
    if not student:
        flash("Étudiant introuvable.")
        return redirect(url_for('student_login'))

    if request.method == 'POST':
        student.nom = request.form['nom']
        student.prenom = request.form['prenom']
        student.promotion = request.form['promotion']
        student.email = request.form['email']
        db.session.commit()
        flash("Informations mises à jour avec succès.")
        return redirect(url_for('student_profile'))

    deja_renseigne = all([student.nom, student.prenom, student.email, student.promotion])
    return render_template('student_profile.html', etudiant=student, deja_renseigne=deja_renseigne)


@app.route('/upload', methods=['POST'])
def upload():
    if 'student' not in session:
        return redirect(url_for('student_login'))

    student = Student.query.filter_by(numero_etudiant=session['student']).first()
    if not student:
        flash("Utilisateur non trouvé.")
        return redirect(url_for('student_login'))

    categorie = request.form['mainCategory']
    sous_categorie = request.form['categorie']
    fichier = request.files['file']
    points = calculate_points(categorie, sous_categorie)
    filename = fichier.filename

    dossier_etudiant = os.path.join(app.config['UPLOAD_FOLDER'], f"{student.nom}_{student.prenom}")
    os.makedirs(dossier_etudiant, exist_ok=True)
    filepath = os.path.join(dossier_etudiant, filename)
    fichier.save(filepath)

    # Ajout dans la BDD
    attestation = Attestation(
        categorie=categorie,
        sous_categorie=sous_categorie,
        fichier=f"{student.nom}_{student.prenom}/{filename}",
        points=points,
        student_id=student.id
    )
    db.session.add(attestation)
    db.session.commit()

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
        Attestation.id,
        Attestation.categorie,
        Attestation.sous_categorie,
        Attestation.points,
        Attestation.validation,
        Attestation.commentaire,
        Attestation.fichier,
        Student.nom,
        Student.prenom,
        Student.numero_etudiant
    ).all()

    return render_template('admin.html', attestations=attestations)


@app.route('/validate', methods=['POST'])
def validate_attestation():
    if not session.get('admin'):
        return redirect('/')
    attestation_id = int(request.form['attestation_id'])
    attestation = Attestation.query.get(attestation_id)
    attestation.validation = "Validée"
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/reject', methods=['POST'])
def reject_attestation():
    if not session.get('admin'):
        return redirect('/')
    attestation_id = int(request.form['attestation_id'])
    commentaire = request.form['commentaire']
    attestation = Attestation.query.get(attestation_id)
    attestation.validation = "Refusée"
    attestation.commentaire = commentaire
    db.session.commit()
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

    student = Student.query.filter_by(numero_etudiant=numero_etudiant).first()
    if not student:
        return "Étudiant introuvable", 404

    attestations = Attestation.query.filter_by(student_id=student.id).all()

    return render_template('admin_etudiant.html',
                           etudiant=student,
                           attestations=attestations)


@app.route('/sauvegarde_drive', methods=['POST'])
def sauvegarde_drive():
    if not session.get('admin'):
        return redirect('/')

    # Paramètres du fichier
    local_file = 'results.csv'
    drive_filename = 'sauvegarde_results.csv'
    folder_id = '17XIrph3Lv7vcIxWtXKXR5tfLb6aGVsXv?lfhs=2'  # à remplacer !

    try:
        credentials = service_account.Credentials.from_service_account_file(
            'credentials_gdrive.json',
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        service = build('drive', 'v3', credentials=credentials)

        file_metadata = {'name': drive_filename}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaFileUpload(local_file, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        flash("✅ Fichier sauvegardé sur Google Drive avec succès !")
    except Exception as e:
        flash(f"❌ Erreur lors de l'envoi : {e}")

    return redirect(url_for('admin'))
with app.app_context():
    db.create_all()



if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
