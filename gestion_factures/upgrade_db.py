import sqlite3

conn = sqlite3.connect("factures.db")
c = conn.cursor()

def colonne_existe(nom_colonne):
    c.execute("PRAGMA table_info(factures)")
    return nom_colonne in [col[1] for col in c.fetchall()]

colonnes_a_ajouter = {
    "nom_fichier": "TEXT",
    "facture_payee": "INTEGER DEFAULT 0",
    "numero_client": "TEXT",
    "echeance": "TEXT",
    "somme_finale": "TEXT"
}

for col, typ in colonnes_a_ajouter.items():
    if not colonne_existe(col):
        print(f"Ajout de la colonne : {col}")
        c.execute(f"ALTER TABLE factures ADD COLUMN {col} {typ}")

conn.commit()
conn.close()
print("✅ Mise à jour terminée.")
