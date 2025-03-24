
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import os
import pandas as pd
import hashlib

app = Flask(__name__)
app.secret_key = 'mon_super_secret'
app.config['UPLOAD_FOLDER'] = 'uploads'

UPLOAD_FOLDER = 'uploads'
STUDENT_CREDENTIALS_FILE = 'students.csv'
RESULTS_FILE = 'results.csv'
INFOS_FILE = 'infos_etudiants.csv'

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
    if os.path.exists(RESULTS_FILE):
        df = pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
        df = df[df['Numéro Étudiant'] == session['student']]
    else:
        df = pd.DataFrame()
    return render_template('student_dashboard.html', attestations=df.to_dict(orient='records'))
# Vérifier si l'étudiant a complété ses infos
    infos_fichier = 'infos_etudiants.csv'
    df_infos = pd.read_csv(infos_fichier, encoding='utf-8-sig')
    infos_ok = not df_infos[df_infos['Numéro Étudiant'] == session['student']].empty

    # Charger les attestations existantes
    df = pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
    student_data = df[df['Numéro Étudiant'] == session['student']]

    return render_template('student_dashboard.html',
                           attestations=student_data.to_dict(orient='records'),
                           infos_ok=infos_ok)

@app.route('/student_profile', methods=['GET', 'POST'])
def student_profile():
    if 'student' not in session:
        return redirect(url_for('student_login'))

    df_infos = pd.read_csv(INFOS_FILE, encoding='utf-8-sig')
    etudiant_infos = df_infos[df_infos['Numéro Étudiant'] == session['student']]

    if request.method == 'POST':
        nom = request.form['nom']
        prenom = request.form['prenom']
        promotion = request.form['promotion']
        email = request.form['email']

        # Supprimer l’ancienne ligne si elle existe
        df_infos = df_infos[df_infos['Numéro Étudiant'] != session['student']]
        # Ajouter la nouvelle
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

    # Pour affichage GET
    if not etudiant_infos.empty:
        etudiant = etudiant_infos.iloc[0]
        return render_template('student_profile.html', etudiant=etudiant, deja_renseigne=True)
    else:
        return render_template('student_profile.html', deja_renseigne=False)


@app.route('/upload', methods=['POST'])
def upload():
    if 'student' not in session:
        return redirect(url_for('student_login'))

    # Lire les informations de l'étudiant depuis infos_etudiants.csv
    try:
        df_infos = pd.read_csv(INFOS_FILE, encoding='utf-8-sig')
        etudiant = df_infos[df_infos['Numéro Étudiant'] == session['student']].iloc[0]
    except:
        flash("Veuillez remplir vos informations personnelles.")
        return redirect(url_for('student_profile'))

    # Création du dossier personnalisé
    dossier_etudiant = os.path.join(UPLOAD_FOLDER, f"{etudiant['Nom']}_{etudiant['Prénom']}")
    os.makedirs(dossier_etudiant, exist_ok=True)

    # Récupération du fichier et de l’info formulaire
    categorie = request.form['mainCategory']
    sous_categorie = request.form['categorie']
    fichier = request.files['file']
    points = calculate_points(categorie, sous_categorie)
    filename = fichier.filename

    # Sauvegarde dans le bon dossier
    filepath = os.path.join(dossier_etudiant, filename)
    fichier.save(filepath)

# Sauvegarde dans results.csv
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
    return redirect(url_for('student_dashboard'))  # ✅ retour obligatoire

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    try:
        df_infos = pd.read_csv(INFOS_FILE, encoding='utf-8-sig')
        etudiant = df_infos[df_infos['Numéro Étudiant'] == session['student']].iloc[0]
    except:
        flash("Veuillez remplir vos informations personnelles.")
        return redirect(url_for('student_profile'))

    new_row = pd.DataFrame([{
        "Nom": etudiant['Nom'],
        "Prénom": etudiant['Prénom'],
        "Numéro Étudiant": session['student'],
        "Catégorie": categorie,
        "Sous-catégorie": sous_categorie,
        "Points": points,
        "Fichier": filename,
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


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)

