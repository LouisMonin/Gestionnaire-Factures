"""
# gestion_factures/app.py
# Application Flask pour la gestion des factures
# Ce script permet aux utilisateurs de télécharger, analyser et gérer leurs factures.
# Il inclut des fonctionnalités de connexion, d'inscription, de téléchargement de fichiers, d'analyse OCR et de visualisation des factures.
# Il utilise SQLite pour stocker les données des factures et des utilisateurs.
# Il est conçu pour être simple et extensible, avec une interface utilisateur basique en HTML.
# Il nécessite les bibliothèques Flask, SQLite, pytesseract, PIL (Pillow), pdf2image et pandas.
# """

from flask import Flask, jsonify, render_template, request, redirect, flash, url_for, session, make_response, send_from_directory
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
from datetime import datetime,date
from collections import defaultdict
import calendar
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
    """Route principale de l'application : page d'accueil avec KPI si connecté"""
    if 'utilisateur_id' not in session:
        return redirect(url_for('login'))

    utilisateur_id = session['utilisateur_id']
    conn = sqlite3.connect('factures.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Dates utiles
    today = date.today()
    debut_annee = today.replace(month=1, day=1).isoformat()
    debut_mois = today.replace(day=1).isoformat()

    # KPI 1 : Total montant année + mois
    c.execute("""
        SELECT SUM(REPLACE(montant_total, ',', '.')) FROM factures
        WHERE utilisateur_id = ? AND date_facture >= ?
    """, (utilisateur_id, debut_annee))
    total_annee = float(c.fetchone()[0] or 0)

    c.execute("""
        SELECT SUM(REPLACE(montant_total, ',', '.')) FROM factures
        WHERE utilisateur_id = ? AND date_facture >= ?
    """, (utilisateur_id, debut_mois))
    total_mois = float(c.fetchone()[0] or 0)

    # KPI 2 : Nombre de factures année + mois
    c.execute("""
        SELECT COUNT(*) FROM factures
        WHERE utilisateur_id = ? AND date_facture >= ?
    """, (utilisateur_id, debut_annee))
    nb_annee = c.fetchone()[0]

    c.execute("""
        SELECT COUNT(*) FROM factures
        WHERE utilisateur_id = ? AND date_facture >= ?
    """, (utilisateur_id, debut_mois))
    nb_mois = c.fetchone()[0]

    # KPI 3 : Factures non payées (en retard / à venir)
    now_iso = today.isoformat()

    c.execute("""
        SELECT id FROM factures
        WHERE utilisateur_id = ? AND facture_payee = 0 AND echeance < ?
    """, (utilisateur_id, now_iso))
    factures_en_retard = c.fetchall()

    c.execute("""
        SELECT id FROM factures
        WHERE utilisateur_id = ? AND facture_payee = 0 AND echeance >= ?
    """, (utilisateur_id, now_iso))
    factures_a_venir = c.fetchall()

    conn.close()

    return render_template('index.html',
        total_annee=total_annee,
        total_mois=total_mois,
        nb_annee=nb_annee,
        nb_mois=nb_mois,
        factures_en_retard=factures_en_retard,
        factures_a_venir=factures_a_venir
    )




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

""" Partie upload des factures """

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        fichier = request.files.get('facture')
        if fichier and fichier.filename:
            nom_fichier = fichier.filename
            chemin_fichier = os.path.join(app.config['UPLOAD_FOLDER'], nom_fichier)

            # Crée le dossier s'il n'existe pas
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

        # Récupération de la catégorie depuis le formulaire
        categorie = request.form.get("categorie", "Non-catégorisée")

        # Récupération de l'état de paiement depuis la checkbox
        facture_payee = 1 if request.form.get("payee") == "1" else 0

        # Appel de la fonction insert_facture avec tous les paramètres, y compris la catégorie
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
            total_ht,
            categorie  # Ajout du paramètre catégorie
        )

        flash("Facture enregistrée avec succès.", "success")
        return redirect(url_for('accueil'))

    return render_template('upload.html')

""" Routes pour l'analyse des factures via OCR pour PDF """

@app.route('/analyse_pdf', methods=['POST'])
def analyse_pdf():
    """ Analyse un fichier PDF envoyé via JavaScript et retourne les données extraites """
    fichier = request.files.get('facture_pdf')
    if not fichier:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    try:
        chemin_temp = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_facture.pdf')
        fichier.save(chemin_temp)

        images = convert_from_path(chemin_temp, dpi=300)
        texte = ""
        for image in images:
            texte += pytesseract.image_to_string(image)

        infos = extraire_infos(texte)
        return jsonify(infos)
    except Exception as e:
        print(f"Erreur d'analyse PDF : {e}")
        return jsonify({"error": "Erreur lors de l'analyse PDF"}), 500

""" Routes pour l'analyse des factures via OCR pour image (PNG/JPG/JPEG) """

@app.route('/analyse_image', methods=['POST'])
def analyse_image():
    """ Analyse une image de facture PNG/JPG/JPEG et retourne les données extraites """
    fichier = request.files.get('facture_image')
    if not fichier:
        return jsonify({"error": "Aucun fichier image reçu"}), 400

    try:
        chemin_temp = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_image_facture.png')
        fichier.save(chemin_temp)

        image = Image.open(chemin_temp)
        texte = pytesseract.image_to_string(image)
        infos = extraire_infos(texte)
        return jsonify(infos)

    except Exception as e:
        print(f"Erreur /analyse_image : {e}")
        return jsonify({"error": "Erreur lors de l'analyse de l'image"}), 500

""" Fonction pour extraire les informations d'une facture à partir du texte OCR """

def extraire_infos(texte):
    import re
    from datetime import datetime

    def clean_num(s):
        return re.sub(r"[^\d,.\-]", "", s).replace(",", ".").strip()

    def extract_date(text):
        match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', text)
        if match:
            d, m, y = match.group(1).split('/')
            y = '20' + y if len(y) == 2 else y
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        return ""

    def extract_first_matching(label_keywords, lines, as_date=False):
        for line in lines:
            for keyword in label_keywords:
                if keyword.lower() in line.lower():
                    if as_date:
                        return extract_date(line)
                    else:
                        match = re.search(r'[:\-]?\s*([€\d][\d\s,.]*)', line)
                        if match:
                            return clean_num(match.group(1))
        return ""

    lines = [l.strip() for l in texte.split('\n') if l.strip()]

    return {
        "fournisseur": next((l for l in lines if "nom entreprise" in l.lower()), lines[0]),
        "numero_facture": extract_first_matching(["numéro de facture", "n° de facture"], lines),
        "date_facture": extract_first_matching(["date de facture"], lines, as_date=True),
        "echeance": extract_first_matching(["échéance de paiement", "échéance"], lines, as_date=True),
        "total_ht1": extract_first_matching(["sous-total", "total ht", "prix total ht"], lines),
        "TVA": extract_first_matching(["tva", "taux de tva"], lines),
        "montant_total": extract_first_matching(["total ttc"], lines),
        "total_ht": extract_first_matching(["total ht"], lines)
    }

def get_categories():
    conn = sqlite3.connect('categories.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT nom_categorie, couleur FROM categories")
    categories = cursor.fetchall()
    conn.close()
    return categories

@app.route('/factures')
def afficher_factures():
    """ Route pour afficher les factures de l'utilisateur """
    conn = sqlite3.connect('factures.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM factures WHERE utilisateur_id = ?', (session['utilisateur_id'],))
    factures = c.fetchall()
    conn.close()
    categories = get_categories()

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


# Route pour afficher les factures en format JSON
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
        "fournisseur": f['fournisseur'], "date_facture": f['date_facture'], "echeance": f['echeance'], "TVA": f['TVA'], "montant_total": f['montant_total']
    } for f in factures])


# Route pour afficher les factures en format JSON dans une page dédiée
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
        "fournisseur": f['fournisseur'], "date_facture": f['date_facture'], "echeance": f['echeance'], "TVA": f['TVA'], "montant_total": f['montant_total']
    } for f in factures])

# Route pour analyser les factures
@app.route('/analyse', methods=['GET', 'POST'])
def analyse():
    """ Route pour analyser les factures """

    # Réinitialisation des filtres si demandé
    if request.method == 'POST' and request.form.get('action') == 'reset':
        return redirect('/analyse')

    # Connexion DB avec noms colonnes
    conn = sqlite3.connect('factures.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Lecture des filtres : fournisseur, dates, champ date sur lequel filtrer
    fournisseur = request.values.get('fournisseur')
    date_debut = request.values.get('date_debut')
    date_fin = request.values.get('date_fin')
    filtre_date = request.values.get('filtre_date') or 'date_facture'
    utilisateur_id = session['utilisateur_id']

    # Requête principale des factures filtrées selon utilisateur et filtres
    query = f"SELECT {filtre_date} as date_val, montant_total, fournisseur FROM factures WHERE utilisateur_id = ?"
    params = [utilisateur_id]

    if date_debut:
        query += f" AND {filtre_date} >= ?"
        params.append(date_debut)
    if date_fin:
        query += f" AND {filtre_date} <= ?"
        params.append(date_fin)
    if fournisseur and fournisseur.lower() != 'tous':
        query += " AND LOWER(fournisseur) = LOWER(?)"
        params.append(fournisseur)

    c.execute(query, params)
    donnees = c.fetchall()

    # Extraction dates et montants nettoyés (conversion string -> float)
    dates = [row['date_val'] for row in donnees]
    montants = []
    for row in donnees:
        try:
            montants.append(float(row['montant_total'].replace(',', '.')))
        except Exception:
            montants.append(0)

    # Dates utiles pour KPI (annuel et mensuel)
    today = date.today()
    debut_annee = today.replace(month=1, day=1).isoformat()
    debut_mois = today.replace(day=1).isoformat()

    # KPI annuels et mensuels (sans filtres, car ce sont des globales)
    c.execute("""
        SELECT COUNT(*), SUM(REPLACE(montant_total, ',', '.'))
        FROM factures
        WHERE utilisateur_id = ? AND date_facture >= ?
    """, (utilisateur_id, debut_annee))
    nb_annee, total_annee = c.fetchone()
    total_annee = float(total_annee or 0)

    c.execute("""
        SELECT COUNT(*), SUM(REPLACE(montant_total, ',', '.'))
        FROM factures
        WHERE utilisateur_id = ? AND date_facture >= ?
    """, (utilisateur_id, debut_mois))
    nb_mois, total_mois = c.fetchone()
    total_mois = float(total_mois or 0)

    # Liste des fournisseurs (pour filtre)
    c.execute("SELECT DISTINCT fournisseur FROM factures WHERE utilisateur_id = ?", (utilisateur_id,))
    fournisseurs = [row[0] for row in c.fetchall()]

    # Répartition des montants payés par catégorie (avec filtres appliqués)
    query_repart = """
        SELECT categorie, SUM(REPLACE(montant_total, ',', '.'))
        FROM factures
        WHERE utilisateur_id = ?
    """
    params_repart = [utilisateur_id]

    if date_debut:
        query_repart += f" AND {filtre_date} >= ?"
        params_repart.append(date_debut)
    if date_fin:
        query_repart += f" AND {filtre_date} <= ?"
        params_repart.append(date_fin)
    if fournisseur and fournisseur.lower() != 'tous':
        query_repart += " AND LOWER(fournisseur) = LOWER(?)"
        params_repart.append(fournisseur)

    query_repart += " GROUP BY categorie"


    c.execute(query_repart, params_repart)
    repartition = c.fetchall()

    # Factures non payées : en retard et à venir (sans filtre sur dates/fournisseurs)
    now_iso = today.isoformat()
    c.execute("""
        SELECT id, numero_facture, date_facture, echeance, fournisseur, montant_total, TVA
        FROM factures
        WHERE utilisateur_id = ? AND facture_payee = 0 AND echeance < ?
        ORDER BY echeance ASC
    """, (utilisateur_id, now_iso))
    factures_en_retard = c.fetchall()

    c.execute("""
        SELECT id, numero_facture, date_facture, echeance, fournisseur, montant_total, TVA
        FROM factures
        WHERE utilisateur_id = ? AND facture_payee = 0 AND echeance >= ?
        ORDER BY echeance ASC
    """, (utilisateur_id, now_iso))
    factures_a_venir = c.fetchall()

    paiements_avenir = factures_en_retard + factures_a_venir

    # Conversion de la date échéance en string pour l'affichage
    for f in paiements_avenir:
        echeance = f['echeance']
        if not isinstance(echeance, str):
            f['echeance'] = echeance.isoformat() if hasattr(echeance, 'isoformat') else str(echeance)

    # Cumul des montants par échéance, séparés payés / impayés (avec filtres)
    query_cumul = """
        SELECT echeance, REPLACE(montant_total, ',', '.'), facture_payee
        FROM factures
        WHERE utilisateur_id = ?
    """
    params_cumul = [utilisateur_id]
    if date_debut:
        query_cumul += " AND echeance >= ?"
        params_cumul.append(date_debut)
    if date_fin:
        query_cumul += " AND echeance <= ?"
        params_cumul.append(date_fin)
    if fournisseur and fournisseur.lower() != 'tous':
        query_cumul += " AND LOWER(fournisseur) = LOWER(?)"
        params_cumul.append(fournisseur)

    c.execute(query_cumul, params_cumul)
    factures_cumul = c.fetchall()

    factures_payees = []
    factures_impayees = []

    for echeance, montant_str, payee in factures_cumul:
        montant = float(montant_str)
        if payee == 1:
            factures_payees.append((echeance, montant))
        else:
            factures_impayees.append((echeance, montant))

    # Trie et cumul des montants par date d'échéance
    all_dates = sorted(set([f[0] for f in factures_payees + factures_impayees]), key=lambda d: datetime.strptime(d, "%Y-%m-%d"))
    cumul_payees_dict = defaultdict(float)
    cumul_impayees_dict = defaultdict(float)

    for d, m in factures_payees:
        cumul_payees_dict[d] += m
    for d, m in factures_impayees:
        cumul_impayees_dict[d] += m

    labels, cumul_payees, cumul_impayees = [], [], []
    total_payees, total_impayees = 0, 0

    for d in all_dates:
        labels.append(d)
        total_payees += cumul_payees_dict[d]
        total_impayees += cumul_impayees_dict[d]
        cumul_payees.append(round(total_payees, 2))
        cumul_impayees.append(round(total_payees + total_impayees, 2))

    # Tri des dates/montants pour graphique d’évolution (filtrés)
    try:
        combined = sorted(zip(dates, montants), key=lambda x: datetime.strptime(x[0], "%Y-%m-%d"))
        dates, montants = zip(*combined) if combined else ([], [])
    except Exception as e:
        print(f"Erreur tri des dates : {e}")

    # Calcul cumulatif montant total (évolution)
    montants_cumul = []
    total = 0
    for m in montants:
        total += m
        montants_cumul.append(total)


    # HISTOGRAMME : répartition des montants par catégorie

    # Récupération des factures payées (avec filtres)
    query_histogramme = """
        SELECT date_facture, montant_total, categorie
        FROM factures
        WHERE utilisateur_id = ?
    """
    params_histogramme = [utilisateur_id]

    if date_debut:
        query_histogramme += f" AND {filtre_date} >= ?"
        params_histogramme.append(date_debut)
    if date_fin:
        query_histogramme += f" AND {filtre_date} <= ?"
        params_histogramme.append(date_fin)
    if fournisseur and fournisseur.lower() != 'tous':
        query_histogramme += " AND LOWER(fournisseur) = LOWER(?)"
        params_histogramme.append(fournisseur)

    c.execute(query_histogramme, params_histogramme)
    factures_payees = c.fetchall()


    # === Nouveau graphique : Top 3 fournisseurs par catégorie ===
    query_top_fournisseurs = """
        SELECT categorie, fournisseur, SUM(REPLACE(montant_total, ',', '.')) AS total
        FROM factures
        WHERE utilisateur_id = ?
    """
    params_top = [utilisateur_id]

    if date_debut:
        query_top_fournisseurs += f" AND {filtre_date} >= ?"
        params_top.append(date_debut)
    if date_fin:
        query_top_fournisseurs += f" AND {filtre_date} <= ?"
        params_top.append(date_fin)
    if fournisseur and fournisseur.lower() != 'tous':
        query_top_fournisseurs += " AND LOWER(fournisseur) = LOWER(?)"
        params_top.append(fournisseur)

    query_top_fournisseurs += """
        GROUP BY categorie, fournisseur
        ORDER BY categorie, total DESC
    """

    c.execute(query_top_fournisseurs, params_top)
    top_fournisseurs_raw = c.fetchall()


    conn.close()

    # Regrouper par mois et catégorie
    data_mensuelle = defaultdict(lambda: defaultdict(float))

    for f in factures_payees:
        date_str = f["date_facture"]
        try:
            date_f = datetime.strptime(date_str, "%Y-%m-%d")  # ou adapte le format
            mois = date_f.strftime("%Y-%m")
        except Exception as e:
            print(f"Erreur conversion date_facture : {e}")
            continue
        categorie = f["categorie"] if "categorie" in f.keys() else "Autre"
        data_mensuelle[mois][categorie] += float(f["montant_total"])

    # Organiser les données pour Chart.js
    mois_tries = sorted(data_mensuelle.keys())
    categories_uniques = sorted({cat for mois in data_mensuelle.values() for cat in mois})

    # Création des datasets
    stacked_data = []
    for cat in categories_uniques:
        values = [data_mensuelle[mois].get(cat, 0) for mois in mois_tries]
        stacked_data.append({
            "label": cat,
            "data": values
        })

    # Calculs pour le graphiques top 3 fournisseurs par catégorie


    # Étape 1 : construire top_data avec tri des 3 premiers fournisseurs par montant décroissant
    top_data = defaultdict(list)

    for row in top_fournisseurs_raw:
        cat = row['categorie'] or 'Autre'
        frs = row['fournisseur']
        montant = float(row['total'])
        top_data[cat].append((frs, montant))

    # Étape 2 : ne garder que le top 3 trié pour chaque catégorie
    for cat in top_data:
        top_data[cat] = sorted(top_data[cat], key=lambda x: x[1], reverse=True)[:3]

    # Étape 3 : récupérer tous les fournisseurs top par ordre décroissant par catégorie
    categories_top = sorted(top_data.keys())
    fournisseurs_uniques = []

    for cat in categories_top:
        for frs, _ in top_data[cat]:
            if frs not in fournisseurs_uniques:
                fournisseurs_uniques.append(frs)

    # Étape 4 : construire les datasets dans l’ordre des fournisseurs triés
    dataset_top_fournisseurs = []
    for frs in fournisseurs_uniques:
        data = []
        for cat in categories_top:
            montant = next((m for f, m in top_data[cat] if f == frs), 0)
            data.append(montant)
        dataset_top_fournisseurs.append({
            "label": frs,
            "data": data
        })

    # Rendu template avec toutes les données
    return render_template('analyse.html',
        dates=dates,
        montants=montants,
        montants_cumul=montants_cumul,
        fournisseurs=fournisseurs,
        fournisseur_actuel=fournisseur,
        categories_repart=[r[0] for r in repartition],
        montants_categories=[float(r[1]) for r in repartition],
        date_debut=date_debut,
        date_fin=date_fin,
        filtre_date=filtre_date,
        total_annee=total_annee,
        nb_annee=nb_annee,
        total_mois=total_mois,
        nb_mois=nb_mois,
        today=today,
        paiements_avenir=paiements_avenir,
        factures_en_retard=factures_en_retard,
        factures_a_venir=factures_a_venir,
        now=now_iso,
        labels=labels,
        cumul_payees=cumul_payees,
        cumul_impayees=cumul_impayees,
        labels_mois=mois_tries,
        stacked_datasets=stacked_data,
        categories_top=categories_top,
        dataset_top_fournisseurs=dataset_top_fournisseurs,
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

@app.route('/uploads/<path:filename>')
def telecharger_fichier(filename):
    """ Route pour télécharger un fichier spécifique depuis le dossier d'uploads """
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.context_processor
def injecter_pseudo():
    """ Route pour afficher le pseudo de l'utilisateur dans les templates """
    return {"pseudo": session.get("pseudo")}


def get_categories_db():
    conn = sqlite3.connect('categories.db')
    conn.row_factory = sqlite3.Row
    return conn



@app.route('/parametres', methods=['GET', 'POST'])
def parametres():
    if request.method == 'POST':
        data = request.get_json()
        print("DEBUG data reçue:", data)  # debug data reçue
        utilisateur_id = session.get('utilisateur_id')
        if not utilisateur_id:
            return jsonify({"message": "Utilisateur non connecté"}), 401

        if not data:
            return jsonify({"message": "Aucune donnée reçue ou JSON malformé"}), 400

        try:
            conn = get_categories_db()
            c = conn.cursor()
            #c.execute('DELETE FROM categories WHERE utilisateur_id = ?', (utilisateur_id,))

            for cat in data:
                nom = cat.get('nom')
                couleur = cat.get('couleur')
                if nom and couleur:
                    c.execute('INSERT INTO categories (utilisateur_id, nom_categorie, couleur) VALUES (?, ?, ?)',
                              (utilisateur_id, nom, couleur))

            conn.commit()
            conn.close()
            return jsonify({"message": "Catégories enregistrées avec succès"}), 200
        except Exception as e:
            print("Erreur lors de l'enregistrement des catégories:",e)
            return jsonify({"message": "Erreur serveur lors de l'enregistrement"}), 500

    return render_template('parametres.html')



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
