function openModal(title, contentHTML, actions) {
  closeModal();
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'active-modal';

  const actionsHTML = (actions || [])
    .map(a => `<button class="btn ${a.cls || 'btn-secondary'}" data-action="${a.id}">${a.label}</button>`)
    .join('');

  overlay.innerHTML = `
    <div class="modal">
      <h3>${title}</h3>
      <div id="modal-body">${contentHTML}</div>
      <div class="modal-actions">${actionsHTML}</div>
    </div>
  `;

  overlay.addEventListener('click', e => {
    if (e.target === overlay) closeModal();
  });

  (actions || []).forEach(a => {
    overlay.querySelector(`[data-action="${a.id}"]`)
      ?.addEventListener('click', () => a.handler(overlay));
  });

  document.getElementById('modal-container').appendChild(overlay);
  return overlay;
}

function closeModal() {
  document.getElementById('active-modal')?.remove();
}
