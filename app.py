
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
import os
import pandas as pd
import hashlib

app = Flask(__name__)
app.secret_key = 'mon_super_secret'

# 🔧 Configuration base de données
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)

# 📁 Fichiers CSV
STUDENT_CREDENTIALS_FILE = 'students.csv'
RESULTS_FILE = 'results.csv'
UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static', exist_ok=True)

# 🔐 Hash
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 🎯 Barème
def calculate_points(main_category, sub_category):
    points_dict = {
        "Cursus Médecine": {"UE supplémentaire facultative": 10},
        "Cursus Hors Médecine": {
            "Année(s) de formation": 10, "Master 1": 40, "Master 2": 60,
            "Thèse d'université": 60, "Publication d'articles": 10
        },
        "Engagement Étudiant": {
            "UE d'engagement associatif": 40,
            "UE d'engagement pédagogique": 40,
            "UE d'engagement social et civique": 40
        },
        "Expérience Professionnelle": {"70h": 10, "140h": 20},
        "Mobilité": {
            "Stage court hors subdivision": 15,
            "Stage court international": 20,
            "Stage Erasmus 1 semestre": 40,
            "Stage Erasmus 2 semestres": 60
        },
        "Linguistique": {
            "Niveau de langue B2": 10,
            "Niveau de langue C1": 20,
            "Niveau de langue C2": 30
        }
    }
    return points_dict.get(main_category, {}).get(sub_category, 0)

# 📌 MODELES BDD
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
    attestations = db.relationship('Attestation', backref='student', lazy=True)

class Attestation(db.Model):
    __tablename__ = 'attestation'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    categorie = db.Column(db.String)
    sous_categorie = db.Column(db.String)
    points = db.Column(db.Integer)
    fichier = db.Column(db.String)
    validation = db.Column(db.String)
    commentaire = db.Column(db.String)

# ✅ Créer les tables
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/validate', methods=['POST'])
def validate_attestation():
    if not session.get('admin'):
        return redirect('/')
    attestation_id = int(request.form['id'])
    attestation = Attestation.query.get(attestation_id)
    if attestation:
        attestation.validation = 'Validée'
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/reject', methods=['POST'])
def reject_attestation():
    if not session.get('admin'):
        return redirect('/')
    attestation_id = int(request.form['id'])
    commentaire = request.form['commentaire']
    attestation = Attestation.query.get(attestation_id)
    if attestation:
        attestation.validation = 'Refusée'
        attestation.commentaire = commentaire
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/export')
def export():
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

    data = [{
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

    df = pd.DataFrame(data)
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
    return render_template('admin_etudiant.html', numero=numero_etudiant, attestations=attestations)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
