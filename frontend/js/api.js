// Rollen: superadmin > admin > chorleiter / mitglied
const Rollen = {
  isSuperadmin: (u) => u?.rolle === 'superadmin',
  // Darf Repertoire, Stimmmatrix und Auftritte verwalten
  canManage: (u) => ['superadmin', 'admin', 'chorleiter'].includes(u?.rolle),
  // Singt im Chor (Chorleiter nicht)
  isSaenger: (u) => ['superadmin', 'admin', 'mitglied'].includes(u?.rolle),
};

// Thin API wrapper
const API = (() => {
  let _token = localStorage.getItem('token') || null;

  function setToken(t) {
    _token = t;
    if (t) localStorage.setItem('token', t);
    else localStorage.removeItem('token');
  }

  function getToken() { return _token; }

  async function request(method, path, body, isForm = false) {
    const headers = {};
    if (_token) headers['Authorization'] = `Bearer ${_token}`;

    const opts = { method, headers };
    if (body) {
      if (isForm) {
        opts.body = body; // FormData
      } else {
        headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
      }
    }

    const res = await fetch(`/api${path}`, opts);
    if (res.status === 204) return null;

    let data;
    try { data = await res.json(); } catch { data = null; }

    if (!res.ok) {
      const msg = data?.detail || `Fehler ${res.status}`;
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    return data;
  }

  return {
    setToken, getToken,
    get: (path) => request('GET', path),
    post: (path, body) => request('POST', path, body),
    put: (path, body) => request('PUT', path, body),
    delete: (path) => request('DELETE', path),
    postForm: (path, formData) => request('POST', path, formData, true),

    // Datei (z.B. PDF) mit Auth-Header laden und als Download anbieten
    async download(path, fallbackName) {
      const headers = {};
      if (_token) headers['Authorization'] = `Bearer ${_token}`;
      const res = await fetch(`/api${path}`, { headers });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Fehler ${res.status}`);
      }
      const cd = res.headers.get('Content-Disposition') || '';
      const m = cd.match(/filename\*=UTF-8''([^;]+)/);
      const name = m ? decodeURIComponent(m[1]) : fallbackName;
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },

    // Auth
    async login(username, password) {
      const fd = new FormData();
      fd.append('username', username);
      fd.append('password', password);
      const res = await fetch('/api/auth/login', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || 'Login fehlgeschlagen');
      setToken(data.access_token);
      return data;
    },

    async logout() {
      await fetch('/api/auth/logout', { method: 'POST' });
      setToken(null);
    },

    async me() { return request('GET', '/auth/me'); },
  };
})();
