// Stück detail + Player view
async function renderStueck(stueckId, currentUser) {
  const main = document.getElementById('main-content');
  document.getElementById('back-btn').classList.remove('hidden');
  document.getElementById('page-title').textContent = 'Stück';

  main.innerHTML = '<div class="empty-state"><div class="icon">⏳</div>Laden…</div>';

  let stueck, audios;
  try {
    [stueck, audios] = await Promise.all([
      API.get(`/stuecke/${stueckId}`),
      API.get(`/audios/stueck/${stueckId}`),
    ]);
  } catch (e) {
    main.innerHTML = `<div class="empty-state">${escHtml(e.message)}</div>`;
    return;
  }

  document.getElementById('page-title').textContent = stueck.titel;

  const canManage = currentUser.rolle === 'admin' || currentUser.rolle === 'chorleiter';

  // Build stimme dropdown options
  const stimmenOpts = (stueck.verfuegbare_stimmen || [])
    .map(s => `<option value="${escHtml(s)}" ${stueck.meine_stimme === s ? 'selected' : ''}>${escHtml(s)}</option>`)
    .join('');

  main.innerHTML = `
    <div class="card" style="margin-bottom:.75rem">
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.5rem">
        <div style="flex:1">
          <div style="font-weight:700;font-size:1.1rem">${escHtml(stueck.titel)}</div>
          ${stueck.komponist ? `<div style="font-size:.85rem;color:var(--text-muted)">${escHtml(stueck.komponist)}</div>` : ''}
        </div>
        <button class="star-btn ${stueck.is_favorit ? 'active' : ''}" id="stueck-fav-btn" onclick="toggleStueckFavDetail()">★</button>
      </div>
      ${stueck.notizen ? `<div style="font-size:.85rem;color:var(--text-muted)">${escHtml(stueck.notizen)}</div>` : ''}

      ${currentUser.rolle === 'mitglied' ? `
        <div style="margin-top:.75rem">
          ${!stueck.meine_stimme ? '<div class="stimme-hint">⚠ Wähle deine Stimme für dieses Stück</div>' : ''}
          <div style="display:flex;align-items:center;gap:.5rem">
            <label style="font-size:.875rem;font-weight:500;white-space:nowrap">Meine Stimme:</label>
            <select id="meine-stimme-sel" style="flex:1">
              <option value="">– wählen –</option>
              ${stimmenOpts}
            </select>
            <button class="btn btn-sm btn-primary" onclick="saveMeineStimme()">OK</button>
          </div>
        </div>
      ` : ''}
    </div>

    <div class="filter-row">
      <select id="filter-stimme">
        <option value="">Alle Stimmen</option>
        ${[...new Set(audios.map(a => a.stimme))].map(s => `<option>${escHtml(s)}</option>`).join('')}
      </select>
      <select id="filter-typ">
        <option value="">Alle Typen</option>
        <option value="gesungen">Gesungen</option>
        <option value="instrumental">Instrumental</option>
      </select>
    </div>

    ${canManage ? `<div style="margin-bottom:.75rem;display:flex;gap:.5rem;flex-wrap:wrap">
      <button class="btn btn-primary btn-sm" onclick="showUploadAudio()">+ Audio hochladen</button>
      <button class="btn btn-secondary btn-sm" id="zip-btn" onclick="downloadZip()">⬇ Alle herunterladen (ZIP)</button>
    </div>` : ''}

    <div id="audio-list"></div>
    <div id="player-container"></div>
  `;

  function renderAudioList() {
    const stimmeFilter = document.getElementById('filter-stimme')?.value || '';
    const typFilter = document.getElementById('filter-typ')?.value || '';

    let filtered = audios;
    if (stimmeFilter) filtered = filtered.filter(a => a.stimme === stimmeFilter);
    if (typFilter) filtered = filtered.filter(a => a.typ === typFilter);

    const list = document.getElementById('audio-list');
    if (!list) return;

    if (!filtered.length) {
      list.innerHTML = '<div class="text-muted" style="text-align:center;padding:1.5rem">Keine Audios</div>';
      return;
    }

    list.innerHTML = filtered.map(a => `
      <div class="audio-item ${a.is_favorit ? 'favorit' : ''}" data-audio-id="${a.id}" onclick="openAudio(${a.id})">
        <div class="audio-header">
          <span class="audio-stimme">${escHtml(a.stimme)}</span>
          <span class="audio-typ">${a.typ === 'gesungen' ? 'Gesungen' : 'Instrumental'}</span>
          <span style="flex:1"></span>
          <button class="star-btn ${a.is_favorit ? 'active' : ''}" onclick="toggleAudioFav(event, ${a.id})">★</button>
          ${canManage ? `<button class="btn-icon" onclick="deleteAudio(event, ${a.id})" title="Löschen">&#x2715;</button>` : ''}
        </div>
        ${a.bezeichnung ? `<div class="audio-bezeichnung">${escHtml(a.bezeichnung)}</div>` : ''}
      </div>
    `).join('');
  }

  window.openAudio = async function (audioId) {
    const container = document.getElementById('player-container');
    container.innerHTML = '<div class="text-muted" style="padding:.5rem">Laden…</div>';
    document.getElementById('audio-list').classList.add('hidden');

    try {
      const audioData = await API.get(`/audios/${audioId}`);
      const p = createPlayer(audioData, currentUser,
        (m) => { audioData.markierungen = [...(audioData.markierungen || []), m]; },
        () => {}
      );
      container.innerHTML = p.render();
      p.initAudio();

      const backToList = document.createElement('button');
      backToList.className = 'back-btn';
      backToList.innerHTML = '&#8592; Alle Audios';
      backToList.onclick = () => {
        container.innerHTML = '';
        document.getElementById('audio-list').classList.remove('hidden');
      };
      container.prepend(backToList);
    } catch (e) {
      container.innerHTML = `<div class="text-muted">${escHtml(e.message)}</div>`;
    }
  };

  window.toggleAudioFav = async function (e, id) {
    e.stopPropagation();
    try {
      const res = await API.post(`/favoriten/audio/${id}`);
      const a = audios.find(x => x.id === id);
      if (a) a.is_favorit = res.is_favorit;
      renderAudioList();
    } catch (err) { showToast(err.message, 'error'); }
  };

  window.deleteAudio = async function (e, id) {
    e.stopPropagation();
    if (!confirm('Audio löschen?')) return;
    try {
      await API.delete(`/audios/${id}`);
      audios = audios.filter(x => x.id !== id);
      renderAudioList();
      showToast('Gelöscht');
    } catch (err) { showToast(err.message, 'error'); }
  };

  window.saveMeineStimme = async function () {
    const stimme = document.getElementById('meine-stimme-sel')?.value;
    if (!stimme) { showToast('Bitte Stimme wählen', 'error'); return; }
    try {
      await API.post(`/stuecke/${stueckId}/stimme`, { stimme });
      showToast('Stimme gespeichert', 'success');
    } catch (e) { showToast(e.message, 'error'); }
  };

  window.toggleStueckFavDetail = async function () {
    try {
      const res = await API.post(`/favoriten/stueck/${stueckId}`);
      stueck.is_favorit = res.is_favorit;
      document.getElementById('stueck-fav-btn').classList.toggle('active', res.is_favorit);
    } catch (e) { showToast(e.message, 'error'); }
  };

  window.showUploadAudio = function () {
    openModal('Audio hochladen', `
      <div class="form-group">
        <label>Stimme</label>
        <select id="up-stimme">
          ${['Sopran','Sopran 1','Sopran 2','Mezzo','Mezzo 1','Mezzo 2','Alt','Alt 1','Alt 2','Tenor','Tenor 1','Tenor 2','Bass','Bass 1','Bass 2','Männer','Alle'].map(s => `<option>${s}</option>`).join('')}
        </select>
      </div>
      <div class="form-group">
        <label>Typ</label>
        <select id="up-typ">
          <option value="instrumental" selected>Instrumental</option>
          <option value="gesungen">Gesungen</option>
        </select>
      </div>
      <div class="form-group">
        <label>Bezeichnung (optional)</label>
        <input type="text" id="up-bezeichnung" placeholder="z.B. 'mit Klavierbegleitung'">
      </div>
      <div class="form-group">
        <label>Audiodatei (MP3, AAC, M4A, WAV)</label>
        <input type="file" id="up-file" accept=".mp3,.aac,.m4a,.wav">
      </div>
      <div class="upload-progress hidden" id="up-progress">
        <div class="upload-progress-fill" id="up-progress-fill" style="width:0%"></div>
      </div>
    `, [
      {
        id: 'upload', label: 'Hochladen', cls: 'btn-primary',
        handler: async () => {
          const file = document.getElementById('up-file').files[0];
          if (!file) { showToast('Datei fehlt', 'error'); return; }

          const fd = new FormData();
          fd.append('stimme', document.getElementById('up-stimme').value);
          fd.append('typ', document.getElementById('up-typ').value);
          const bez = document.getElementById('up-bezeichnung').value.trim();
          if (bez) fd.append('bezeichnung', bez);
          fd.append('datei', file);

          document.getElementById('up-progress').classList.remove('hidden');
          try {
            const res = await API.postForm(`/audios/stueck/${stueckId}`, fd);
            const refreshed = await API.get(`/audios/stueck/${stueckId}`);
            audios = refreshed;
            closeModal();
            showToast('Hochgeladen', 'success');
            renderAudioList();
          } catch (e) { showToast(e.message, 'error'); }
        }
      },
      { id: 'cancel', label: 'Abbrechen', handler: closeModal },
    ]);
  };

  window.downloadZip = async function () {
    const btn = document.getElementById('zip-btn');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Wird erstellt…'; }
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`/api/stuecke/${stueckId}/download-zip`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Fehler beim Download' }));
        throw new Error(err.detail || 'Fehler');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${stueck.titel}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '⬇ Alle herunterladen (ZIP)'; }
    }
  };

  document.getElementById('filter-stimme')?.addEventListener('change', renderAudioList);
  document.getElementById('filter-typ')?.addEventListener('change', renderAudioList);

  renderAudioList();
}
