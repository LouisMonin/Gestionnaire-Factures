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

""" Configuration de l'application Flask """

app = Flask(__name__)
app.secret_key = 'ma_clé_secrète'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

""" Initialisation de la base de données """

@app.before_request
def verifier_connexion():
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
        if 'facture' not in request.files:
            flash("❌ Aucun fichier sélectionné.", "error")
            return redirect(url_for('upload'))

        fichier = request.files['facture']
        if fichier.filename == '':
            flash("❌ Fichier vide.", "error")
            return redirect(url_for('upload'))

        extension = fichier.filename.split('.')[-1].lower()
        chemin_fichier = os.path.join(app.config['UPLOAD_FOLDER'], fichier.filename)
        fichier.save(chemin_fichier)

        try:
            # ✅ Pour images PNG/JPG/JPEG
            if extension in ['png', 'jpg', 'jpeg']:
                texte = ocr_core(chemin_fichier)
                donnees = extraire_infos(texte)
                insert_facture(
                    donnees["fournisseur"],
                    donnees["date_facture"],
                    donnees["numero_facture"],
                    donnees["montant_total"],
                    donnees["TVA"],
                    session['utilisateur_id']
                )
                flash("✅ Facture image enregistrée avec succès !", "success")

            # ✅ Pour PDF
            elif extension == 'pdf':
                from pdf2image import convert_from_path
                pages = convert_from_path(chemin_fichier, 300)
                texte = ""
                for page in pages:
                    texte += pytesseract.image_to_string(page)
                donnees = extraire_infos(texte)
                insert_facture(
                    donnees["fournisseur"],
                    donnees["date_facture"],
                    donnees["numero_facture"],
                    donnees["montant_total"],
                    donnees["TVA"],
                    session['utilisateur_id']
                )
                flash("✅ Facture PDF enregistrée avec succès !", "success")

            # ✅ Pour Excel XLSX/XLS avec plusieurs lignes
            elif extension in ['xlsx', 'xls']:
                import pandas as pd
                df = pd.read_excel(chemin_fichier)

                if df.empty:
                    flash("❌ Fichier Excel vide ou mal formaté.", "error")
                    return redirect(url_for('upload'))

                lignes_inserees = 0
                for _, row in df.iterrows():
                    donnees = {
                        "fournisseur": str(row.get("Fournisseur", "Non trouvé")),
                        "date_facture": str(row.get("Date", "Non trouvée")),
                        "numero_facture": str(row.get("Numéro de facture", "Non trouvé")),
                        "montant_total": str(row.get("Montant TTC", "Non trouvé")),
                        "TVA": str(row.get("TVA", "Non trouvée"))
                    }

                    insert_facture(
                        donnees["fournisseur"],
                        donnees["date_facture"],
                        donnees["numero_facture"],
                        donnees["montant_total"],
                        donnees["TVA"],
                        session['utilisateur_id']
                    )
                    lignes_inserees += 1

                flash(f"✅ {lignes_inserees} facture(s) Excel enregistrée(s) avec succès !", "success")

            else:
                flash("❌ Format non supporté. Utilisez : PNG, JPG, PDF ou Excel.", "error")
                return redirect(url_for('upload'))

            return redirect(url_for('accueil'))

        except Exception as e:
            flash(f"❌ Erreur lors du traitement : {str(e)}", "error")
            return redirect(url_for('upload'))

    return render_template('upload.html')

@app.route('/factures')
def afficher_factures():
    """ Route pour afficher les factures de l'utilisateur """
    conn = sqlite3.connect('factures.db')
    c = conn.cursor()
    c.execute('SELECT * FROM factures WHERE utilisateur_id = ?', (session['utilisateur_id'],))
    factures = c.fetchall()
    conn.close()
    return render_template('factures.html', factures=factures)

@app.route('/factures/json')
def factures_json():
    """ Route pour obtenir les factures en format JSON """
    conn = sqlite3.connect('factures.db')
    c = conn.cursor()
    c.execute('SELECT * FROM factures WHERE utilisateur_id = ?', (session['utilisateur_id'],))
    factures = c.fetchall()
    conn.close()
    return jsonify([{
        "id": f[0], "fournisseur": f[1], "date_facture": f[2], "numero_facture": f[3],
        "montant_total": f[4], "TVA": f[5]
    } for f in factures])

@app.route('/factures/json/page')
def json_visuel():
    """ Route pour afficher les factures en format JSON dans une page dédiée """
    conn = sqlite3.connect('factures.db')
    c = conn.cursor()
    c.execute('SELECT * FROM factures WHERE utilisateur_id = ?', (session['utilisateur_id'],))
    factures = c.fetchall()
    conn.close()
    return render_template("factures_json.html", factures=[{
        "id": f[0], "fournisseur": f[1], "date_facture": f[2], "numero_facture": f[3],
        "montant_total": f[4], "TVA": f[5]
    } for f in factures])

@app.route('/analyse', methods=['GET', 'POST'])
def analyse():
    """ Route pour analyser les factures """
    if request.method == 'POST' and request.form.get('action') == 'reset':
        return redirect('/analyse')
    conn = sqlite3.connect('factures.db')
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
    for date, montant, _ in donnees:
        try:
            # Nettoyage : supprimer € ou autres caractères et convertir proprement
            montant_clean = str(montant).replace('€', '').replace(',', '.').strip()
            montant_float = float(montant_clean)
            dates.append(date)
            montants.append(montant_float)
        except Exception as e:
            print(f"Erreur montant: {montant} → {e}")
            continue


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
    conn.close()

    return render_template('analyse.html',
                           dates=dates,
                           montants=montants,
                           fournisseurs=fournisseurs,
                           fournisseur_actuel=fournisseur,
                           fournisseurs_repart=[r[0] for r in repartition],
                           montants_fournisseurs=[float(r[1]) for r in repartition],
                           date_debut=date_debut,
                           date_fin=date_fin)

@app.route('/export_csv', methods=['POST'])
def export_csv():
    """ Route pour exporter les factures filtrées en CSV """
    conn = sqlite3.connect('factures.db')
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
