// Admin panel
async function renderAdmin(currentUser) {
  if (currentUser.rolle !== 'admin') return;

  const main = document.getElementById('main-content');
  document.getElementById('page-title').textContent = 'Verwaltung';
  document.getElementById('back-btn').classList.remove('hidden');

  main.innerHTML = '<div class="empty-state"><div class="icon">⏳</div>Laden…</div>';

  let users = [];
  try {
    users = await API.get('/users');
  } catch (e) {
    main.innerHTML = `<div class="empty-state">${escHtml(e.message)}</div>`;
    return;
  }

  function render() {
    main.innerHTML = `
      <div class="section-title">Benutzer (${users.length})</div>
      ${users.map(u => `
        <div class="card card-row" style="margin-bottom:.5rem">
          <div style="flex:1;min-width:0">
            <div style="font-weight:600">${escHtml(u.name)}</div>
            <div style="font-size:.8rem;color:var(--text-muted)">
              @${escHtml(u.username)} · ${escHtml(u.rolle)}${u.stimme ? ' · ' + escHtml(u.stimme) : ''}
            </div>
          </div>
          ${u.id !== currentUser.id ? `
            <button class="btn-icon" onclick="editUser(${u.id})" title="Bearbeiten">&#9998;</button>
            <button class="btn-icon" onclick="deleteUser(${u.id})" title="Löschen">&#x2715;</button>
          ` : '<span style="font-size:.75rem;color:var(--text-muted)">Ich</span>'}
        </div>
      `).join('')}
    `;
  }

  window.editUser = function (id) {
    const u = users.find(x => x.id === id);
    if (!u) return;

    openModal('Benutzer bearbeiten', `
      <div class="form-group"><label>Name</label><input type="text" id="eu-name" value="${escHtml(u.name)}"></div>
      <div class="form-group">
        <label>Rolle</label>
        <select id="eu-rolle">
          <option value="mitglied" ${u.rolle === 'mitglied' ? 'selected' : ''}>Mitglied</option>
          <option value="chorleiter" ${u.rolle === 'chorleiter' ? 'selected' : ''}>Chorleiter</option>
          <option value="admin" ${u.rolle === 'admin' ? 'selected' : ''}>Admin</option>
        </select>
      </div>
      <div class="form-group">
        <label>Stimme (leer = keine)</label>
        <select id="eu-stimme">
          <option value="">– keine –</option>
          ${['Sopran','Sopran 1','Sopran 2','Mezzo','Mezzo 1','Mezzo 2','Alt','Alt 1','Alt 2','Tenor','Tenor 1','Tenor 2','Bass','Bass 1','Bass 2','Männer'].map(s => `<option ${u.stimme === s ? 'selected' : ''}>${s}</option>`).join('')}
        </select>
      </div>
      <div class="form-group"><label>Neues Passwort (leer = unverändert)</label><input type="password" id="eu-pw"></div>
    `, [
      {
        id: 'save', label: 'Speichern', cls: 'btn-primary',
        handler: async () => {
          const payload = {
            name: document.getElementById('eu-name').value.trim(),
            rolle: document.getElementById('eu-rolle').value,
            stimme: document.getElementById('eu-stimme').value || null,
          };
          const pw = document.getElementById('eu-pw').value;
          if (pw) payload.password = pw;

          try {
            await API.put(`/users/${id}`, payload);
            closeModal();
            showToast('Gespeichert', 'success');
            users = await API.get('/users');
            render();
          } catch (e) { showToast(e.message, 'error'); }
        }
      },
      { id: 'cancel', label: 'Abbrechen', handler: closeModal },
    ]);
  };

  window.deleteUser = async function (id) {
    if (!confirm('Benutzer löschen?')) return;
    try {
      await API.delete(`/users/${id}`);
      users = users.filter(x => x.id !== id);
      render();
      showToast('Gelöscht');
    } catch (e) { showToast(e.message, 'error'); }
  };

  render();
}
