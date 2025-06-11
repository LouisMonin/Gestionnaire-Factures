document.getElementById('facture').addEventListener('change', function () {
  const file = this.files[0];
  const preview = document.getElementById('preview');
  const form = document.getElementById('facture-formulaire');

  preview.innerHTML = '';
  form.style.display = 'none';
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function (e) {
    const data = new Uint8Array(e.target.result);
    const workbook = XLSX.read(data, { type: 'array' });
    const sheet = workbook.Sheets[workbook.SheetNames[0]];
    const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, raw: false });

    // Affichage tableau
    let table = '<table>';
    rows.forEach(row => {
      table += '<tr>' + row.map(cell => `<td>${cell || ''}</td>`).join('') + '</tr>';
    });
    table += '</table>';
    preview.innerHTML = table;
    preview.style.display = 'block';

    const normalize = str => (str || '').toString().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]/gi, '').toLowerCase();
    const cleanValue = val => (val || '').replace(/[^\d.,]/g, '').replace(',', '.').trim();

    const flatMap = {};
    rows.forEach(row => {
      for (let i = 0; i < row.length; i++) {
        const current = String(row[i] || '').trim();
        const keyNorm = normalize(current);

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
        } else if (keyNorm && row[i + 1]) {
          const val = String(row[i + 1]).trim();
          if (val) flatMap[keyNorm] = val;
        }
      }
    });

    const findValue = (labels) => {
      for (let key in flatMap) {
        for (let label of labels) {
          if (key.includes(normalize(label))) return flatMap[key];
        }
      }
      return '';
    };

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

    // Détection automatique de la catégorie basée sur le nom de l'entreprise ou du contenu
    const detectCategory = () => {
      const nomEntreprise = findValue(["nom entreprise", "nomentreprise"]).toLowerCase();
      const allText = rows.flat().join(' ').toLowerCase();

      if (nomEntreprise.includes('edf') || nomEntreprise.includes('engie') || nomEntreprise.includes('électricité') ||
          allText.includes('électricité') || allText.includes('kwh') || allText.includes('consommation électrique')) {
        return 'Électricité';
      }
      if (nomEntreprise.includes('veolia') || nomEntreprise.includes('suez') || nomEntreprise.includes('eau') ||
          allText.includes('eau') || allText.includes('m3') || allText.includes('consommation eau')) {
        return 'Eau';
      }
      if (nomEntreprise.includes('orange') || nomEntreprise.includes('sfr') || nomEntreprise.includes('bouygues') ||
          nomEntreprise.includes('free') || nomEntreprise.includes('internet') || nomEntreprise.includes('box') ||
          allText.includes('internet') || allText.includes('adsl') || allText.includes('fibre')) {
        return 'Internet';
      }
      if (nomEntreprise.includes('téléphone') || nomEntreprise.includes('mobile') ||
          allText.includes('téléphone') || allText.includes('mobile') || allText.includes('forfait')) {
        return 'Téléphone';
      }
      if (nomEntreprise.includes('assurance') || nomEntreprise.includes('axa') || nomEntreprise.includes('maif') ||
          nomEntreprise.includes('macif') || allText.includes('assurance') || allText.includes('prime')) {
        return 'Assurance';
      }
      return 'Non-catégorisée';
    };

    // Remplissage automatique des champs
    document.getElementById("nom_entreprise").value = findValue(["nom entreprise", "nomentreprise"]);
    document.getElementById("date_facture").value = formatDate(findValue(["date de facture", "datedefacture"]));
    document.getElementById("echeance").value = formatDate(findValue(["echeance", "echeance de paiement"]));
    document.getElementById("total_ht").value = cleanValue(findValue(["sous total", "sous-total", "soustotal", "total ht", "totalht", "ht"]));
    document.getElementById("tva").value = cleanValue(findValue(["taux de tva", "tauxtva", "tva"]));
    document.getElementById("total_ttc").value = cleanValue(findValue(["total ttc", "totalttc"]));
    document.getElementById("nom_fichier").value = file.name;

    // Détection automatique de la catégorie
    document.getElementById("categorie").value = detectCategory();

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

    form.style.display = 'block';
  };

  reader.readAsArrayBuffer(file);
});

// Validation des champs numériques
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

// Validation des dates
function validateDates() {
  const dateFacture = document.getElementById('date_facture');
  const dateEcheance = document.getElementById('echeance');
  const today = new Date().toISOString().split('T')[0];

  // Validation date de facture (ne peut pas être dans le futur)
  if (dateFacture.value && dateFacture.value > today) {
    dateFacture.style.backgroundColor = '#ffdddd';
    showDateError(dateFacture, '❌ La date doit être antérieure ou égale à aujourd\'hui');
    return false;
  } else {
    dateFacture.style.backgroundColor = '';
    hideDateError(dateFacture);
  }

  // Validation date d'échéance (ne peut pas être avant la date de facture)
  if (dateFacture.value && dateEcheance.value && dateEcheance.value < dateFacture.value) {
    dateEcheance.style.backgroundColor = '#ffdddd';
    showDateError(dateEcheance, '❌ La date d\'échéance doit être postérieur à la date de facture');
    return false;
  } else {
    dateEcheance.style.backgroundColor = '';
    hideDateError(dateEcheance);
  }

  return true;
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

// Ajouter les événements de validation sur les champs de date
document.getElementById('date_facture').addEventListener('change', validateDates);
document.getElementById('echeance').addEventListener('change', validateDates);