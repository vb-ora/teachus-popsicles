// Auftritte & Setlists (Chorleiter/Admin)
const BEGLEITUNG_VORSCHLAEGE = ['A cappella', 'mit Klavier', 'mit Cajon', 'mit Band', 'Playback'];

function fmtDauer(sek) {
  if (sek == null || sek === '') return '';
  sek = Math.round(sek);
  const h = Math.floor(sek / 3600);
  const m = Math.floor((sek % 3600) / 60);
  const s = String(sek % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

// Wert für Eingabefelder: immer mm:ss (auch über 60 Minuten, z.B. 75:00)
function fmtMmSs(sek) {
  if (sek == null || sek === '') return '';
  return `${Math.floor(sek / 60)}:${String(sek % 60).padStart(2, '0')}`;
}

// Dauer-Eingabe immer als mm:ss: "3:45" → 225, "" → null, alles andere → NaN
function parseDauer(str) {
  str = (str || '').trim();
  if (!str) return null;
  const m = str.match(/^(\d+):([0-5]\d)$/);
  return m ? +m[1] * 60 + +m[2] : NaN;
}

// Zusatzzeiten eines Auftritts (zählen zur Gesamtdauer)
const ZUSATZZEITEN = [
  { feld: 'dauer_aufabgang', label: 'Auf- und Abgang' },
  { feld: 'dauer_moderation', label: 'Moderation' },
  { feld: 'dauer_applaus_tonangabe', label: 'Applaus & Tonangabe' },
];

function fmtDatum(iso) {
  const [y, m, d] = iso.split('-');
  return `${d}.${m}.${y}`;
}

function auftrittZeiten(a) {
  return [
    a.uhrzeit_einsingen ? `Einsingen ${a.uhrzeit_einsingen}` : '',
    a.uhrzeit_konzert ? `Konzert ${a.uhrzeit_konzert}` : '',
  ].filter(Boolean).join(' · ');
}

async function downloadAuftrittPdf(a, btn) {
  if (btn) btn.disabled = true;
  try { await API.download(`/auftritte/${a.id}/pdf`, `Setlist ${a.name}.pdf`); }
  catch (e) { showToast(e.message, 'error'); }
  finally { if (btn) btn.disabled = false; }
}

// Anlegen/Bearbeiten-Dialog; onSaved bekommt den gespeicherten Auftritt
function openAuftrittModal(a, onSaved) {
  a = a || {};
  openModal(a.id ? 'Auftritt bearbeiten' : 'Auftritt anlegen', `
    <div class="form-group"><label>Name</label>
      <input type="text" id="af-name" value="${escHtml(a.name || '')}" placeholder="z.B. 125 Jahre Chorverband"></div>
    <div class="form-group"><label>Datum</label>
      <input type="date" id="af-datum" value="${escHtml(a.datum || '')}"></div>
    <div class="flex gap-1">
      <div class="form-group" style="flex:1"><label>Einsingen (optional)</label>
        <input type="time" id="af-einsingen" value="${escHtml(a.uhrzeit_einsingen || '')}"></div>
      <div class="form-group" style="flex:1"><label>Konzert (optional)</label>
        <input type="time" id="af-konzert" value="${escHtml(a.uhrzeit_konzert || '')}"></div>
    </div>
    <div class="section-title" style="margin-top:.25rem">Zusatzzeiten (optional, mm:ss)</div>
    <div class="flex gap-1 flex-wrap">
      ${ZUSATZZEITEN.map(z => `
        <div class="form-group" style="flex:1;min-width:8rem"><label>${z.label}</label>
          <input type="text" id="af-${z.feld}" placeholder="mm:ss"
            value="${fmtMmSs(a[z.feld])}"></div>`).join('')}
    </div>
    <div class="form-group"><label>Notizen (optional)</label>
      <textarea id="af-notizen" rows="3">${escHtml(a.notizen || '')}</textarea></div>
  `, [
    {
      id: 'save', label: 'Speichern', cls: 'btn-primary',
      handler: async () => {
        const payload = {
          name: document.getElementById('af-name').value.trim(),
          datum: document.getElementById('af-datum').value,
          uhrzeit_einsingen: document.getElementById('af-einsingen').value || null,
          uhrzeit_konzert: document.getElementById('af-konzert').value || null,
          notizen: document.getElementById('af-notizen').value.trim() || null,
        };
        for (const z of ZUSATZZEITEN) {
          const wert = parseDauer(document.getElementById(`af-${z.feld}`).value);
          if (Number.isNaN(wert)) { showToast(`${z.label}: bitte als mm:ss angeben, z.B. 2:30`, 'error'); return; }
          payload[z.feld] = wert;
        }
        if (!payload.name) { showToast('Name fehlt', 'error'); return; }
        if (!payload.datum) { showToast('Datum fehlt', 'error'); return; }
        try {
          const saved = a.id
            ? await API.put(`/auftritte/${a.id}`, payload)
            : await API.post('/auftritte', payload);
          closeModal();
          showToast('Gespeichert', 'success');
          onSaved(saved);
        } catch (e) { showToast(e.message, 'error'); }
      }
    },
    { id: 'cancel', label: 'Abbrechen', handler: closeModal },
  ]);
}

// ── Liste aller Auftritte ──
async function renderAuftritte(currentUser) {
  const main = document.getElementById('main-content');
  document.getElementById('page-title').textContent = 'Auftritte';
  document.getElementById('back-btn').classList.add('hidden');
  main.innerHTML = '<div class="empty-state"><div class="icon">⏳</div>Laden…</div>';

  let auftritte = [];
  try {
    auftritte = await API.get('/auftritte');
  } catch (e) {
    main.innerHTML = `<div class="empty-state">${escHtml(e.message)}</div>`;
    return;
  }

  function render() {
    main.innerHTML = `
      <div style="margin-bottom:.75rem">
        <button class="btn btn-primary btn-sm" id="af-add">+ Auftritt anlegen</button>
      </div>
      ${!auftritte.length ? '<div class="empty-state"><div class="icon">🎤</div>Noch keine Auftritte.</div>' : ''}
      ${auftritte.map(a => `
        <div class="stueck-item" data-id="${a.id}">
          <div class="stueck-info" data-action="open">
            <div class="stueck-titel">${escHtml(a.name)}</div>
            <div class="stueck-komponist">
              ${fmtDatum(a.datum)}${auftrittZeiten(a) ? ' · ' + escHtml(auftrittZeiten(a)) : ''}
              · ${a.anzahl_stuecke} Stück${a.anzahl_stuecke === 1 ? '' : 'e'}
              · ${fmtDauer(a.gesamtdauer_sekunden)}
            </div>
          </div>
          <button class="btn-icon" data-action="pdf" title="PDF exportieren">⬇</button>
          <button class="btn-icon" data-action="edit" title="Bearbeiten">&#9998;</button>
          <button class="btn-icon" data-action="delete" title="Löschen">&#x2715;</button>
        </div>
      `).join('')}
    `;

    document.getElementById('af-add').onclick = () =>
      openAuftrittModal(null, saved => goToAuftritt(saved.id));

    main.querySelectorAll('.stueck-item').forEach(row => {
      const a = auftritte.find(x => x.id === +row.dataset.id);
      row.addEventListener('click', async (e) => {
        const action = e.target.closest('[data-action]')?.dataset.action || 'open';
        if (action === 'open') goToAuftritt(a.id);
        else if (action === 'pdf') downloadAuftrittPdf(a, e.target);
        else if (action === 'edit') {
          openAuftrittModal(a, saved => { Object.assign(a, saved); render(); });
        } else if (action === 'delete') {
          if (!confirm(`Auftritt „${a.name}" samt Setlist löschen?`)) return;
          try {
            await API.delete(`/auftritte/${a.id}`);
            auftritte = auftritte.filter(x => x.id !== a.id);
            render();
            showToast('Gelöscht');
          } catch (err) { showToast(err.message, 'error'); }
        }
      });
    });
  }

  render();
}

// ── Detail: Setlist eines Auftritts ──
async function renderAuftritt(auftrittId, currentUser) {
  const main = document.getElementById('main-content');
  document.getElementById('page-title').textContent = 'Auftritt';
  document.getElementById('back-btn').classList.remove('hidden');
  main.innerHTML = '<div class="empty-state"><div class="icon">⏳</div>Laden…</div>';

  let a, stuecke;
  try {
    [a, stuecke] = await Promise.all([
      API.get(`/auftritte/${auftrittId}`),
      API.get('/stuecke'),
    ]);
  } catch (e) {
    main.innerHTML = `<div class="empty-state">${escHtml(e.message)}</div>`;
    return;
  }

  function render() {
    document.getElementById('page-title').textContent = a.name;
    main.innerHTML = `
      <div class="card">
        <div class="card-row">
          <div style="flex:1;min-width:0">
            <div style="font-weight:700;font-size:1.1rem">${escHtml(a.name)}</div>
            <div class="text-muted">${fmtDatum(a.datum)}${auftrittZeiten(a) ? ' · ' + escHtml(auftrittZeiten(a)) : ''}</div>
            ${a.notizen ? `<div class="text-muted" style="margin-top:.35rem;white-space:pre-line">${escHtml(a.notizen)}</div>` : ''}
          </div>
          <button class="btn-icon" id="sl-edit" title="Bearbeiten">&#9998;</button>
        </div>
        <div class="flex gap-1 flex-wrap mt-1">
          <button class="btn btn-secondary btn-sm" id="sl-pdf">⬇ Setlist-PDF</button>
        </div>
      </div>

      <div class="section-title">Besetzung</div>
      <div class="text-muted" style="font-size:.8rem;margin-bottom:.4rem">
        ${a.saenger.filter(x => x.anwesend).length} von ${a.saenger.length} Sängern anwesend ·
        Namen anklicken zum Umschalten. Abwesende erscheinen nicht im PDF.
      </div>
      <div class="matrix-wrap besetzung">
        ${matrixTableHTML(a.saenger, a.eintraege, {
          nameCls: s => 'mx-toggle ' + (s.anwesend ? 'anwesend' : 'abwesend'),
          nameTitle: s => `${s.name} (${s.stimme || 'keine Stimme'}) – ${s.anwesend ? 'anwesend' : 'abwesend'}, klicken zum Umschalten`,
          cellCls: s => s.anwesend ? '' : 'abwesend',
        })}
      </div>

      <div class="section-title">Setlist</div>
      <datalist id="begleitung-vorschlaege">
        ${BEGLEITUNG_VORSCHLAEGE.map(b => `<option value="${escHtml(b)}">`).join('')}
      </datalist>
      <div id="setlist">
        ${!a.eintraege.length ? '<div class="text-muted" style="text-align:center;padding:1rem">Noch keine Stücke in der Setlist.</div>' : ''}
        ${a.eintraege.map((e, i) => `
          <div class="setlist-row" data-id="${e.id}">
            <span class="drag-handle" title="Ziehen zum Sortieren">⋮⋮</span>
            <span class="setlist-nr">${i + 1}</span>
            <div class="setlist-main">
              <div class="setlist-titel">${escHtml(e.titel)}</div>
              <div class="setlist-fields">
                <input type="text" class="sl-begleitung" list="begleitung-vorschlaege"
                  placeholder="Begleitung" value="${escHtml(e.begleitung || '')}">
                <input type="text" class="sl-dauer"
                  placeholder="mm:ss" value="${fmtMmSs(e.dauer_sekunden)}">
              </div>
            </div>
            <div class="setlist-actions">
              <button class="btn-icon" data-action="up" title="Nach oben" ${i === 0 ? 'disabled' : ''}>▲</button>
              <button class="btn-icon" data-action="down" title="Nach unten" ${i === a.eintraege.length - 1 ? 'disabled' : ''}>▼</button>
              <button class="btn-icon" data-action="delete" title="Entfernen">&#x2715;</button>
            </div>
          </div>
        `).join('')}
      </div>

      ${ZUSATZZEITEN.some(z => a[z.feld] != null) ? `
        <div class="setlist-extras">
          <div><span>Lieder</span><span>${fmtDauer(a.lieddauer_sekunden)}</span></div>
          ${ZUSATZZEITEN.filter(z => a[z.feld] != null).map(z =>
            `<div><span>${z.label}</span><span>${fmtDauer(a[z.feld])}</span></div>`).join('')}
        </div>` : ''}
      <div class="setlist-total">
        <span>Gesamtdauer</span>
        <strong>${fmtDauer(a.gesamtdauer_sekunden)}</strong>
      </div>
      ${a.eintraege.some(e => e.dauer_sekunden == null) ? '<div class="text-muted" style="text-align:right;font-size:.8rem">Nicht alle Stücke haben eine Dauer.</div>' : ''}

      <div class="card mt-2">
        <div class="section-title" style="margin-top:0">Stück hinzufügen</div>
        <div class="flex gap-1">
          <select id="sl-add-stueck" style="flex:1">
            <option value="">Stück wählen…</option>
            ${stuecke.map(s => `<option value="${s.id}">${escHtml(s.titel)}${
              a.eintraege.some(e => e.stueck_id === s.id) ? ' ✓' : ''}</option>`).join('')}
          </select>
          <button class="btn btn-primary btn-sm" id="sl-add">Hinzufügen</button>
        </div>
      </div>
    `;
    bind();
  }

  async function update(promise) {
    try {
      a = await promise;
      render();
    } catch (e) {
      showToast(e.message, 'error');
      render();
    }
  }

  function saveOrder(ids) {
    return update(API.put(`/setlists/${a.id}/reihenfolge`, { eintrag_ids: ids }));
  }

  async function toggleSaenger(userId) {
    try {
      const res = await API.post(`/auftritte/${a.id}/saenger/${userId}/toggle`);
      const s = a.saenger.find(x => x.id === userId);
      if (s) s.anwesend = res.anwesend;
      const scroll = document.querySelector('.besetzung')?.scrollLeft || 0;
      render();
      const wrap = document.querySelector('.besetzung');
      if (wrap) wrap.scrollLeft = scroll;
    } catch (e) { showToast(e.message, 'error'); }
  }

  function bind() {
    document.querySelectorAll('.besetzung th.mx-toggle').forEach(th => {
      th.onclick = () => toggleSaenger(+th.dataset.user);
    });
    document.getElementById('sl-edit').onclick = () =>
      openAuftrittModal(a, saved => { a = saved; render(); });
    document.getElementById('sl-pdf').onclick = (e) => downloadAuftrittPdf(a, e.currentTarget);

    document.getElementById('sl-add').onclick = () => {
      const stueckId = +document.getElementById('sl-add-stueck').value;
      if (!stueckId) { showToast('Bitte Stück wählen', 'error'); return; }
      update(API.post(`/setlists/${a.id}/eintraege`, { stueck_id: stueckId }));
    };

    const list = document.getElementById('setlist');
    const ids = () => a.eintraege.map(e => e.id);

    list.querySelectorAll('.setlist-row').forEach(row => {
      const id = +row.dataset.id;
      const eintrag = a.eintraege.find(e => e.id === id);

      // Begleitung/Dauer speichern, sobald ein Feld verlassen wird
      const begInput = row.querySelector('.sl-begleitung');
      const dauerInput = row.querySelector('.sl-dauer');
      const save = () => {
        const dauer = parseDauer(dauerInput.value);
        if (Number.isNaN(dauer)) {
          showToast('Dauer bitte als mm:ss angeben, z.B. 3:45', 'error');
          dauerInput.focus();
          return;
        }
        const begleitung = begInput.value.trim() || null;
        if (begleitung === eintrag.begleitung && dauer === eintrag.dauer_sekunden) return;
        update(API.put(`/setlists/eintraege/${id}`, {
          begleitung, dauer_sekunden: dauer, notizen: eintrag.notizen,
        }));
      };
      begInput.addEventListener('change', save);
      dauerInput.addEventListener('change', save);
      [begInput, dauerInput].forEach(inp =>
        inp.addEventListener('keydown', ev => { if (ev.key === 'Enter') inp.blur(); }));

      row.querySelector('.setlist-actions').addEventListener('click', ev => {
        const action = ev.target.closest('[data-action]')?.dataset.action;
        const order = ids();
        const idx = order.indexOf(id);
        if (action === 'up' && idx > 0) {
          [order[idx - 1], order[idx]] = [order[idx], order[idx - 1]];
          saveOrder(order);
        } else if (action === 'down' && idx < order.length - 1) {
          [order[idx + 1], order[idx]] = [order[idx], order[idx + 1]];
          saveOrder(order);
        } else if (action === 'delete') {
          if (!confirm(`„${eintrag.titel}" aus der Setlist entfernen?`)) return;
          update(API.delete(`/setlists/eintraege/${id}`));
        }
      });

      // Drag & Drop: nur über den Griff starten, damit die Eingabefelder normal bedienbar bleiben
      const handle = row.querySelector('.drag-handle');
      handle.addEventListener('mousedown', () => { row.draggable = true; });
      handle.addEventListener('mouseup', () => { row.draggable = false; });
      row.addEventListener('dragstart', ev => {
        ev.dataTransfer.effectAllowed = 'move';
        ev.dataTransfer.setData('text/plain', String(id));
        row.classList.add('dragging');
      });
      row.addEventListener('dragend', () => {
        row.draggable = false;
        row.classList.remove('dragging');
        const neu = [...list.querySelectorAll('.setlist-row')].map(r => +r.dataset.id);
        if (neu.join() !== ids().join()) saveOrder(neu);
      });
    });

    list.addEventListener('dragover', ev => {
      const dragging = list.querySelector('.dragging');
      if (!dragging) return;
      ev.preventDefault();
      const after = [...list.querySelectorAll('.setlist-row:not(.dragging)')].find(r => {
        const box = r.getBoundingClientRect();
        return ev.clientY < box.top + box.height / 2;
      });
      if (after) list.insertBefore(dragging, after);
      else list.appendChild(dragging);
    });
  }

  render();
}
