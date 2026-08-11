// Configuration publique du site autonome.
// Renseigner un client OAuth Web autorisant l’origine https://ultramax333.github.io.
window.HEP_CONFIG = {
  GOOGLE_CLIENT_ID: '',
  DRIVE_BACKUP_FILENAME: 'hep-orthographe-feedback.json',
};

if (typeof module !== 'undefined') module.exports = window.HEP_CONFIG;
