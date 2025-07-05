document.addEventListener('DOMContentLoaded', function () {
  const table = document.getElementById('table-factures');


  const noResultRow = document.createElement('tr');
  const td = document.createElement('td');
  td.colSpan = table.rows[0].cells.length;
  td.style.textAlign = 'center';
  td.textContent = 'Aucune facture';
  noResultRow.appendChild(td);
  noResultRow.style.display = 'none';
  table.tBodies[0].appendChild(noResultRow);

 
    });