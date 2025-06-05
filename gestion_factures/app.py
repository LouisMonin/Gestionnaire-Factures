"""
# gestion_factures/app.py
# Application Flask pour la gestion des factures
# Ce script permet aux utilisateurs de télécharger, analyser et gérer leurs factures.
# Il inclut des fonctionnalités de connexion, d'inscription, de téléchargement de fichiers, d'analyse OCR et de visualisation des factures.
# Il utilise SQLite pour stocker les données des factures et des utilisateurs.
# Il est conçu pour être simple et extensible, avec une interface utilisateur basique en HTML.
# Il nécessite les bibliothèques Flask, SQLite, pytesseract, PIL (Pillow), pdf2image et pandas.
# """

from flask import Flask, jsonify, render_template, request, redirect, flash, url_for, session, make_response
from database import init_db, insert_facture, ajouter_utilisateur, verifier_utilisateur
import os
import pytesseract
from PIL import Image
import re
import sqlite3
import csv
import io
from pdf2image import convert_from_path
import pandas as pd
from datetime import datetime, date

""" Configuration de l'application Flask """

app = Flask(__name__)
app.secret_key = 'ma_clé_secrète'
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

""" Initialisation de la base de données """

@app.before_request
def verifier_connexion():
    """ Vérifie si l'utilisateur est connecté avant d'accéder à certaines routes """
    if request.endpoint in ['upload', 'afficher_factures', 'analyse'] and 'utilisateur_id' not in session:
        return redirect(url_for('login'))

@app.route('/')
def accueil():
    """Route principale de l'application.Cette route redirige vers la page de connexion
    si l'utilisateur n'est pas connecté."""
    if 'utilisateur_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """ Routes pour la gestion des utilisateurs """
    if request.method == 'POST':
        pseudo = request.form['pseudo']
        mot_de_passe = request.form['mot_de_passe']
        utilisateur = verifier_utilisateur(pseudo, mot_de_passe)

        if utilisateur:
            session['utilisateur_id'] = utilisateur[0]
            session['pseudo'] = utilisateur[6]
            return redirect('/')
        else:
            flash("❌ Profil inexistant ou mot de passe incorrect.", "error")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """ Route pour l'inscription d'un nouvel utilisateur """
    if request.method == 'POST':
        success = ajouter_utilisateur(
            request.form['nom'],
            request.form['prenom'],
            int(request.form['age']),
            request.form['secteur'],
            request.form['email'],
            request.form['pseudo'],
            request.form['mot_de_passe']
        )
        if success:
            flash("✅ Compte créé avec succès. Connectez-vous.", "success")
            return redirect('/login')
        else:
            flash("⚠️ Un compte existe déjà avec cette adresse email.", "error")
            return redirect('/register')

    return render_template('register.html')

@app.route('/logout')
def logout():
    """ Route pour la déconnexion de l'utilisateur """
    session.clear()
    return redirect('/login')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """ Route pour télécharger et traiter les factures """
    if request.method == 'POST':
        # Si soumission du formulaire après prévisualisation
        if 'nom_entreprise' in request.form:
            nom_fichier = request.form.get("nom_fichier")  # 🔧 utiliser la vraie valeur
            nom_entreprise = request.form.get("nom_entreprise")
            numero_client = request.form.get("numero_client")
            numero_facture = request.form.get("numero_facture")
            date_facture = request.form.get("date_facture")
            echeance = request.form.get("echeance")
            tva = request.form.get("tva")
            total_ttc = request.form.get("total_ttc")
            somme_finale = request.form.get("somme_finale")
            facture_payee =  0 # Par défaut, on considère que la facture n'est pas payée
            insert_facture(
                nom_entreprise,
                date_facture,
                numero_facture,
                total_ttc,
                tva,
                session['utilisateur_id'],
                nom_fichier,  # ✅ bon nom de fichier
                facture_payee,
                numero_client,
                echeance,
                somme_finale
            )

            flash("✅ Facture validée et enregistrée avec succès !", "success")
            return redirect(url_for('accueil'))

        # 📨 Traitement de l'upload initial
        if 'facture' not in request.files:
            flash("❌ Aucun fichier sélectionné.", "error")
            return redirect(url_for('upload'))

        fichier = request.files['facture']
        if fichier.filename == '':
            flash("❌ Fichier vide.", "error")
            return redirect(url_for('upload'))

        nom_fichier = fichier.filename
        chemin_fichier = os.path.join(app.config['UPLOAD_FOLDER'], nom_fichier)
        print(">>> Nom du fichier reçu :", fichier.filename)
        print(">>> Sauvegarde dans :", chemin_fichier)

        fichier.save(chemin_fichier)

        flash("✅ Fichier uploadé avec succès, veuillez valider les informations extraites.", "success")
        return render_template('upload.html')

    return render_template('upload.html')



@app.route('/factures')
def afficher_factures():
    """ Route pour afficher les factures de l'utilisateur """
    conn = sqlite3.connect('factures.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM factures WHERE utilisateur_id = ?', (session['utilisateur_id'],))
    factures = c.fetchall()
    conn.close()

    payee_filter = request.args.get('checkbox_paiement')  # '1' si cochée, None sinon
    filter_active = request.args.get('filter_active', '0') == '1'  # '1' si le filtre est actif

    # Appliquer le filtre uniquement si la case est cochée
    if filter_active:
        if payee_filter == '1':
            factures = [f for f in factures if str(f['facture_payee']) in ['0', 'False', 'false']]

    return render_template('factures.html', factures=factures)

@app.route('/toggle_payee/<int:facture_id>', methods=['POST'])
def toggle_payee(facture_id):
    """ Met à jour l'état 'payée' d'une facture selon la case cochée """
    conn = sqlite3.connect('factures.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # L'état réel de la checkbox
    nouvelle_valeur = 1 if 'checkbox_paiement' in request.form else 0

    # Mise à jour dans la BDD
    c.execute(
        'UPDATE factures SET facture_payee = ? WHERE id = ? AND utilisateur_id = ?',
        (nouvelle_valeur, facture_id, session['utilisateur_id'])
    )
    conn.commit()
    conn.close()

    return redirect(url_for('afficher_factures'))


@app.route('/factures/json')
def factures_json():
    """ Route pour obtenir les factures en format JSON """
    conn = sqlite3.connect('factures.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM factures WHERE utilisateur_id = ?', (session['utilisateur_id'],))
    factures = c.fetchall()
    conn.close()
    return jsonify([{
        "id": f['id'], "fournisseur": f['fournisseur'], "date_facture": f['date_facture'], "numero_facture": f['numero_facture'],
        "montant_total": f['montant_total'], "TVA": f['TVA']
    } for f in factures])

@app.route('/factures/json/page')
def json_visuel():
    """ Route pour afficher les factures en format JSON dans une page dédiée """
    conn = sqlite3.connect('factures.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM factures WHERE utilisateur_id = ?', (session['utilisateur_id'],))
    factures = c.fetchall()
    conn.close()
    return render_template("factures_json.html", factures=[{
        "id": f['id'], "fournisseur": f['fournisseur'], "date_facture": f['date_facture'], "numero_facture": f['numero_facture'],
        "montant_total": f['montant_total'], "TVA": f['TVA']
    } for f in factures])

@app.route('/analyse', methods=['GET', 'POST'])
def analyse():
    """ Route pour analyser les factures """
    if request.method == 'POST' and request.form.get('action') == 'reset':
        return redirect('/analyse')
    conn = sqlite3.connect('factures.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    fournisseur = request.form.get('fournisseur')
    date_debut = request.form.get('date_debut')
    date_fin = request.form.get('date_fin')
    query = 'SELECT date_facture, montant_total, fournisseur FROM factures WHERE utilisateur_id = ?'
    params = [session['utilisateur_id']]

    if date_debut:
        query += ' AND date_facture >= ?'
        params.append(date_debut)
    if date_fin:
        query += ' AND date_facture <= ?'
        params.append(date_fin)
    if fournisseur and fournisseur != 'Tous':
        query += ' AND fournisseur = ?'
        params.append(fournisseur)

    c.execute(query, params)
    donnees = c.fetchall()

    dates, montants = [], []

    for date_facture, montant, _ in donnees:
        try:
            # Nettoyage : supprimer € ou autres caractères et convertir proprement
            montant_clean = str(montant).replace('€', '').replace(',', '.').strip()
            montant_float = float(montant_clean)
            dates.append(date_facture)
            montants.append(montant_float)
        except Exception as e:
            print(f"Erreur montant: {montant} → {e}")
            continue

    # Récupération de la date actuelle pour les KPI indépendants des filtres
    today = date.today()
    debut_annee = today.replace(month=1, day=1).isoformat()
    debut_mois = today.replace(day=1).isoformat()

    # Factures depuis le 1er janvier
    c.execute('''
        SELECT COUNT(*), SUM(REPLACE(montant_total, ",", "."))
        FROM factures
        WHERE utilisateur_id = ? AND date_facture >= ?
    ''', (session['utilisateur_id'], debut_annee))
    nb_annee, total_annee = c.fetchone()
    total_annee = float(total_annee or 0)

    # Factures depuis le 1er du mois
    c.execute('''
        SELECT COUNT(*), SUM(REPLACE(montant_total, ",", "."))
        FROM factures
        WHERE utilisateur_id = ? AND date_facture >= ?
    ''', (session['utilisateur_id'], debut_mois))
    nb_mois, total_mois = c.fetchone()
    total_mois = float(total_mois or 0)


    c.execute('SELECT DISTINCT fournisseur FROM factures WHERE utilisateur_id = ?', (session['utilisateur_id'],))
    fournisseurs = [row[0] for row in c.fetchall()]

    query_repart = 'SELECT fournisseur, SUM(REPLACE(montant_total, ",", ".")) FROM factures WHERE utilisateur_id = ?'
    params_repart = [session['utilisateur_id']]

    if date_debut:
        query_repart += ' AND date_facture >= ?'
        params_repart.append(date_debut)
    if date_fin:
        query_repart += ' AND date_facture <= ?'
        params_repart.append(date_fin)
    if fournisseur and fournisseur != 'Tous':
        query_repart += ' AND fournisseur = ?'
        params_repart.append(fournisseur)

    query_repart += ' GROUP BY fournisseur'
    c.execute(query_repart, params_repart)

    repartition = c.fetchall()

    # Toutes les factures impayées, triées par date d'échéance
    now = datetime.now().strftime("%Y-%m-%d")
    c.execute('''
        SELECT id, numero_facture, date_facture, echeance, fournisseur, montant_total, TVA
        FROM factures
        WHERE utilisateur_id = ? AND facture_payee = 0
        ORDER BY echeance ASC
    ''', (session['utilisateur_id'],))
    paiements_avenir = c.fetchall()


    # Cumul à l’échéance selon paiement -----------------------------------
    c.execute('''
    SELECT echeance, REPLACE(montant_total, ",", "."), facture_payee
    FROM factures
    WHERE utilisateur_id = ?
''', (session['utilisateur_id'],))
    factures_brutes = c.fetchall()

    factures_payees = []
    factures_impayees = []

    for echeance, montant_str, payee in factures_brutes:
        try:
            montant = float(str(montant_str).replace('€', '').replace(',', '.').strip())
            if payee == 1:
                factures_payees.append((echeance, montant))
            else:
                factures_impayees.append((echeance, montant))
        except Exception as e:
            print(f"Erreur montant: {montant_str} → {e}")
            continue

    # Trier chaque groupe par date
    factures_payees.sort(key=lambda x: datetime.strptime(x[0], "%Y-%m-%d"))
    factures_impayees.sort(key=lambda x: datetime.strptime(x[0], "%Y-%m-%d"))

    # Dates et cumul pour les payées
    dates_payees = []
    cumul_payees = []
    total_payees = 0
    for date_str, montant in factures_payees:
        total_payees += montant
        dates_payees.append(date_str)
        cumul_payees.append(total_payees)

    # Courbe prévisionnelle : commence à la dernière date payée avec valeur cumulée actuelle
    dates_impayees = []
    cumul_impayees = []

    if dates_payees:
        last_paid_date = dates_payees[-1]
        cumul_impayees.append(total_payees)
        dates_impayees.append(last_paid_date)

    for date_str, montant in factures_impayees:
        total_payees += montant
        dates_impayees.append(date_str)
        cumul_impayees.append(total_payees)

    # Fin ajout cumul échéance -----------------------------------

    conn.close()

    # Tri des dates et montants
    try:
        combined = sorted(zip(dates, montants), key=lambda x: datetime.strptime(x[0], "%Y-%m-%d"))
        dates, montants = zip(*combined) if combined else ([], [])
    except Exception as e:
        print(f"Erreur tri des dates : {e}")

    # Calcul du cumul
    montants_cumul = []
    total = 0
    for montant in montants:
        total += montant
        montants_cumul.append(total)

    return render_template('analyse.html',
        dates=dates,
        montants=montants,
        montants_cumul=montants_cumul,
        fournisseurs=fournisseurs,
        fournisseur_actuel=fournisseur,
        fournisseurs_repart=[r[0] for r in repartition],
        montants_fournisseurs=[float(r[1]) for r in repartition],
        date_debut=date_debut,
        date_fin=date_fin,
        total_annee=total_annee,
        nb_annee=nb_annee,
        total_mois=total_mois,
        nb_mois=nb_mois,
        today=today,
        paiements_avenir=paiements_avenir,
        dates_payees=dates_payees,
        cumul_payees=cumul_payees,
        dates_impayees=dates_impayees,
        cumul_impayees=cumul_impayees,
        now=now,
    )

@app.route('/export_csv', methods=['POST'])
def export_csv():
    """ Route pour exporter les factures filtrées en CSV """
    conn = sqlite3.connect('factures.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    fournisseur = request.form.get('fournisseur')
    date_debut = request.form.get('date_debut')
    date_fin = request.form.get('date_fin')

    query = 'SELECT * FROM factures WHERE utilisateur_id = ?'
    params = [session['utilisateur_id']]
    if date_debut:
        query += ' AND date_facture >= ?'
        params.append(date_debut)
    if date_fin:
        query += ' AND date_facture <= ?'
        params.append(date_fin)
    if fournisseur and fournisseur != 'Tous':
        query += ' AND fournisseur = ?'
        params.append(fournisseur)

    c.execute(query, params)
    factures = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Fournisseur', 'Date', 'Numéro', 'Montant', 'TVA'])
    writer.writerows(factures)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=factures_filtrees.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/supprimer/<int:id>', methods=['POST'])
def supprimer_facture(id):
    """ Route pour supprimer une facture spécifique """
    conn = sqlite3.connect('factures.db')
    c = conn.cursor()
    c.execute('DELETE FROM factures WHERE id = ? AND utilisateur_id = ?', (id, session['utilisateur_id']))
    conn.commit()
    conn.close()
    return redirect('/factures')

@app.route('/supprimer_tout', methods=['POST'])
def supprimer_tout():
    """ Route pour supprimer toutes les factures de l'utilisateur """
    conn = sqlite3.connect('factures.db')
    c = conn.cursor()
    c.execute('DELETE FROM factures WHERE utilisateur_id = ?', (session['utilisateur_id'],))
    conn.commit()
    conn.close()
    return redirect('/factures')

from flask import send_from_directory

@app.route('/uploads/<path:filename>')
def telecharger_fichier(filename):
    """ Route pour télécharger un fichier spécifique depuis le dossier d'uploads """
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.context_processor
def injecter_pseudo():
    """ Route pour afficher le pseudo de l'utilisateur dans les templates """
    return {"pseudo": session.get("pseudo")}

def ocr_core(fichier):
    """ Fonction pour effectuer l'OCR sur une image ou un PDF """
    return pytesseract.image_to_string(Image.open(fichier))

def extraire_infos(texte):
    """ Fonction pour extraire les informations d'une facture à partir du texte OCR """
    date = re.search(r'(\d{2}/\d{2}/\d{4})', texte)
    numero = re.search(r'(?:Facture|N\u00b0|No|Num\u00e9ro)[^\d]*(\d+)', texte, re.I)
    montant = re.search(r'(\d+[.,]\d{2}) ?(?:\u20ac|EUR)', texte)
    tva = re.search(r'TVA[^\d]*(\d+[.,]\d{2})', texte, re.I)
    fournisseur = texte.strip().split('\n')[0]
    return {
        "fournisseur": fournisseur if fournisseur else "Non trouv\u00e9",
        "date_facture": date.group(1) if date else "Non trouv\u00e9e",
        "numero_facture": numero.group(1) if numero else "Non trouv\u00e9",
        "montant_total": montant.group(1) if montant else "Non trouv\u00e9",
        "TVA": tva.group(1) if tva else "Non trouv\u00e9e"
    }

if __name__ == "__main__":
    """ Point d'entrée de l'application Flask """
    import webbrowser
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    init_db()
    webbrowser.open('http://127.0.0.1:5000/login')
    app.run(debug=True)
