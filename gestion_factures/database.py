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

    # Table factures avec utilisateur_id
    c.execute('''CREATE TABLE IF NOT EXISTS factures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fournisseur TEXT,
        date_facture TEXT,
        numero_facture TEXT,
        montant_total TEXT,
        TVA TEXT,
        utilisateur_id INTEGER,
        FOREIGN KEY (utilisateur_id) REFERENCES utilisateurs(id)
    )''')

    conn.commit()
    conn.close()

def insert_facture(fournisseur, date_facture, numero_facture, montant_total, tva, utilisateur_id):
    conn = sqlite3.connect('factures.db')
    c = conn.cursor()
    c.execute('''INSERT INTO factures (fournisseur, date_facture, numero_facture, montant_total, TVA, utilisateur_id)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (fournisseur, date_facture, numero_facture, montant_total, tva, utilisateur_id))
    conn.commit()
    conn.close()

def ajouter_utilisateur(nom, prenom, age, secteur, email, pseudo, mot_de_passe):
    conn = sqlite3.connect('factures.db')
    c = conn.cursor()
    
    # Vérifie si l'email est déjà utilisé
    c.execute("SELECT * FROM utilisateurs WHERE email = ?", (email,))
    if c.fetchone():
        conn.close()
        return False  # Signal d'erreur

    # Insertion normale si email unique
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