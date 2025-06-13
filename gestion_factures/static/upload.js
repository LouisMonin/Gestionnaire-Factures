// Écouteur principal : quand l'utilisateur sélectionne un fichier
document.getElementById('facture').addEventListener('change', function () {
  const file = this.files[0]; // Récupère le fichier importé
  const form = document.getElementById('facture-formulaire'); // Le formulaire de saisie
  const preview = document.getElementById('preview'); // Zone d'aperçu du fichier

  // Nettoyage des affichages précédents
  preview.innerHTML = '';
  preview.style.display = 'none';
  form.style.display = 'none';

  if (!file) return; // Si aucun fichier sélectionné, on arrête là

  const extension = file.name.split('.').pop().toLowerCase(); // Extension du fichier

  // ===========================
  // CAS PDF
  // ===========================
  if (extension === 'pdf') {
    const formData = new FormData();
    formData.append('facture_pdf', file); // Envoie du fichier PDF au backend

    fetch('/analyse_pdf', {
      method: 'POST',
      body: formData
    })
    .then(r => r.json())
    .then(data => {
      // Remplissage automatique des champs du formulaire
      document.getElementById("nom_entreprise").value = data.fournisseur || '';
      document.getElementById("numero_facture").value = data.numero_facture || '';
      document.getElementById("date_facture").value = data.date_facture || '';
      document.getElementById("echeance").value = data.echeance || '';
      document.getElementById("total_ht").value = data.total_ht || '';
      document.getElementById("tva").value = data.TVA || '';
      document.getElementById("total_ttc").value = data.montant_total || '';
      document.getElementById("nom_fichier").value = file.name;

      form.style.display = 'block'; // Affiche le formulaire avec les champs remplis

      // Affiche le PDF dans un <iframe>
      const url = URL.createObjectURL(file);
      preview.innerHTML = `
        <iframe
          src="${url}"
          style="width: 100%; height: 85vh; border: none; box-shadow: 0 0 10px rgba(0,0,0,0.1); border-radius: 12px;">
        </iframe>`;
      preview.style.display = 'block';
    })
    .catch(err => {
      console.error('Erreur PDF:', err); // Affiche l'erreur en console
      alert("❌ Erreur lors de l'analyse du fichier PDF."); // Alerte utilisateur
    });

    return; // On arrête l'exécution ici pour ne pas analyser comme Excel/image
  }

  // ===========================
  // CAS IMAGE
  // ===========================
  if (['png', 'jpg', 'jpeg'].includes(extension)) {
    const formData = new FormData();
    formData.append('facture_image', file); // Envoie du fichier image au backend

    fetch('/analyse_image', {
      method: 'POST',
      body: formData
    })
    .then(r => r.json())
    .then(data => {
      // Remplissage des champs à partir des données OCR
      document.getElementById("nom_entreprise").value = data.fournisseur || '';
      document.getElementById("numero_facture").value = data.numero_facture || '';
      document.getElementById("date_facture").value = data.date_facture || '';
      document.getElementById("echeance").value = data.echeance || '';
      document.getElementById("total_ht").value = data.total_ht || '';
      document.getElementById("tva").value = data.TVA || '';
      document.getElementById("total_ttc").value = data.montant_total || '';
      document.getElementById("nom_fichier").value = file.name;

      form.style.display = 'block'; // Affiche le formulaire

      // Affiche l'image sélectionnée
      const url = URL.createObjectURL(file);
      preview.innerHTML = `
        <img src="${url}" style="width: 100%; max-height: 85vh; object-fit: contain; border-radius: 12px; box-shadow: 0 0 10px rgba(0,0,0,0.1);" />
      `;
      preview.style.display = 'block';
    })
    .catch(err => {
      console.error('Erreur image :', err); // Erreur technique en console
      alert("❌ Erreur lors de l'analyse du fichier image."); // Alerte utilisateur
    });

    return;
  }


  // ===========================
  // CAS EXCEL ou CSV
  // ===========================
  const reader = new FileReader();

  reader.onload = function (e) {
    // Lecture du fichier Excel avec SheetJS
    const data = new Uint8Array(e.target.result);
    const workbook = XLSX.read(data, { type: 'array' });
    const sheet = workbook.Sheets[workbook.SheetNames[0]];
    const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, raw: false });

    // Affiche un tableau HTML dans la preview
    let table = '<table>';
    rows.forEach(row => {
      table += '<tr>' + row.map(cell => `<td>${cell || ''}</td>`).join('') + '</tr>';
    });
    table += '</table>';
    preview.innerHTML = table;
    preview.style.display = 'block';

    // Fonctions utilitaires pour extraire et nettoyer les champs
    const normalize = str => (str || '').toString().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]/gi, '').toLowerCase();
    const cleanValue = val => (val || '').replace(/[^\d.,]/g, '').replace(',', '.').trim();

    // Transforme le tableau en dictionnaire clé-valeur (clé = étiquette détectée)
    const flatMap = {};
    rows.forEach(row => {
      for (let i = 0; i < row.length; i++) {
        const current = String(row[i] || '').trim();
        const keyNorm = normalize(current);

        // Cas où la valeur est dans la même cellule (ex: "Total HT : 123.45")
        if (current.includes(':')) {
          const [keyRaw, ...rest] = current.split(':');
          const key = normalize(keyRaw);
          let val = rest.join(':').trim();
          if (!val) {
            for (let j = i + 1; j < row.length; j++) {
              if (String(row[j]).trim()) {
                val = String(row[j]).trim();
                break;
              }
            }
          }
          flatMap[key] = val;

        // Cas où la clé est suivie d'une valeur dans la cellule suivante
        } else if (keyNorm && row[i + 1]) {
          const val = String(row[i + 1]).trim();
          if (val) flatMap[keyNorm] = val;
        }
      }
    });

    // Fonction de recherche de valeur en fonction de synonymes possibles
    const findValue = (labels) => {
      for (let key in flatMap) {
        for (let label of labels) {
          if (key.includes(normalize(label))) return flatMap[key];
        }
      }
      return '';
    };

    // Conversion de date Excel ou texte → format ISO (aaaa-mm-jj)
    const formatDate = value => {
      const num = parseFloat(value);
      if (!isNaN(num) && num > 40000) {
        const date = new Date((num - 25569) * 86400 * 1000);
        return date.toISOString().split('T')[0];
      }
      const tryDate = new Date(value);
      if (!isNaN(tryDate)) return tryDate.toISOString().split('T')[0];
      if (typeof value === 'string' && value.match(/\d{1,2}\/\d{1,2}\/\d{2,4}/)) {
        const [d, m, y] = value.split('/');
        return `${y.length === 2 ? '20' + y : y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`;
      }
      return '';
    };

    // Détection automatique d'une catégorie selon les mots-clés
    const detectCategory = () => {
      const nomEntreprise = findValue(["nom entreprise", "nomentreprise"]).toLowerCase();
      const allText = rows.flat().join(' ').toLowerCase();

      if (nomEntreprise.includes('edf') || nomEntreprise.includes('engie') || nomEntreprise.includes('électricité') || allText.includes('électricité')) return 'Électricité';
      if (nomEntreprise.includes('veolia') || nomEntreprise.includes('suez') || nomEntreprise.includes('eau') || allText.includes('eau')) return 'Eau';
      if (nomEntreprise.includes('orange') || nomEntreprise.includes('internet') || allText.includes('internet')) return 'Internet';
      if (nomEntreprise.includes('téléphone') || allText.includes('mobile')) return 'Téléphone';
      if (nomEntreprise.includes('assurance') || allText.includes('assurance')) return 'Assurance';
      return 'Non-catégorisée';
    };

    // Remplit le formulaire avec les valeurs extraites
    document.getElementById("nom_entreprise").value = findValue(["nom entreprise", "nomentreprise"]);
    document.getElementById("date_facture").value = formatDate(findValue(["date de facture", "datedefacture"]));
    document.getElementById("echeance").value = formatDate(findValue(["echeance", "echeance de paiement"]));
    document.getElementById("total_ht").value = cleanValue(findValue(["sous total", "sous-total", "soustotal", "total ht", "totalht", "ht"]));
    document.getElementById("tva").value = cleanValue(findValue(["taux de tva", "tauxtva", "tva"]));
    document.getElementById("total_ttc").value = cleanValue(findValue(["total ttc", "totalttc"]));
    document.getElementById("nom_fichier").value = file.name;
    document.getElementById("categorie").value = detectCategory();

    // Fallback : si certains champs n'ont pas été trouvés, recherche dans les cellules HTML
    const fallbackFromDOM = (label, fieldId) => {
      if (!document.getElementById(fieldId).value) {
        const cells = [...document.querySelectorAll('#preview td')];
        for (let i = 0; i < cells.length; i++) {
          const text = cells[i].textContent.toLowerCase().trim();
          if (text.includes(label.toLowerCase())) {
            for (let j = 1; j <= 5; j++) {
              const nextCell = cells[i + j];
              if (nextCell) {
                const val = nextCell.textContent.trim().replace(/[^\d.,]/g, '').replace(',', '.');
                if (val) {
                  document.getElementById(fieldId).value = val;
                  return;
                }
              }
            }
          }
        }
      }
    };

    fallbackFromDOM("sous-total", "total_ht");
    fallbackFromDOM("taux de tva", "tva");
    fallbackFromDOM("total ttc", "total_ttc");

    form.style.display = 'block'; // Affiche le formulaire une fois rempli
  };

  reader.readAsArrayBuffer(file); // Lance la lecture du fichier Excel/CSV
});

// ✅ Validation des champs numériques
['total_ht', 'tva', 'total_ttc'].forEach(id => {
  const el = document.getElementById(id);

  const errorMsg = document.createElement('div');
  errorMsg.style.color = 'red';
  errorMsg.style.fontSize = '0.8em';
  errorMsg.style.display = 'none';
  errorMsg.textContent = '❌ Chiffres et un seul point uniquement';
  el.parentNode.appendChild(errorMsg);

  el.addEventListener('input', () => {
    let value = el.value;
    value = value.replace(/[^0-9.]/g, '');
    const parts = value.split('.');
    if (parts.length > 2) {
      value = parts[0] + '.' + parts.slice(1).join('').replace(/\./g, '');
    }

    if (el.value !== value) {
      el.style.backgroundColor = '#ffdddd';
      errorMsg.style.display = 'block';
    } else {
      el.style.backgroundColor = '';
      errorMsg.style.display = 'none';
    }

    el.value = value;
  });
});

// ✅ Validation des dates
function validateDates() {
  const dateFactureEl = document.getElementById('date_facture');
  const dateEcheanceEl = document.getElementById('echeance');
  const today = new Date();
  let valid = true;

  const factureDate = dateFactureEl.value ? new Date(dateFactureEl.value) : null;
  const echeanceDate = dateEcheanceEl.value ? new Date(dateEcheanceEl.value) : null;

  if (factureDate && factureDate > today) {
    dateFactureEl.style.backgroundColor = '#ffdddd';
    showDateError(dateFactureEl, '❌ La date de facture ne peut pas être dans le futur');
    valid = false;
  } else {
    dateFactureEl.style.backgroundColor = '';
    hideDateError(dateFactureEl);
  }

  if (factureDate && echeanceDate && echeanceDate < factureDate) {
    dateEcheanceEl.style.backgroundColor = '#ffdddd';
    showDateError(dateEcheanceEl, '❌ L\'échéance doit être postérieure ou égale à la date de facture');
    valid = false;
  } else {
    dateEcheanceEl.style.backgroundColor = '';
    hideDateError(dateEcheanceEl);
  }

  return valid;
}





function validateMontants() {
  const ht = parseFloat(document.getElementById('total_ht').value);
  const ttc = parseFloat(document.getElementById('total_ttc').value);

  const elHT = document.getElementById('total_ht');
  const elTTC = document.getElementById('total_ttc');

  let error = elHT.parentNode.querySelector('.montant-error');
  if (!error) {
    error = document.createElement('div');
    error.className = 'montant-error';
    error.style.color = 'red';
    error.style.fontSize = '0.8em';
    elTTC.parentNode.appendChild(error);
  }

  if (!isNaN(ht) && !isNaN(ttc) && ht > ttc) {
    elHT.style.backgroundColor = '#ffdddd';
    elTTC.style.backgroundColor = '#ffdddd';
    error.textContent = '❌ Le montant HT doit être inférieur ou égal au montant TTC';
    error.style.display = 'block';
    return false;
  } else {
    elHT.style.backgroundColor = '';
    elTTC.style.backgroundColor = '';
    error.style.display = 'none';
    return true;
  }
}


function showDateError(element, message) {
  let errorMsg = element.parentNode.querySelector('.date-error');
  if (!errorMsg) {
    errorMsg = document.createElement('div');
    errorMsg.className = 'date-error';
    errorMsg.style.color = 'red';
    errorMsg.style.fontSize = '0.8em';
    element.parentNode.appendChild(errorMsg);
  }
  errorMsg.textContent = message;
  errorMsg.style.display = 'block';
}

function hideDateError(element) {
  const errorMsg = element.parentNode.querySelector('.date-error');
  if (errorMsg) {
    errorMsg.style.display = 'none';
  }
}

document.getElementById('date_facture').addEventListener('change', validateDates);
document.getElementById('echeance').addEventListener('change', validateDates);
document.getElementById('total_ht').addEventListener('input', validateMontants);
document.getElementById('total_ttc').addEventListener('input', validateMontants);

document.getElementById('facture-formulaire').addEventListener('submit', function (e) {
  const validDates = validateDates();
  const validMontants = validateMontants();

  const champsObligatoires = ['nom_entreprise', 'date_facture', 'echeance', 'total_ttc', 'tva', 'total_ht'];
  let champsOk = true;

  champsObligatoires.forEach(id => {
    const el = document.getElementById(id);
    if (!el.value) {
      el.style.backgroundColor = '#ffdddd';
      champsOk = false;

      let error = el.parentNode.querySelector('.champ-error');
      if (!error) {
        error = document.createElement('div');
        error.className = 'champ-error';
        error.style.color = 'red';
        error.style.fontSize = '0.8em';
        error.textContent = '❌ Ce champ est obligatoire';
        el.parentNode.appendChild(error);
      } else {
        error.style.display = 'block';
      }
    } else {
      el.style.backgroundColor = '';
      const error = el.parentNode.querySelector('.champ-error');
      if (error) error.style.display = 'none';
    }
  });

  if (!validDates || !validMontants || !champsOk) {
    e.preventDefault();
    alert("⚠️ Veuillez corriger les erreurs avant de soumettre le formulaire.");
  }
});



document.getElementById('facture').addEventListener('change', function () {
      const file = this.files[0];
      if (!file) return;

      if (file.type === 'application/pdf') {
        const formData = new FormData();
        formData.append('facture_pdf', file);

        fetch('/analyse_pdf', {
          method: 'POST',
          body: formData
        })
        .then(r => r.json())
        .then(data => {
          document.getElementById("nom_entreprise").value = data.fournisseur || '';
          document.getElementById("date_facture").value = data.date_facture || '';
          document.getElementById("numero_facture").value = data.numero_facture || '';
          document.getElementById("total_ttc").value = data.montant_total || '';
          document.getElementById("tva").value = data.TVA || '';
          document.getElementById("nom_fichier").value = file.name;
          document.getElementById("facture-formulaire").style.display = 'block';
        })
        .catch(err => console.error('Erreur PDF:', err));
      }
    });