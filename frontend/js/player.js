// Audio Player component
function createPlayer(audio, currentUser, onMarkierungSaved, onKapitelSaved) {
  let audioEl = null;
  let ausschnittStart = null;
  let isPlaying = false;
  let ausschnittEnd = null;
  let ausschnittPlayEnd = null;

  function formatTime(s) {
    if (!s && s !== 0) return '--:--';
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  }

  function render() {
    const canManage = currentUser.rolle === 'admin' || currentUser.rolle === 'chorleiter';
    const bezeichnung = audio.bezeichnung ? ` – ${audio.bezeichnung}` : '';

    const markierungenHTML = audio.markierungen?.length
      ? audio.markierungen.map(m => `
        <div class="markierung-item ${m.ist_oeffentlich ? 'oeffentlich' : ''}" data-id="${m.id}">
          <button class="btn btn-sm" style="flex-shrink:0" onclick="playerPlayMarkierung(${m.id})">&#9654;</button>
          <div style="flex:1;min-width:0">
            <div class="markierung-name">${escHtml(m.name)}</div>
            <div class="markierung-time">${formatTime(m.start_sekunden)} – ${formatTime(m.ende_sekunden)}</div>
          </div>
          ${m.ist_oeffentlich ? '<span class="markierung-badge">Öffentlich</span>' : ''}
          ${m.ist_eigen ? `<button class="btn-icon" onclick="playerDeleteMarkierung(${m.id})" title="Löschen">&#x2715;</button>` : ''}
        </div>
      `).join('')
      : '<div class="text-muted" style="font-size:0.85rem">Keine Markierungen</div>';

    const kapitelHTML = audio.kapitel?.length
      ? `<div class="kapitel-list">${audio.kapitel.map(k => `
        <div class="kapitel-item" data-kid="${k.id}" onclick="playerSeekTo(${k.start_sekunden})" title="${escHtml(k.name)} — ${formatTime(k.start_sekunden)}">
          <span class="kapitel-name">${escHtml(k.name)}</span>
          <span class="kapitel-time">${formatTime(k.start_sekunden)}</span>
          ${canManage ? `<button class="btn-icon" onclick="event.stopPropagation();playerDeleteKapitel(${k.id})" title="Löschen">&#x2715;</button>` : ''}
        </div>
      `).join('')}</div>`
      : '';

    return `
      <div class="player-card" id="player-root">
        <div class="player-title">${escHtml(audio.stimme)}${escHtml(bezeichnung)}</div>
        <div class="player-subtitle">${audio.typ === 'gesungen' ? 'Gesungen' : 'Instrumental'}${audio.dauer_sekunden ? ' · ' + formatTime(audio.dauer_sekunden) : ''}</div>

        <div class="progress-container" id="progress-container">
          <div class="progress-track" id="progress-track">
            <div class="progress-fill" id="progress-fill" style="width:0%"></div>
            <div class="progress-thumb" id="progress-thumb" style="left:0%"></div>
          </div>
          ${(audio.kapitel || []).map(k => {
            if (!audio.dauer_sekunden) return '';
            const pct = (k.start_sekunden / audio.dauer_sekunden) * 100;
            const label = `${escHtml(k.name)} — ${formatTime(k.start_sekunden)}`;
            return `<div class="chapter-marker" data-label="${label}" style="left:${pct}%" onclick="playerSeekTo(${k.start_sekunden})"></div>`;
          }).join('')}
        </div>

        <div class="player-controls">
          <button class="play-btn" id="play-btn" onclick="playerToggle()">&#9654;</button>
          <span class="time-display" id="time-display">0:00 / ${formatTime(audio.dauer_sekunden)}</span>
          <button class="btn btn-sm btn-secondary" id="ausschnitt-btn" onclick="playerAusschnittToggle()">Ausschnitt starten</button>
          <div style="display:flex;align-items:center;gap:.5rem">
            <label style="font-size:.8rem;color:var(--text-muted)">Lautstärke</label>
            <input type="range" id="volume-slider" min="0" max="1" step="0.05" value="1" style="width:80px" oninput="playerSetVolume(this.value)">
          </div>
        </div>

        <div id="ausschnitt-form" class="ausschnitt-form hidden">
          <div class="ausschnitt-info" id="ausschnitt-info"></div>
          <div class="form-group" style="margin-bottom:.5rem">
            <label>Name für diese Stelle</label>
            <input type="text" id="ausschnitt-name" placeholder="z.B. Einsatz Sopran">
          </div>
          ${canManage ? `
          <div class="form-group" style="margin-bottom:.5rem">
            <label style="display:flex;align-items:center;gap:.5rem">
              <input type="checkbox" id="ausschnitt-oeffentlich"> Öffentlich
            </label>
          </div>` : ''}
          <div class="flex gap-1">
            <button class="btn btn-primary btn-sm" onclick="playerSaveMarkierung()">Speichern</button>
            <button class="btn btn-secondary btn-sm" onclick="playerCancelAusschnitt()">Abbrechen</button>
          </div>
        </div>

        ${kapitelHTML ? `<div class="section-title" style="margin-top:.75rem">Kapitel</div>${kapitelHTML}` : ''}

        ${canManage ? `
        <div class="mt-1" style="display:flex;gap:.5rem;flex-wrap:wrap">
          <button class="admin-btn" onclick="playerAddKapitel()">+ Kapitel anlegen</button>
          ${audio.kapitel?.length ? `<button class="admin-btn" onclick="playerUebertragenKapitel()">Kapitel übertragen</button>` : ''}
        </div>` : ''}

        <div class="section-title">Markierungen</div>
        <div id="markierungen-list">${markierungenHTML}</div>
      </div>

      <audio id="audio-el" src="/files/${audio.id}" preload="metadata"></audio>
    `;
  }

  // Expose to window for inline onclick handlers
  window.playerToggle = function () {
    if (!audioEl) return;
    if (isPlaying) { audioEl.pause(); }
    else { audioEl.play(); }
  };

  window.playerSeekTo = function (sec) {
    if (!audioEl) return;
    audioEl.currentTime = sec;
  };

  window.playerSetVolume = function (val) {
    if (audioEl) audioEl.volume = parseFloat(val);
  };

  window.playerAusschnittToggle = function () {
    const btn = document.getElementById('ausschnitt-btn');
    const form = document.getElementById('ausschnitt-form');
    if (!audioEl) return;

    if (ausschnittStart === null) {
      ausschnittStart = audioEl.currentTime;
      btn.textContent = 'Ausschnitt stoppen';
      btn.classList.remove('btn-secondary');
      btn.classList.add('btn-primary');
    } else {
      ausschnittEnd = audioEl.currentTime;
      btn.textContent = 'Ausschnitt starten';
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-secondary');
      const info = document.getElementById('ausschnitt-info');
      info.textContent = `Von ${formatTime(ausschnittStart)} bis ${formatTime(ausschnittEnd)}`;
      form.classList.remove('hidden');
    }
  };

  window.playerCancelAusschnitt = function () {
    ausschnittStart = null;
    ausschnittEnd = null;
    document.getElementById('ausschnitt-form').classList.add('hidden');
    document.getElementById('ausschnitt-btn').textContent = 'Ausschnitt starten';
  };

  window.playerSaveMarkierung = async function () {
    const name = document.getElementById('ausschnitt-name').value.trim();
    if (!name) { showToast('Bitte Namen eingeben', 'error'); return; }
    const oeffentlich = document.getElementById('ausschnitt-oeffentlich')?.checked || false;

    try {
      const m = await API.post('/markierungen', {
        audio_id: audio.id,
        name,
        start_sekunden: ausschnittStart,
        ende_sekunden: ausschnittEnd,
        ist_oeffentlich: oeffentlich,
      });
      showToast('Markierung gespeichert', 'success');
      playerCancelAusschnitt();
      if (onMarkierungSaved) onMarkierungSaved(m);
    } catch (e) {
      showToast(e.message, 'error');
    }
  };

  window.playerDeleteMarkierung = async function (id) {
    if (!confirm('Markierung löschen?')) return;
    try {
      await API.delete(`/markierungen/${id}`);
      document.querySelector(`.markierung-item[data-id="${id}"]`)?.remove();
      showToast('Gelöscht');
    } catch (e) {
      showToast(e.message, 'error');
    }
  };

  window.playerPlayMarkierung = function (id) {
    const m = audio.markierungen?.find(x => x.id === id);
    if (!m || !audioEl) return;
    audioEl.currentTime = m.start_sekunden;
    ausschnittPlayEnd = m.ende_sekunden;
    audioEl.play();
  };

  window.playerDeleteKapitel = async function (id) {
    if (!confirm('Kapitel löschen?')) return;
    try {
      await API.delete(`/kapitel/${id}`);
      document.querySelector(`.kapitel-item[data-kid="${id}"]`)?.remove();
      showToast('Gelöscht');
    } catch (e) {
      showToast(e.message, 'error');
    }
  };

  window.playerAddKapitel = function () {
    const currentTime = audioEl ? audioEl.currentTime : 0;
    openModal('Kapitel anlegen', `
      <div class="form-group">
        <label>Name</label>
        <input type="text" id="kapitel-name" placeholder="z.B. Strophe 1">
      </div>
      <div class="form-group">
        <label>Startzeit (Sekunden)</label>
        <input type="number" id="kapitel-time" step="0.1" value="${currentTime.toFixed(1)}">
      </div>
    `, [
      {
        id: 'save', label: 'Speichern', cls: 'btn-primary',
        handler: async () => {
          const name = document.getElementById('kapitel-name').value.trim();
          const start = parseFloat(document.getElementById('kapitel-time').value);
          if (!name) { showToast('Name fehlt', 'error'); return; }
          try {
            const k = await API.post('/kapitel', { audio_id: audio.id, name, start_sekunden: start });
            closeModal();
            showToast('Kapitel angelegt', 'success');

            // Ask to transfer
            const otherAudios = await API.get(`/audios/stueck/${audio.stueck_id}`);
            const others = otherAudios.filter(a => a.id !== audio.id);
            if (others.length > 0) {
              _showTransferModal(k, others);
            }
            if (onKapitelSaved) onKapitelSaved(k);
          } catch (e) {
            showToast(e.message, 'error');
          }
        }
      },
      { id: 'cancel', label: 'Abbrechen', handler: closeModal },
    ]);
  };

  function _showTransferModal(kapitel, others) {
    const checkboxes = others.map(a =>
      `<label class="checklist-item">
        <input type="checkbox" value="${a.id}">
        ${escHtml(a.stimme)}${a.bezeichnung ? ' – ' + escHtml(a.bezeichnung) : ''} (${a.typ})
      </label>`
    ).join('');

    openModal('Kapitel übertragen', `
      <p style="font-size:.9rem;margin-bottom:.75rem">Kapitel „${escHtml(kapitel.name)}" auf weitere Audios übertragen?</p>
      <div>${checkboxes}</div>
    `, [
      {
        id: 'transfer', label: 'Übertragen', cls: 'btn-primary',
        handler: async (overlay) => {
          const checked = [...overlay.querySelectorAll('input[type=checkbox]:checked')].map(x => parseInt(x.value));
          if (!checked.length) { closeModal(); return; }
          try {
            await API.post(`/kapitel/${kapitel.id}/uebertragen`, { ziel_audio_ids: checked });
            showToast(`Auf ${checked.length} Audio(s) übertragen`, 'success');
          } catch (e) {
            showToast(e.message, 'error');
          }
          closeModal();
        }
      },
      { id: 'skip', label: 'Überspringen', handler: closeModal },
    ]);
  }

  function _audioLabel(a) {
    const typ = a.typ === 'gesungen' ? 'Gesungen' : 'Instrumental';
    return `${escHtml(a.stimme)} – ${typ}${a.bezeichnung ? ' – ' + escHtml(a.bezeichnung) : ''}`;
  }

  function _transferSuccess(res) {
    const parts = [];
    if (res.kopiert)      parts.push(`${res.kopiert} Kapitel übertragen`);
    if (res.uebersprungen) parts.push(`${res.uebersprungen} übersprungen`);
    showToast(parts.join(', ') || 'Fertig', 'success');
  }

  async function _doTransfer(zielIds, modus) {
    try {
      const res = await API.post(`/kapitel/audio/${audio.id}/uebertragen`, {
        ziel_audio_ids: zielIds,
        modus,
      });

      // Konflikte beim ersten Aufruf (skip) anzeigen
      if (modus === 'skip' && res.konflikte && res.konflikte.length) {
        const liste = res.konflikte.map(k =>
          `<li><strong>${k.label}</strong>: ${k.namen.map(n => escHtml(n)).join(', ')}</li>`
        ).join('');
        closeModal();
        openModal('Konflikte erkannt', `
          <p style="font-size:.9rem;margin-bottom:.5rem">
            Bei folgenden Audios existieren bereits Kapitel mit gleichen Namen:
          </p>
          <ul style="font-size:.85rem;margin:.5rem 0 .75rem 1.25rem;line-height:1.6">${liste}</ul>
          <p style="font-size:.9rem">Was soll mit diesen Konflikten passieren?</p>
        `, [
          {
            id: 'overwrite', label: 'Überschreiben', cls: 'btn-primary',
            handler: async () => { closeModal(); await _doTransfer(zielIds, 'overwrite'); },
          },
          {
            id: 'skip', label: 'Überspringen',
            handler: () => { closeModal(); _transferSuccess(res); },
          },
          { id: 'cancel', label: 'Abbrechen', handler: closeModal },
        ]);
        return;
      }

      closeModal();
      _transferSuccess(res);
    } catch (e) {
      showToast(e.message, 'error');
    }
  }

  window.playerUebertragenKapitel = async function () {
    let alleAudios;
    try {
      alleAudios = await API.get(`/audios/stueck/${audio.stueck_id}`);
    } catch (e) {
      showToast(e.message, 'error');
      return;
    }

    const others = alleAudios.filter(a => a.id !== audio.id);
    if (!others.length) {
      showToast('Keine weiteren Audios vorhanden', 'error');
      return;
    }

    const checkboxes = others.map(a =>
      `<label class="checklist-item">
        <input type="checkbox" class="uebertragen-check" value="${a.id}">
        ${_audioLabel(a)}
      </label>`
    ).join('');

    openModal('Kapitel übertragen', `
      <p style="font-size:.9rem;margin-bottom:.75rem">
        Alle Kapitel von <strong>${escHtml(audio.stimme)}</strong> auf weitere Audios übertragen:
      </p>
      <div style="display:flex;gap:.5rem;margin-bottom:.75rem">
        <button class="btn btn-sm btn-secondary"
          onclick="document.querySelectorAll('.uebertragen-check').forEach(c=>c.checked=true)">
          Alle auswählen
        </button>
        <button class="btn btn-sm btn-secondary"
          onclick="document.querySelectorAll('.uebertragen-check').forEach(c=>c.checked=false)">
          Keine auswählen
        </button>
      </div>
      <div>${checkboxes}</div>
    `, [
      {
        id: 'transfer', label: 'Übertragen', cls: 'btn-primary',
        handler: async (overlay) => {
          const checked = [...overlay.querySelectorAll('.uebertragen-check:checked')]
            .map(x => parseInt(x.value));
          if (!checked.length) { showToast('Keine Audios ausgewählt', 'error'); return; }
          await _doTransfer(checked, 'skip');
        },
      },
      { id: 'cancel', label: 'Abbrechen', handler: closeModal },
    ]);
  };

  function initAudio() {
    audioEl = document.getElementById('audio-el');
    if (!audioEl) return;

    audioEl.addEventListener('play', () => {
      isPlaying = true;
      document.getElementById('play-btn').innerHTML = '&#9646;&#9646;';
    });
    audioEl.addEventListener('pause', () => {
      isPlaying = false;
      document.getElementById('play-btn').innerHTML = '&#9654;';
    });
    audioEl.addEventListener('ended', () => {
      isPlaying = false;
      document.getElementById('play-btn').innerHTML = '&#9654;';
      ausschnittPlayEnd = null;
    });

    audioEl.addEventListener('timeupdate', () => {
      if (ausschnittPlayEnd !== null && audioEl.currentTime >= ausschnittPlayEnd) {
        audioEl.pause();
        audioEl.currentTime = ausschnittPlayEnd;
        ausschnittPlayEnd = null;
        return;
      }
      updateProgress();
    });

    audioEl.addEventListener('loadedmetadata', () => {
      const dur = audioEl.duration;
      if (dur && !audio.dauer_sekunden) {
        audio.dauer_sekunden = dur;
        const disp = document.getElementById('time-display');
        if (disp) disp.textContent = `0:00 / ${formatTime(dur)}`;
      }
      updateProgress();
    });

    const track = document.getElementById('progress-track');
    if (track) {
      track.addEventListener('click', e => {
        const rect = track.getBoundingClientRect();
        const ratio = (e.clientX - rect.left) / rect.width;
        if (audioEl.duration) {
          audioEl.currentTime = ratio * audioEl.duration;
        }
      });
    }
  }

  function updateProgress() {
    if (!audioEl || !audioEl.duration) return;
    const pct = (audioEl.currentTime / audioEl.duration) * 100;
    const fill = document.getElementById('progress-fill');
    const thumb = document.getElementById('progress-thumb');
    const disp = document.getElementById('time-display');
    if (fill) fill.style.width = `${pct}%`;
    if (thumb) thumb.style.left = `${pct}%`;
    if (disp) disp.textContent = `${formatTime(audioEl.currentTime)} / ${formatTime(audioEl.duration)}`;
  }

  return { render, initAudio };
}

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
