from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_etudiant = db.Column(db.String(50), unique=True, nullable=False)
    mot_de_passe = db.Column(db.String(128), nullable=False)
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    email = db.Column(db.String(120))
    promotion = db.Column(db.String(20))
    attestations = db.relationship('Attestation', backref='etudiant', lazy=True)

class Attestation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    categorie = db.Column(db.String(100))
    sous_categorie = db.Column(db.String(100))
    fichier = db.Column(db.String(200))
    points = db.Column(db.Integer)
    validation = db.Column(db.String(20), default="En attente")
    commentaire = db.Column(db.String(255))
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
