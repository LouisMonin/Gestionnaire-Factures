// Envoi au serveur
document.getElementById('save-categories-btn').addEventListener('click', () => {
  const categories = [];

  // 1. Lire la catégorie dans l'encart du haut
  const nomHaut = document.getElementById('new-category-name').value.trim();
  const couleurHaut = document.getElementById('new-category-color').value.trim();

  if (nomHaut || couleurHaut) {
    if (!nomHaut) {
      alert("Le nom de la catégorie (en haut) est obligatoire.");
      return;
    }
    if (!couleurHaut) {
      alert("La couleur de la catégorie (en haut) est obligatoire.");
      return;
    }
    categories.push({ nom: nomHaut, couleur: couleurHaut });
  }

  // 2. Lire les lignes dynamiques du tableau
  const rows = document.querySelectorAll('#categories-table tbody tr');

  rows.forEach(row => {
    const nom = row.querySelector('.category-input')?.value.trim();
    const couleur = row.querySelector('.color-select')?.value.trim();

    if (nom && couleur) {
      categories.push({ nom, couleur });
    }
  });

  // 3. Valider s’il y a bien des données à envoyer
  if (categories.length === 0) {
    alert("Veuillez saisir au moins une catégorie avec une couleur.");
    return;
  }

  // 4. Envoi au backend Flask
  fetch('/parametres', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(categories)
  })
    .then(async response => {
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || "Erreur serveur");
      }
      return response.json();
    })
    .then(data => {
      alert(data.message || "Catégories enregistrées avec succès.");
      // Optionnel : reset le formulaire haut
      document.getElementById('new-category-name').value = '';
      document.getElementById('new-category-color').value = '';
      window.location.reload();
    })
    .catch(err => {
      alert("Erreur réseau ou serveur lors de l'enregistrement : " + err.message);
    });
});
