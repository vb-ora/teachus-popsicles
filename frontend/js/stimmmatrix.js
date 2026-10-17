// Stimmmatrix: welcher Sänger singt in welchem Stück welche Stimme (Chorleiter/Admin)
const STIMMGRUPPEN_CSS = {
  Sopran: 'grp-sopran', Mezzo: 'grp-mezzo', Alt: 'grp-alt',
  Tenor: 'grp-tenor', Bass: 'grp-bass', Sonstige: 'grp-sonstige',
};

// Gemeinsame Matrix-Darstellung (Stimmmatrix + Auftritts-Besetzung).
// Sänger sind nach Standardstimme gruppiert (dicke Trennlinie, keine Überschrift);
// die Zellfarbe richtet sich nach der Stimme, die im jeweiligen Stück gesungen wird.
function matrixCellHTML(zeile, s, i, saenger, extraCls = '') {
  const z = zeile.zellen[s.id];
  const grpStart = i === 0 || saenger[i - 1].gruppe !== s.gruppe;
  const cls = [
    'mx-cell', STIMMGRUPPEN_CSS[z.gruppe] || '',
    z.ist_standard ? 'is-standard' : 'is-custom',
    grpStart ? 'grp-start' : '', extraCls,
  ].join(' ');
  const tip = `${s.name}: ${z.stimme || '–'}${z.ist_standard ? ' (Standard)' : ''}`;
  return `<td class="${cls}" data-zeile="${zeile.id}" data-user="${s.id}" title="${escHtml(tip)}">${escHtml(z.kuerzel || '–')}</td>`;
}

function matrixTableHTML(saenger, zeilen, { nameCls = () => '', nameTitle = null, cellCls = () => '' } = {}) {
  const grpStart = (i) => i === 0 || saenger[i - 1].gruppe !== saenger[i].gruppe;
  return `
    <table class="matrix">
      <thead>
        <tr>
          <th class="mx-sticky">Stück</th>
          ${saenger.map((s, i) => `
            <th class="mx-name ${STIMMGRUPPEN_CSS[s.gruppe]} ${grpStart(i) ? 'grp-start' : ''} ${nameCls(s)}"
                data-user="${s.id}"
                title="${escHtml(nameTitle ? nameTitle(s) : `${s.name} (${s.stimme || 'keine Stimme'})`)}">
              <span>${escHtml(s.name)}</span>
            </th>`).join('')}
        </tr>
      </thead>
      <tbody>
        ${zeilen.map(z => `
          <tr>
            <th class="mx-sticky mx-titel" title="${escHtml(z.titel)}">${escHtml(z.titel)}</th>
            ${saenger.map((s, i) => matrixCellHTML(z, s, i, saenger, cellCls(s))).join('')}
          </tr>`).join('')}
      </tbody>
    </table>`;
}

async function renderStimmmatrix(currentUser) {
  const main = document.getElementById('main-content');
  document.getElementById('page-title').textContent = 'Stimmmatrix';
  document.getElementById('back-btn').classList.add('hidden');
  main.innerHTML = '<div class="empty-state"><div class="icon">⏳</div>Laden…</div>';

  let data;
  try {
    data = await API.get('/stimmmatrix');
  } catch (e) {
    main.innerHTML = `<div class="empty-state">${escHtml(e.message)}</div>`;
    return;
  }

  const { saenger, stuecke } = data;

  function render() {
    if (!saenger.length || !stuecke.length) {
      main.innerHTML = `<div class="empty-state"><div class="icon">🎼</div>${
        !stuecke.length ? 'Noch keine Stücke im Repertoire.' : 'Noch keine Sänger mit Stimme.'}</div>`;
      return;
    }

    main.innerHTML = `
      <div class="toolbar">
        <div class="text-muted" style="flex:1">
          ${stuecke.length} Stücke · ${saenger.length} Sänger ·
          <span class="legend-custom">fett</span> = stückspezifisch, grau = Standardstimme.
          Zellfarbe = gesungene Stimme. Zelle anklicken zum Ändern.
        </div>
        <button class="btn btn-secondary btn-sm" id="mx-pdf-btn">⬇ PDF</button>
      </div>
      <div class="matrix-wrap">${matrixTableHTML(saenger, stuecke)}</div>
    `;

    document.getElementById('mx-pdf-btn').onclick = async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      try { await API.download('/stimmmatrix/pdf', 'Stimmmatrix.pdf'); }
      catch (err) { showToast(err.message, 'error'); }
      finally { btn.disabled = false; }
    };

    main.querySelector('.matrix tbody').addEventListener('click', (e) => {
      const td = e.target.closest('td.mx-cell');
      if (td && !td.querySelector('select')) openEditor(td);
    });
  }

  function openEditor(td) {
    const stueck = stuecke.find(x => x.id === +td.dataset.zeile);
    const s = saenger.find(x => x.id === +td.dataset.user);
    const z = stueck.zellen[s.id];
    const rerender = () => { td.outerHTML = matrixCellHTML(stueck, s, saenger.indexOf(s), saenger); };

    const optionen = [...stueck.verfuegbare_stimmen];
    if (!z.ist_standard && z.stimme && !optionen.includes(z.stimme)) optionen.unshift(z.stimme);

    const sel = document.createElement('select');
    sel.className = 'mx-select';
    sel.innerHTML = `
      <option value="">Standard (${escHtml(s.stimme || 'keine')})</option>
      ${optionen.map(o => `<option value="${escHtml(o)}">${escHtml(o)}</option>`).join('')}
    `;
    sel.value = z.ist_standard ? '' : z.stimme;

    const original = td.innerHTML;
    td.innerHTML = '';
    td.appendChild(sel);
    sel.focus();

    let done = false;
    const close = () => {
      if (done) return;
      done = true;
      rerender();
    };

    sel.addEventListener('click', ev => ev.stopPropagation());
    sel.addEventListener('keydown', ev => { if (ev.key === 'Escape') close(); });
    sel.addEventListener('blur', close);
    sel.addEventListener('change', async () => {
      const neu = sel.value || null;
      done = true;
      td.innerHTML = '…';
      try {
        stueck.zellen[s.id] = await API.put(`/stimmmatrix/${stueck.id}/${s.id}`, { stimme: neu });
        rerender();
      } catch (err) {
        showToast(err.message, 'error');
        td.innerHTML = original;
      }
    });
  }

  render();
}
