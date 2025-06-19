// Dynamique : couleur et texte
document.querySelectorAll('#categories-table tbody tr').forEach(row => {
  const inputNom = row.querySelector('.category-input');
  const selectCouleur = row.querySelector('.color-select');
  const preview = row.querySelector('.category-preview');
  const table = document.getElementById('categories-list');


  function majPreview() {
    const nom = inputNom.value.trim();
    const couleur = selectCouleur.value;

    if (nom && couleur) {
      preview.style.backgroundColor = couleur;
      preview.textContent = nom;
      preview.style.color = 'white'; // ou noir selon la couleur, simple fix
      preview.style.padding = '5px';
      preview.style.borderRadius = '3px';
      preview.style.fontWeight = 'bold';
    } else {
      preview.style.backgroundColor = 'transparent';
      preview.textContent = '';
      preview.style.padding = '';
      preview.style.borderRadius = '';
      preview.style.fontWeight = '';
    }
  }

  inputNom.addEventListener('input', majPreview);
  selectCouleur.addEventListener('change', majPreview);
});

// Envoi au serveur
document.getElementById('save-categories-btn').addEventListener('click', () => {
  const rows = document.querySelectorAll('#categories-table tbody tr');
  const categories = [];

  rows.forEach(row => {
    const nom = row.querySelector('.category-input').value.trim();
    const couleur = row.querySelector('.color-select').value.trim();

    if (nom && couleur) {
      categories.push({ nom, couleur });
    }
  });

  if (categories.length === 0) {
    alert("Veuillez saisir au moins une catégorie avec une couleur.");
    return;
  }

  fetch('/parametres', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(categories)
  })
  .then(async response => {
    if (!response.ok) {
      // Affiche le message d'erreur côté serveur si possible
      const error = await response.json().catch(() => ({}));
      throw new Error(error.message || "Erreur serveur");
    }
    return response.json();
  })
  .then(data => {
    alert(data.message || "Catégories enregistrées avec succès.");
    window.location.reload();
  })
  .catch(err => {
    alert("Erreur réseau ou serveur lors de l'enregistrement : " + err.message);
  });
});
