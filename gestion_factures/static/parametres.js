console.log("parametres.js chargé");


document.addEventListener('DOMContentLoaded', function () {
  const input = document.getElementById('new_category1');
  const preview = document.getElementById('cat1_preview');

  if (input && preview) {
    input.addEventListener('input', function () {
      preview.textContent = this.value;
    });
  }

    // Change le fond de la cellule quand une couleur est choisie
if (colorSelect && preview) {
    colorSelect.addEventListener('change', function () {
        preview.style.backgroundColor = this.value;
        preview.style.color = ['yellow', 'pink'].includes(this.value) ? 'black' : 'white'; // contraste lisible
        preview.style.padding = '4px';
        preview.style.borderRadius = '4px';
    });
}
});