// Benutzerverwaltung (nur Superadmin)
const USER_STIMMEN = [
  'Sopran', 'Sopran 1', 'Sopran 2', 'Mezzo', 'Mezzo 1', 'Mezzo 2',
  'Alt', 'Alt 1', 'Alt 2', 'Tenor', 'Tenor 1', 'Tenor 2',
  'Bass', 'Bass 1', 'Bass 2', 'Männer',
];
const ROLLEN_LABEL = {
  superadmin: 'Superadmin', admin: 'Admin', chorleiter: 'Chorleiter', mitglied: 'Mitglied',
};
const VERGEBBARE_ROLLEN = ['mitglied', 'chorleiter', 'admin'];

async function renderBenutzerverwaltung(currentUser) {
  if (!Rollen.isSuperadmin(currentUser)) return;

  const main = document.getElementById('main-content');
  document.getElementById('page-title').textContent = 'Benutzerverwaltung';
  document.getElementById('back-btn').classList.add('hidden');
  main.innerHTML = '<div class="empty-state"><div class="icon">⏳</div>Laden…</div>';

  let users = [];
  try {
    users = await API.get('/superadmin/users');
  } catch (e) {
    main.innerHTML = `<div class="empty-state">${escHtml(e.message)}</div>`;
    return;
  }

  const fmtRegistriert = (iso) => iso ? new Date(iso + 'Z').toLocaleDateString('de-DE') : '–';

  function render() {
    main.innerHTML = `
      <div class="toolbar">
        <div class="section-title" style="margin:0;flex:1">Benutzer (${users.length})</div>
        <button class="btn btn-primary btn-sm" id="bv-add">+ Benutzer anlegen</button>
      </div>
      ${users.map(u => `
        <div class="card card-row" style="margin-bottom:.5rem" data-id="${u.id}">
          <div style="flex:1;min-width:0">
            <div style="font-weight:600">
              ${escHtml(u.name)}
              <span class="rolle-badge rolle-${u.rolle}">${ROLLEN_LABEL[u.rolle] || escHtml(u.rolle)}</span>
            </div>
            <div style="font-size:.8rem;color:var(--text-muted)">
              @${escHtml(u.username)} · ${u.stimme ? escHtml(u.stimme) : 'keine Stimme'}
              · registriert ${fmtRegistriert(u.created_at)}
            </div>
          </div>
          <button class="btn-icon" data-action="edit" title="Bearbeiten">&#9998;</button>
          ${u.id !== currentUser.id && u.rolle !== 'superadmin'
            ? '<button class="btn-icon" data-action="delete" title="Löschen">&#x2715;</button>'
            : '<span style="width:1.6rem"></span>'}
        </div>
      `).join('')}
    `;

    document.getElementById('bv-add').onclick = () => openUserModal(null);
    main.querySelectorAll('[data-id]').forEach(row => {
      const u = users.find(x => x.id === +row.dataset.id);
      row.querySelector('[data-action="edit"]').onclick = () => openUserModal(u);
      const del = row.querySelector('[data-action="delete"]');
      if (del) del.onclick = () => deleteUser(u);
    });
  }

  async function reload() {
    users = await API.get('/superadmin/users');
    render();
  }

  function openUserModal(u) {
    const neu = !u;
    const istSuperadmin = u?.rolle === 'superadmin';
    const rolle = u?.rolle || 'mitglied';

    openModal(neu ? 'Benutzer anlegen' : 'Benutzer bearbeiten', `
      <div class="form-group"><label>Name</label>
        <input type="text" id="bv-name" value="${escHtml(u?.name || '')}"></div>
      ${neu ? `<div class="form-group"><label>Benutzername</label>
        <input type="text" id="bv-username" autocomplete="off"></div>` : ''}
      <div class="form-group"><label>${neu ? 'Passwort' : 'Neues Passwort (leer = unverändert)'}</label>
        <input type="password" id="bv-pw" autocomplete="new-password"></div>
      <div class="form-group">
        <label>Rolle</label>
        ${istSuperadmin
          ? '<input type="text" value="Superadmin (nicht änderbar)" disabled>'
          : `<select id="bv-rolle">
              ${VERGEBBARE_ROLLEN.map(r => `<option value="${r}" ${r === rolle ? 'selected' : ''}>${ROLLEN_LABEL[r]}</option>`).join('')}
            </select>`}
      </div>
      <div class="form-group" id="bv-stimme-group">
        <label>Stimme</label>
        <select id="bv-stimme">
          <option value="">Stimme wählen…</option>
          ${USER_STIMMEN.map(s => `<option ${u?.stimme === s ? 'selected' : ''}>${s}</option>`).join('')}
        </select>
      </div>
      <div class="text-muted hidden" id="bv-chorleiter-hint" style="font-size:.8rem">
        Chorleiter haben keine Stimme und erscheinen nicht in der Stimmmatrix.
      </div>
    `, [
      {
        id: 'save', label: 'Speichern', cls: 'btn-primary',
        handler: async () => {
          const rolleNeu = istSuperadmin ? 'superadmin' : document.getElementById('bv-rolle').value;
          const stimme = document.getElementById('bv-stimme').value || null;
          const pw = document.getElementById('bv-pw').value;
          const payload = { name: document.getElementById('bv-name').value.trim(), stimme };
          if (!istSuperadmin) payload.rolle = rolleNeu;
          if (pw) payload.password = pw;

          if (!payload.name) { showToast('Name fehlt', 'error'); return; }
          if (rolleNeu !== 'chorleiter' && !stimme) { showToast('Bitte Stimme wählen', 'error'); return; }
          if (neu) {
            payload.username = document.getElementById('bv-username').value.trim();
            if (!payload.username) { showToast('Benutzername fehlt', 'error'); return; }
            if (!pw) { showToast('Passwort fehlt', 'error'); return; }
          }

          try {
            if (neu) await API.post('/superadmin/users', payload);
            else await API.put(`/superadmin/users/${u.id}`, payload);
            closeModal();
            showToast(neu ? 'Benutzer angelegt' : 'Gespeichert', 'success');
            await reload();
          } catch (e) { showToast(e.message, 'error'); }
        }
      },
      { id: 'cancel', label: 'Abbrechen', handler: closeModal },
    ]);

    // Chorleiter: Stimmauswahl ausblenden
    const rolleSel = document.getElementById('bv-rolle');
    const syncStimme = () => {
      const chorleiter = rolleSel?.value === 'chorleiter';
      document.getElementById('bv-stimme-group').classList.toggle('hidden', chorleiter);
      document.getElementById('bv-chorleiter-hint').classList.toggle('hidden', !chorleiter);
    };
    rolleSel?.addEventListener('change', syncStimme);
    syncStimme();
  }

  async function deleteUser(u) {
    if (!confirm(`Benutzer „${u.name}" (@${u.username}) wirklich löschen?\n\n`
      + 'Persönliche Favoriten und private Markierungen werden gelöscht. '
      + 'Kapitel und öffentliche Markierungen gehen auf dich über.')) return;
    try {
      await API.delete(`/superadmin/users/${u.id}`);
      users = users.filter(x => x.id !== u.id);
      render();
      showToast('Gelöscht');
    } catch (e) { showToast(e.message, 'error'); }
  }

  render();
}
