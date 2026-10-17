// Repertoire view
async function renderRepertoire(currentUser) {
  const main = document.getElementById('main-content');
  document.getElementById('page-title').textContent = 'Repertoire';
  document.getElementById('back-btn').classList.add('hidden');

  const canManage = Rollen.canManage(currentUser);

  main.innerHTML = `
    <div class="search-row">
      <input type="text" id="search-input" placeholder="Titel oder Komponist suchen…">
    </div>
    <div class="tabs">
      <button class="tab-btn active" id="tab-favoriten" onclick="switchTab('favoriten')">Favoriten</button>
      <button class="tab-btn" id="tab-alle" onclick="switchTab('alle')">Alle Stücke</button>
    </div>
    ${canManage ? `<div style="margin-bottom:.75rem"><button class="btn btn-primary btn-sm" onclick="showAddStueck()">+ Stück anlegen</button></div>` : ''}
    <div id="stuecke-list"></div>
  `;

  let allStuecke = [];
  let currentTab = 'favoriten';

  async function loadAndRender(q = '') {
    try {
      allStuecke = await API.get(`/stuecke${q ? `?q=${encodeURIComponent(q)}` : ''}`);
      renderList();
    } catch (e) {
      showToast(e.message, 'error');
    }
  }

  function renderList() {
    const list = document.getElementById('stuecke-list');
    if (!list) return;

    let items = allStuecke;
    if (currentTab === 'favoriten') {
      items = allStuecke.filter(s => s.is_favorit);
    }

    if (!items.length) {
      list.innerHTML = `<div class="empty-state"><div class="icon">🎵</div>${currentTab === 'favoriten' ? 'Noch keine Favoriten.<br>Stücke mit ★ markieren.' : 'Keine Stücke gefunden.'}</div>`;
      return;
    }

    list.innerHTML = items.map(s => `
      <div class="stueck-item" data-id="${s.id}">
        <div class="stueck-info" onclick="goToStueck(${s.id})">
          <div class="stueck-titel">${escHtml(s.titel)}</div>
          ${s.komponist ? `<div class="stueck-komponist">${escHtml(s.komponist)}</div>` : ''}
        </div>
        <button class="star-btn ${s.is_favorit ? 'active' : ''}" onclick="toggleStueckFav(event, ${s.id})">★</button>
        ${canManage ? `
          <button class="btn-icon" onclick="editStueck(event, ${s.id})" title="Bearbeiten">&#9998;</button>
          <button class="btn-icon" onclick="deleteStueck(event, ${s.id})" title="Löschen">&#x2715;</button>
        ` : ''}
      </div>
    `).join('');
  }

  window.switchTab = function (tab) {
    currentTab = tab;
    document.getElementById('tab-favoriten').classList.toggle('active', tab === 'favoriten');
    document.getElementById('tab-alle').classList.toggle('active', tab === 'alle');
    renderList();
  };

  window.toggleStueckFav = async function (e, id) {
    e.stopPropagation();
    try {
      const res = await API.post(`/favoriten/stueck/${id}`);
      const s = allStuecke.find(x => x.id === id);
      if (s) s.is_favorit = res.is_favorit;
      renderList();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  window.showAddStueck = function () {
    openModal('Stück anlegen', `
      <div class="form-group"><label>Titel</label><input type="text" id="m-titel" required></div>
      <div class="form-group"><label>Komponist (optional)</label><input type="text" id="m-komponist"></div>
      <div class="form-group"><label>Notizen (optional)</label><textarea id="m-notizen" rows="3"></textarea></div>
    `, [
      {
        id: 'save', label: 'Speichern', cls: 'btn-primary',
        handler: async () => {
          const titel = document.getElementById('m-titel').value.trim();
          if (!titel) { showToast('Titel fehlt', 'error'); return; }
          try {
            await API.post('/stuecke', {
              titel,
              komponist: document.getElementById('m-komponist').value.trim() || null,
              notizen: document.getElementById('m-notizen').value.trim() || null,
            });
            closeModal();
            showToast('Stück angelegt', 'success');
            loadAndRender(document.getElementById('search-input')?.value || '');
          } catch (e) { showToast(e.message, 'error'); }
        }
      },
      { id: 'cancel', label: 'Abbrechen', handler: closeModal },
    ]);
  };

  window.editStueck = async function (e, id) {
    e.stopPropagation();
    const s = allStuecke.find(x => x.id === id);
    if (!s) return;
    openModal('Stück bearbeiten', `
      <div class="form-group"><label>Titel</label><input type="text" id="m-titel" value="${escHtml(s.titel)}"></div>
      <div class="form-group"><label>Komponist</label><input type="text" id="m-komponist" value="${escHtml(s.komponist || '')}"></div>
      <div class="form-group"><label>Notizen</label><textarea id="m-notizen" rows="3">${escHtml(s.notizen || '')}</textarea></div>
    `, [
      {
        id: 'save', label: 'Speichern', cls: 'btn-primary',
        handler: async () => {
          try {
            await API.put(`/stuecke/${id}`, {
              titel: document.getElementById('m-titel').value.trim(),
              komponist: document.getElementById('m-komponist').value.trim() || null,
              notizen: document.getElementById('m-notizen').value.trim() || null,
            });
            closeModal();
            showToast('Gespeichert', 'success');
            loadAndRender(document.getElementById('search-input')?.value || '');
          } catch (e) { showToast(e.message, 'error'); }
        }
      },
      { id: 'cancel', label: 'Abbrechen', handler: closeModal },
    ]);
  };

  window.deleteStueck = async function (e, id) {
    e.stopPropagation();
    if (!confirm('Stück und alle Audios löschen?')) return;
    try {
      await API.delete(`/stuecke/${id}`);
      allStuecke = allStuecke.filter(x => x.id !== id);
      renderList();
      showToast('Gelöscht');
    } catch (err) { showToast(err.message, 'error'); }
  };

  let searchTimer;
  document.getElementById('search-input').addEventListener('input', e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadAndRender(e.target.value.trim()), 300);
  });

  await loadAndRender();
}
