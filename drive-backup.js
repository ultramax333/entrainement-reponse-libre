(function (root, factory) {
  const api = factory(root);
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.HEP_DRIVE_BACKUP = api;
}(typeof window !== 'undefined' ? window : globalThis, function (root) {
  'use strict';

  const SCOPE = 'https://www.googleapis.com/auth/drive.file';
  const API = 'https://www.googleapis.com/drive/v3';
  const UPLOAD_API = 'https://www.googleapis.com/upload/drive/v3';

  function configured(config) {
    return Boolean(config && String(config.GOOGLE_CLIENT_ID || '').trim());
  }

  function requireGoogle() {
    if (!root.google || !root.google.accounts || !root.google.accounts.oauth2) {
      throw new Error('La connexion Google n’est pas encore disponible. Recharge la page et réessaie.');
    }
  }

  function accessToken(config) {
    if (!configured(config)) throw new Error('Le client Google Drive n’est pas configuré.');
    requireGoogle();
    return new Promise((resolve, reject) => {
      const client = root.google.accounts.oauth2.initTokenClient({
        client_id: config.GOOGLE_CLIENT_ID,
        scope: SCOPE,
        callback: (response) => {
          if (response && response.access_token) resolve(response.access_token);
          else reject(new Error(response && response.error_description ? response.error_description : 'Connexion Google annulée.'));
        },
        error_callback: () => reject(new Error('La fenêtre de connexion Google a été fermée.')),
      });
      client.requestAccessToken({ prompt: '' });
    });
  }

  async function driveRequest(url, token, options) {
    const response = await fetch(url, {
      ...(options || {}),
      headers: {
        Authorization: `Bearer ${token}`,
        ...((options && options.headers) || {}),
      },
    });
    if (!response.ok) {
      let detail = '';
      try { detail = (await response.json()).error.message || ''; } catch (_) { detail = ''; }
      throw new Error(detail || `Google Drive a répondu ${response.status}.`);
    }
    if (response.status === 204) return null;
    return response.json();
  }

  async function findBackup(token, filename) {
    const safeName = String(filename).replace(/'/g, "\\'");
    const params = new URLSearchParams({
      q: `name = '${safeName}' and trashed = false`,
      spaces: 'drive',
      orderBy: 'modifiedTime desc',
      pageSize: '1',
      fields: 'files(id,name,modifiedTime)',
    });
    const result = await driveRequest(`${API}/files?${params}`, token);
    return result.files && result.files[0] ? result.files[0] : null;
  }

  async function save(config, document) {
    const token = await accessToken(config);
    const filename = config.DRIVE_BACKUP_FILENAME || 'hep-orthographe-feedback.json';
    let file = await findBackup(token, filename);
    if (!file) {
      file = await driveRequest(`${API}/files?fields=id,name`, token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: filename, mimeType: 'application/json' }),
      });
    }
    await driveRequest(`${UPLOAD_API}/files/${encodeURIComponent(file.id)}?uploadType=media`, token, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json; charset=UTF-8' },
      body: JSON.stringify(document),
    });
    return { id: file.id, name: filename };
  }

  async function restore(config) {
    const token = await accessToken(config);
    const filename = config.DRIVE_BACKUP_FILENAME || 'hep-orthographe-feedback.json';
    const file = await findBackup(token, filename);
    if (!file) throw new Error('Aucune sauvegarde de feedback n’a été trouvée sur Google Drive.');
    const document = await driveRequest(`${API}/files/${encodeURIComponent(file.id)}?alt=media`, token);
    return { file, document };
  }

  return { configured, save, restore };
}));
