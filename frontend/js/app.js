// App router & bootstrap
const App = (() => {
  let currentUser = null;
  let currentPage = null;
  let currentStueckId = null;

  async function init() {
    // Check for register route
    const params = new URLSearchParams(window.location.search);
    const inviteCode = params.get('code');
    const path = window.location.pathname;

    if ((path === '/register' || path === '/register/') && inviteCode) {
      document.getElementById('view-register').classList.remove('hidden');
      setupRegister(inviteCode);
      return;
    }

    // Try auto-login from stored token
    if (API.getToken()) {
      try {
        currentUser = await API.me();
        showApp();
        return;
      } catch {
        API.setToken(null);
      }
    }

    showLogin();
  }

  function showLogin() {
    hideAll();
    document.getElementById('view-login').classList.remove('hidden');
    setupLogin();
  }

  function showApp() {
    hideAll();
    document.getElementById('view-app').classList.remove('hidden');

    // Chorleiter-Menü (Stimmmatrix, Auftritte) für Chorleiter, Admin und Superadmin;
    // Benutzerverwaltung nur für Superadmin
    const nav = document.getElementById('main-nav');
    nav.classList.toggle('hidden', !Rollen.canManage(currentUser));
    nav.querySelector('[data-page="benutzer"]')
      .classList.toggle('hidden', !Rollen.isSuperadmin(currentUser));
    nav.querySelectorAll('button').forEach(btn => {
      btn.onclick = () => navigate(btn.dataset.page);
    });

    document.getElementById('logout-btn').onclick = async () => {
      await API.logout();
      currentUser = null;
      showLogin();
    };

    document.getElementById('back-btn').onclick = () => {
      if (currentPage === 'auftritt') navigate('auftritte');
      else navigate('repertoire');
    };

    navigate('repertoire');
  }

  function navigate(page, arg) {
    currentPage = page;
    // Matrix-Ansichten brauchen die volle Breite
    document.getElementById('main-content').classList.toggle('wide', page === 'stimmmatrix');
    document.querySelectorAll('#main-nav button').forEach(btn => {
      const section = page === 'stueck' ? 'repertoire' : page === 'auftritt' ? 'auftritte' : page;
      btn.classList.toggle('active', btn.dataset.page === section);
    });

    switch (page) {
      case 'benutzer': return renderBenutzerverwaltung(currentUser);
      case 'stueck': return renderStueck(arg, currentUser);
      case 'stimmmatrix': return renderStimmmatrix(currentUser);
      case 'auftritte': return renderAuftritte(currentUser);
      case 'auftritt': return renderAuftritt(arg, currentUser);
      default:
        currentPage = 'repertoire';
        return renderRepertoire(currentUser);
    }
  }

  function hideAll() {
    ['view-login', 'view-register', 'view-app'].forEach(id => {
      document.getElementById(id).classList.add('hidden');
    });
  }

  function setupLogin() {
    document.getElementById('login-form').onsubmit = async (e) => {
      e.preventDefault();
      const username = document.getElementById('login-username').value.trim();
      const password = document.getElementById('login-password').value;
      try {
        const res = await API.login(username, password);
        currentUser = { id: res.id, name: res.name, username, rolle: res.rolle };
        // Fetch full profile
        currentUser = await API.me();
        showApp();
      } catch (err) {
        showToast(err.message, 'error');
      }
    };
  }

  function setupRegister(inviteCode) {
    document.getElementById('goto-login').onclick = (e) => {
      e.preventDefault();
      history.pushState({}, '', '/');
      hideAll();
      document.getElementById('view-login').classList.remove('hidden');
      setupLogin();
    };

    document.getElementById('register-form').onsubmit = async (e) => {
      e.preventDefault();
      const stimme = document.getElementById('reg-stimme').value;
      if (!stimme) { showToast('Bitte Stimme wählen', 'error'); return; }

      try {
        const res = await API.post('/auth/register', {
          name: document.getElementById('reg-name').value.trim(),
          username: document.getElementById('reg-username').value.trim(),
          password: document.getElementById('reg-password').value,
          stimme,
          invite_code: inviteCode,
        });
        API.setToken(res.access_token);
        currentUser = await API.me();
        history.pushState({}, '', '/');
        showApp();
      } catch (err) {
        showToast(err.message, 'error');
      }
    };
  }

  // Global navigation
  window.goToStueck = function (id) {
    currentStueckId = id;
    navigate('stueck', id);
  };

  window.goToAuftritt = function (id) {
    navigate('auftritt', id);
  };

  document.addEventListener('DOMContentLoaded', init);
})();
