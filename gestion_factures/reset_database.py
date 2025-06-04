import sqlite3
import os

DB_NAME = "factures.db"

def reset_database():
    # Supprimer l'ancienne base si elle existe
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"🧹 Ancienne base de données '{DB_NAME}' supprimée.")

    # Recréer la base
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Table utilisateurs
    c.execute('''
        CREATE TABLE utilisateurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT,
            prenom TEXT,
            age INTEGER,
            secteur TEXT,
            email TEXT UNIQUE,
            pseudo TEXT UNIQUE,
            mot_de_passe TEXT
        )
    ''')

    # Table factures
    c.execute('''
        CREATE TABLE factures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fournisseur TEXT,
            date_facture TEXT,
            numero_facture TEXT,
            montant_total TEXT,
            TVA TEXT,
            utilisateur_id INTEGER,
            nom_fichier TEXT,
            facture_payee INTEGER DEFAULT 0,
            numero_client TEXT,
            echeance TEXT,
            somme_finale TEXT,
            FOREIGN KEY (utilisateur_id) REFERENCES utilisateurs(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Nouvelle base de données créée avec succès.")

if __name__ == "__main__":
    reset_database()
