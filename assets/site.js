document.documentElement.classList.add('js');
const toggle = document.querySelector('.menu-toggle');
const menu = document.querySelector('.nav-links');
toggle?.addEventListener('click', () => {
  const open = toggle.getAttribute('aria-expanded') !== 'true';
  toggle.setAttribute('aria-expanded', String(open));
  menu.classList.toggle('is-open', open);
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && toggle?.getAttribute('aria-expanded') === 'true') {
    toggle.setAttribute('aria-expanded', 'false');
    menu.classList.remove('is-open');
    toggle.focus();
  }
});
const search = document.querySelector('#publication-search');
if (search) {
  const rows = Array.from(document.querySelectorAll('.pubs > li'));
  const status = document.querySelector('#search-status');
  const archive = document.querySelector('.publication-archive');
  let currentPage = 0;
  const normalize = text => text.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/[₀-₉]/g, digit => String('₀₁₂₃₄₅₆₇₈₉'.indexOf(digit))).replace(/[‐‑–—]/g, '-');
  const indexedRows = rows.map(row => ({row, text: normalize(row.textContent)}));
  if (archive) {
    const pagination = document.querySelector('#search-pagination');
    const previous = document.querySelector('#previous-results');
    const next = document.querySelector('#next-results');
    const render = () => {
      const terms = normalize(search.value.trim()).split(/\s+/).filter(Boolean);
      const matches = indexedRows.filter(item => terms.every(term => /^(19|20)\d{2}$/.test(term) ? item.row.dataset.year === term : item.text.includes(term)));
      const totalPages = Math.ceil(matches.length / 10);
      currentPage = Math.min(currentPage, Math.max(0, totalPages - 1));
      rows.forEach(row => {row.hidden = true;});
      const start = terms.length ? currentPage * 10 : 0;
      matches.slice(start, start + 10).forEach(({row}) => {row.hidden = false;});
      status.textContent = terms.length
        ? (matches.length ? `Showing ${start + 1}–${Math.min(start + 10, matches.length)} of ${matches.length} matching papers · ${rows.length} papers searched` : `No matching papers · ${rows.length} papers searched`)
        : `Showing the latest ${Math.min(10, rows.length)} papers · ${rows.length} papers in the archive`;
      document.querySelector('#no-results').hidden = matches.length > 0;
      pagination.hidden = !terms.length || totalPages <= 1;
      previous.disabled = currentPage === 0;
      next.disabled = currentPage >= totalPages - 1;
      document.querySelector('#results-page').textContent = `Page ${currentPage + 1} of ${Math.max(1,totalPages)}`;
    };
    search.addEventListener('input', () => {currentPage = 0;render();});
    document.querySelector('#clear-search').addEventListener('click', () => {search.value = '';currentPage = 0;render();search.focus();});
    previous.addEventListener('click', () => {currentPage--;render();archive.scrollIntoView({block:'start'});});
    next.addEventListener('click', () => {currentPage++;render();archive.scrollIntoView({block:'start'});});
    render();
  } else {
  const filter = () => {
    const term = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    rows.forEach(row => {
      row.hidden = !row.textContent.toLocaleLowerCase().includes(term);
      if (!row.hidden) visible++;
    });
    status.textContent = visible ? `${visible} of ${rows.length} entries shown` : 'No matching entries. Try another author, material or journal.';
  };
  search.addEventListener('input', filter);
  filter();
  }
}
