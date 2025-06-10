import sqlite3

conn = sqlite3.connect('factures.db')
c = conn.cursor()

# Ajouter la colonne si elle n'existe pas
try:
    c.execute("ALTER TABLE factures ADD COLUMN total_ht TEXT;")
    print("✅ Colonne 'categorie' ajoutée.")
except sqlite3.OperationalError:
    print("ℹ️ La colonne 'categorie' existe déjà.")

conn.commit()
conn.close()
