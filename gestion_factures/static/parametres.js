// Ajout dynamique de lignes dans le formulaire d'ajout

const tbodyForm = document.querySelector('#categories-table tbody');
const btnSave = document.getElementById('save-categories-btn');

// Fonction pour créer une ligne de formulaire catégorie
function createCategoryRow(nom = '', couleur = '') {
  const tr = document.createElement('tr');

  // Col input nom
  const tdNom = document.createElement('td');
  const inputNom = document.createElement('input');
  inputNom.type = 'text';
  inputNom.classList.add('category-input');
  inputNom.placeholder = 'Nom de la catégorie';
  inputNom.maxLength = 50;
  inputNom.value = nom;
  tdNom.appendChild(inputNom);
  tr.appendChild(tdNom);

  // Col aperçu
  const tdPreview = document.createElement('td');
  const preview = document.createElement('div');
  preview.classList.add('category-preview');
  tdPreview.appendChild(preview);
  tr.appendChild(tdPreview);

  // Col select couleur
  const tdColor = document.createElement('td');
  const select = document.createElement('select');
  select.classList.add('color-select');

  const colors = [
    { val: '', label: 'Choisir une couleur' },
    { val: 'red', label: 'Rouge' },
    { val: 'blue', label: 'Bleu' },
    { val: 'green', label: 'Vert' },
    { val: 'orange', label: 'Orange' },
    { val: 'purple', label: 'Violet' },
    { val: 'brown', label: 'Marron' },
    { val: 'pink', label: 'Rose' },
    { val: 'yellow', label: 'Jaune' },
    { val: 'cyan', label: 'Cyan' },
    { val: 'black', label: 'Noir' }
  ];

  colors.forEach(c => {
    const option = document.createElement('option');
    option.value = c.val;
    option.textContent = c.label;
    if (c.val === couleur) option.selected = true;
    select.appendChild(option);
  });

  tdColor.appendChild(select);
  tr.appendChild(tdColor);

  // Event pour mise à jour aperçu
  function majPreview() {
    const nomVal = inputNom.value.trim();
    const couleurVal = select.value;

    if (nomVal && couleurVal) {
      preview.style.backgroundColor = couleurVal;
      preview.textContent = nomVal;
      preview.style.color = ['yellow', 'cyan', 'pink'].includes(couleurVal) ? 'black' : 'white';
      preview.style.padding = '5px 10px';
      preview.style.borderRadius = '4px';
      preview.style.fontWeight = 'bold';
      preview.style.display = 'inline-block';
    } else {
      preview.style.backgroundColor = 'transparent';
      preview.textContent = '';
      preview.style.padding = '';
      preview.style.borderRadius = '';
      preview.style.fontWeight = '';
      preview.style.display = 'none';
    }
  }

  inputNom.addEventListener('input', majPreview);
  select.addEventListener('change', majPreview);

  // Initial preview
  majPreview();

  return tr;
}

// Bouton pour ajouter une nouvelle ligne (en haut ou en bas de la table)
const addRowBtn = document.createElement('button');
addRowBtn.type = 'button';
addRowBtn.textContent = '+ Ajouter une catégorie';
addRowBtn.style.margin = '10px 0';
addRowBtn.addEventListener('click', () => {
  tbodyForm.appendChild(createCategoryRow());
});
document.querySelector('#categories-table').parentNode.insertBefore(addRowBtn, document.querySelector('#categories-table'));

// Au chargement, si tbody vide, ajoute une ligne vide
if (tbodyForm.children.length === 0) {
  tbodyForm.appendChild(createCategoryRow());
}

btnSave.addEventListener('click', () => {
  const categories = [];

  // 1. Récupère l'encart du haut
  const newNom = document.getElementById('new-category-name').value.trim();
  const newCouleur = document.getElementById('new-category-color').value;

  if (newNom || newCouleur) {
    if (!newNom) {
      alert('Le nom de la catégorie est obligatoire.');
      return;
    }
    if (!newCouleur) {
      alert('La couleur est obligatoire.');
      return;
    }
    categories.push({ nom: newNom, couleur: newCouleur });
  }

  // 2. (Optionnel) On pourrait aussi lire les lignes du tableau ici si tu veux.

  if (categories.length === 0) {
    alert('Veuillez remplir une catégorie et une couleur.');
    return;
  }

  // 3. Envoi vers Flask
  fetch('/parametres', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(categories)
  })
    .then(async response => {
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Erreur serveur');
      }
      return response.json();
    })
    .then(data => {
      alert(data.message || 'Catégorie enregistrée avec succès.');
      // On vide les champs après enregistrement
      document.getElementById('new-category-name').value = '';
      document.getElementById('new-category-color').value = '';
      window.location.reload();
    })
    .catch(err => {
      alert('Erreur lors de l\'enregistrement : ' + err.message);
    });
});