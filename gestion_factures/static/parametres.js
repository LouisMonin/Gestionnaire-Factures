console.log("parametres.js chargé");

document.addEventListener('DOMContentLoaded', function () {
  const rows = document.querySelectorAll('#categories-table tbody tr');

  rows.forEach(row => {
    const input = row.querySelector('.category-input');
    const preview = row.querySelector('.category-preview');
    const colorSelect = row.querySelector('.color-select');

    input.addEventListener('input', function () {
      preview.textContent = this.value;
    });

    colorSelect.addEventListener('change', function () {
      const color = this.value;
      preview.style.backgroundColor = color;

      // Contraste automatique
      preview.style.color = ['yellow', 'pink', 'white'].includes(color) ? 'black' : 'white';
    });
  });

  // Bouton enregistrer
  document.getElementById('save-categories-btn').addEventListener('click', function () {
    const categories_personnalisees = [];

    rows.forEach(row => {
      const input = row.querySelector('.category-input');
      const color = row.querySelector('.color-select').value;
      const name = input.value.trim();

      if (name) {
        categories_personnalisees.push({ nom: name, couleur: color });
      }
    });

    console.log("Catégories enregistrées :", categories_personnalisees);
  });
});
