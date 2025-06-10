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
from collections import defaultdict

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
    if request.method == 'POST':
        fichier = request.files.get('facture')
        if fichier and fichier.filename:
            nom_fichier = fichier.filename
            chemin_fichier = os.path.join(app.config['UPLOAD_FOLDER'], nom_fichier)

            # Crée le dossier s’il n’existe pas
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

            try:
                fichier.save(chemin_fichier)
                print("✅ Fichier sauvegardé :", chemin_fichier)
            except Exception as e:
                print("❌ Erreur lors de la sauvegarde :", e)
                flash("❌ Erreur lors de la sauvegarde du fichier.", "error")
                return redirect(url_for('upload'))
        else:
            flash("❌ Aucun fichier sélectionné.", "error")
            return redirect(url_for('upload'))

        # Puis traite les champs extraits du formulaire
        nom_entreprise = request.form.get("nom_entreprise")
        numero_client = request.form.get("numero_client")
        numero_facture = request.form.get("numero_facture")
        date_facture = request.form.get("date_facture")
        echeance = request.form.get("echeance")
        total_ht = request.form.get("total_ht")
        tva = request.form.get("tva")
        total_ttc = request.form.get("total_ttc")
        somme_finale = request.form.get("somme_finale")
        facture_payee = 0

        insert_facture(
            nom_entreprise,
            date_facture,
            numero_facture,
            total_ttc,
            tva,
            session['utilisateur_id'],
            nom_fichier,
            facture_payee,
            numero_client,
            echeance,
            somme_finale
        )

        flash("✅ Facture enregistrée avec succès.", "success")
        return redirect(url_for('accueil'))

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

    # Catégories de factures
    categories = ["Non-catégorisée", "Électricité", "Eau", "Internet", "Téléphone", "Assurance", "Autre"]



    return render_template('factures.html', factures=factures, categories=categories)

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

@app.route('/modifier_categorie/<int:facture_id>', methods=['POST'])
def modifier_categorie(facture_id):
    nouvelle_categorie = request.form.get('categorie')
    conn = sqlite3.connect('factures.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('UPDATE factures SET categorie = ? WHERE id = ? AND utilisateur_id = ?', (nouvelle_categorie, facture_id, session['utilisateur_id']))

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

    # Toutes les factures impayées, triées par date d'échéance -----------------
    now = date.today().isoformat()

    # Factures impayées en retard (date échéance < today)
    c.execute('''
        SELECT id, numero_facture, date_facture, echeance, fournisseur, montant_total, TVA
        FROM factures
        WHERE utilisateur_id = ? AND facture_payee = 0 AND echeance < ?
        ORDER BY echeance ASC
    ''', (session['utilisateur_id'], today))
    factures_en_retard = c.fetchall()

    # Factures impayées à venir (date échéance >= today)
    c.execute('''
        SELECT id, numero_facture, date_facture, echeance, fournisseur, montant_total, TVA
        FROM factures
        WHERE utilisateur_id = ? AND facture_payee = 0 AND echeance >= ?
        ORDER BY echeance ASC
    ''', (session['utilisateur_id'], now))
    factures_a_venir = c.fetchall()

    # Concaténation des listes pour afficher dans le même tableau, triées par date d'échéance
    paiements_avenir = factures_en_retard + factures_a_venir

    # Conversion des dates en string ISO (par sécurité)
    for f in paiements_avenir:
        if not isinstance(f['echeance'], str):
            f['echeance'] = f['echeance'].isoformat() if hasattr(f['echeance'], 'isoformat') else str(f['echeance'])


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

    # --- Construction d'une timeline unique triée ---
    all_dates = set([f[0] for f in factures_payees + factures_impayees])
    all_dates = sorted(all_dates, key=lambda d: datetime.strptime(d, "%Y-%m-%d"))

    # Dictionnaires pour regrouper les montants par date
    cumul_payees_dict = defaultdict(float)
    cumul_impayees_dict = defaultdict(float)

    for date_str, montant in factures_payees:
        cumul_payees_dict[date_str] += montant

    for date_str, montant in factures_impayees:
        cumul_impayees_dict[date_str] += montant

    # Courbes cumulées sur une même ligne de temps
    labels = []
    cumul_payees = []
    cumul_impayees = []

    total_payees = 0
    total_impayees = 0

    for date_str in all_dates:
        labels.append(date_str)
        total_payees += cumul_payees_dict[date_str]
        total_impayees += cumul_impayees_dict[date_str]
        cumul_payees.append(round(total_payees, 2))
        cumul_impayees.append(round(total_payees + total_impayees, 2))  # global avec impayés


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
        factures_en_retard=factures_en_retard,
        factures_a_venir=factures_a_venir,
        now=now,
        labels=labels,
        cumul_payees=cumul_payees,
        cumul_impayees=cumul_impayees,
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
    import webbrowser
    # 🛠️ Création sécurisée du dossier uploads si manquant
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'])
            print(f"📂 Dossier uploads créé dans : {app.config['UPLOAD_FOLDER']}")
        except Exception as e:
            print(f"❌ Impossible de créer le dossier uploads : {e}")
    else:
        print(f"📁 Dossier uploads déjà présent : {app.config['UPLOAD_FOLDER']}")

    init_db()
    webbrowser.open('http://127.0.0.1:5000/login')
    app.run(debug=True, use_reloader=False)
