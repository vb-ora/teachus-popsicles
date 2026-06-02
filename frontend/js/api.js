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
