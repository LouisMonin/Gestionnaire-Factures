import sqlite3

def init_db():
    conn = sqlite3.connect('factures.db')
    c = conn.cursor()

    # Table utilisateurs
    c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        prenom TEXT,
        age INTEGER,
        secteur TEXT,
        email TEXT UNIQUE,
        pseudo TEXT UNIQUE,
        mot_de_passe TEXT
    )''')

    # Table factures enrichie
    c.execute('''CREATE TABLE IF NOT EXISTS factures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fournisseur TEXT,
        date_facture TEXT,
        numero_facture TEXT,
        montant_total TEXT,
        TVA TEXT,
        utilisateur_id INTEGER,
        nom_fichier TEXT,
        facture_payee INTEGER,
        numero_client TEXT,
        echeance TEXT,
        somme_finale TEXT,
        categorie TEXT DEFAULT 'Non-catégorisée',
        FOREIGN KEY (utilisateur_id) REFERENCES utilisateurs(id)
    )''')

    # Migration pour ajouter la colonne categorie si elle n'existe pas déjà
    try:
        c.execute('ALTER TABLE factures ADD COLUMN categorie TEXT DEFAULT "Non-catégorisée"')
        print("✅ Colonne 'categorie' ajoutée à la table factures")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️ Colonne 'categorie' déjà présente dans la table factures")
        else:
            print(f"❌ Erreur lors de l'ajout de la colonne categorie : {e}")

    conn.commit()
    conn.close()

# Fonction pour insérer une facture dans la base de données
def insert_facture(
    fournisseur,
    date_facture,
    numero_facture,
    montant_total,
    tva,
    utilisateur_id,
    nom_fichier,
    facture_payee,
    numero_client,
    echeance,
    somme_finale,
    categorie="Non-catégorisée"
):
    conn = sqlite3.connect('factures.db')
    c = conn.cursor()

    c.execute('''
        INSERT INTO factures (
            fournisseur,
            date_facture,
            numero_facture,
            montant_total,
            TVA,
            utilisateur_id,
            nom_fichier,
            facture_payee,
            numero_client,
            echeance,
            somme_finale,
            categorie
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        fournisseur,
        date_facture,
        numero_facture,
        montant_total,
        tva,
        utilisateur_id,
        nom_fichier,
        facture_payee,
        numero_client,
        echeance,
        somme_finale,
        categorie
    ))

    conn.commit()
    conn.close()

def ajouter_utilisateur(nom, prenom, age, secteur, email, pseudo, mot_de_passe):
    conn = sqlite3.connect('factures.db')
    c = conn.cursor()
    c.execute("SELECT * FROM utilisateurs WHERE email = ?", (email,))
    if c.fetchone():
        conn.close()
        return False
    c.execute('''
        INSERT INTO utilisateurs (nom, prenom, age, secteur, email, pseudo, mot_de_passe)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nom, prenom, age, secteur, email, pseudo, mot_de_passe))
    conn.commit()
    conn.close()
    return True

def verifier_utilisateur(pseudo, mot_de_passe):
    conn = sqlite3.connect('factures.db')
    c = conn.cursor()
    c.execute('SELECT * FROM utilisateurs WHERE pseudo = ? AND mot_de_passe = ?', (pseudo, mot_de_passe))
    utilisateur = c.fetchone()
    conn.close()
    return utilisateur