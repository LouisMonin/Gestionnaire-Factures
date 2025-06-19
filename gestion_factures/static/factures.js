document.addEventListener('DOMContentLoaded', function () {
  const table = document.getElementById('table-factures');
  const paidFilter = document.getElementById('filter-paid');
  const textFilters = document.querySelectorAll('.filter-input');
  const toggleBtn = document.getElementById('toggle-filters-btn');
  const resetBtn = document.getElementById('reset-filters-btn');
  const filterGroups = document.querySelectorAll('.filter-group');

  const rowsPerPage = 10;
  let currentPage = 1;

  const noResultRow = document.createElement('tr');
  const td = document.createElement('td');
  td.colSpan = table.rows[0].cells.length;
  td.style.textAlign = 'center';
  td.textContent = 'Aucune facture';
  noResultRow.appendChild(td);
  noResultRow.style.display = 'none';
  table.tBodies[0].appendChild(noResultRow);

  const paginationControls = document.getElementById('pagination-controls');
  const prevBtn = document.getElementById('prevPage');
  const nextBtn = document.getElementById('nextPage');
  const pageInfo = document.getElementById('pageInfo');

  function getFilteredRows() {
    const allRows = Array.from(table.tBodies[0].rows).filter(r => r !== noResultRow);
    return allRows.filter(row => {
      let visible = true;

      // Filtres texte et select
      textFilters.forEach(input => {
        const col = parseInt(input.dataset.col);
        const cell = row.cells[col];
        let cellText = '';

        const select = cell.querySelector('select');
        if (select) {
          cellText = select.value.toLowerCase();
        } else {
          cellText = cell.textContent.toLowerCase();
        }

        if (input.value && !cellText.includes(input.value.toLowerCase())) {
          visible = false;
        }
      });

      // Filtre Payée
      const checkbox = row.cells[8]?.querySelector('input[type="checkbox"]');
      if (checkbox) {
        const estPayee = checkbox.checked;
        if (paidFilter.value === 'payee' && !estPayee) visible = false;
        if (paidFilter.value === 'impayee' && estPayee) visible = false;
      }

      return visible;
    });
  }

  function renderPagination(filteredRows) {
    const totalPages = Math.ceil(filteredRows.length / rowsPerPage);
    if (currentPage > totalPages) currentPage = totalPages || 1;

    filteredRows.forEach((row, i) => {
      row.style.display = (i >= (currentPage - 1) * rowsPerPage && i < currentPage * rowsPerPage) ? '' : 'none';
    });

    // Cache tous les autres
    Array.from(table.tBodies[0].rows).forEach(row => {
      if (!filteredRows.includes(row) && row !== noResultRow) row.style.display = 'none';
    });

    noResultRow.style.display = filteredRows.length === 0 ? '' : 'none';
    pageInfo.textContent = `Page ${currentPage} sur ${Math.max(totalPages, 1)}`;
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
  }

  function updateTable() {
    const filteredRows = getFilteredRows();
    renderPagination(filteredRows);
  }

  // Navigation pagination
  prevBtn.addEventListener('click', () => {
    currentPage--;
    updateTable();
  });

  nextBtn.addEventListener('click', () => {
    currentPage++;
    updateTable();
  });

  // Mise à jour sur saisie des filtres
  textFilters.forEach(input => input.addEventListener('input', () => {
    currentPage = 1;
    updateTable();
  }));

  paidFilter.addEventListener('change', () => {
    currentPage = 1;
    updateTable();
  });

  // Bouton toggle affichage filtres
  toggleBtn.addEventListener('click', function () {
    const isVisible = this.classList.toggle('active');
    filterGroups.forEach(group => {
      group.style.display = isVisible ? 'block' : 'none';
    });
    this.textContent = isVisible ? 'Masquer les filtres' : 'Afficher les filtres';
  });

  // Bouton Réinitialiser les filtres
  resetBtn.addEventListener('click', () => {
    textFilters.forEach(input => input.value = '');
    paidFilter.value = 'toutes';
    currentPage = 1;
    updateTable();
  });

  // Initialisation
  updateTable();

  let currentSort = {
    col: null,
    order: 'asc'
  };

  function parseDate(str) {
    // Format attendu : JJ/MM/AAAA ou AAAA-MM-JJ
    if (!str) return null;
    const parts = str.split('/');
    if (parts.length === 3) {
      return new Date(parts[2], parts[1] - 1, parts[0]); // JJ/MM/AAAA
    }
    return new Date(str); // fallback (ISO format)
  }

  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      const colIndex = parseInt(this.dataset.col);
      const isSameCol = currentSort.col === colIndex;
      currentSort.col = colIndex;
      currentSort.order = isSameCol && currentSort.order === 'asc' ? 'desc' : 'asc';

      const rows = getFilteredRows();

      rows.sort((a, b) => {
        const aText = a.cells[colIndex].textContent.trim();
        const bText = b.cells[colIndex].textContent.trim();
        const aDate = parseDate(aText);
        const bDate = parseDate(bText);
        if (!aDate || !bDate) return 0;

        return currentSort.order === 'asc' ? aDate - bDate : bDate - aDate;
      });

      // Réattache les lignes triées
      rows.forEach(row => table.tBodies[0].appendChild(row));
      updateTable();
    });
  });
});
