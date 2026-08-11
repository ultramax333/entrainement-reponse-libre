(function () {
  'use strict';

  if (typeof document === 'undefined') return;
  const APP = document.getElementById('app');
  const BANK = window.HEP_CHOICE_BANK;
  const ENGINE = window.HEP_CHOICE_ENGINE;
  const DRIVE = window.HEP_DRIVE_BACKUP;
  const CONFIG = window.HEP_CONFIG || {};
  const STORAGE_KEY = 'hep-choice-feedback/1.0';
  const OAUTH_STORAGE_KEY = 'hep-choice-google-client-id/1.0';
  const state = {
    index: 0, selected: null, attempts: [], orders: {}, feedbacks: {},
    feedbackStatus: '', backupStatus: '', backupBusy: false,
  };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function current() {
    return BANK.questions[state.index] || null;
  }

  function resetOrders() {
    state.orders = Object.fromEntries(BANK.questions.map((question) => [
      question.id,
      ENGINE.shuffled(question.choices),
    ]));
  }

  function loadFeedbacks() {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY));
      state.feedbacks = value && typeof value === 'object' ? value : {};
    } catch (_) {
      state.feedbacks = {};
    }
    if (!CONFIG.GOOGLE_CLIENT_ID) {
      CONFIG.GOOGLE_CLIENT_ID = localStorage.getItem(OAUTH_STORAGE_KEY) || '';
    }
  }

  function persistFeedbacks() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.feedbacks));
  }

  function saveGoogleClientId(input) {
    const clientId = input.value.trim();
    if (!/^[0-9A-Za-z_-]+\.apps\.googleusercontent\.com$/.test(clientId)) {
      state.backupStatus = 'L’identifiant client Google OAuth n’est pas valide.';
      render();
      return;
    }
    CONFIG.GOOGLE_CLIENT_ID = clientId;
    localStorage.setItem(OAUTH_STORAGE_KEY, clientId);
    state.backupStatus = 'Google Drive est configuré sur cet appareil.';
    render();
  }

  function saveQuestionFeedback(questionId, textarea) {
    const comment = textarea.value.trim();
    if (comment) {
      state.feedbacks[questionId] = { comment, updated_at: new Date().toISOString() };
      state.feedbackStatus = 'Feedback enregistré sur cet appareil.';
    } else {
      delete state.feedbacks[questionId];
      state.feedbackStatus = 'Feedback supprimé.';
    }
    persistFeedbacks();
    render();
  }

  function backupDocument() {
    return ENGINE.feedbackDocument(BANK, state.feedbacks, new Date().toISOString());
  }

  function downloadBackup() {
    const blob = new Blob([JSON.stringify(backupDocument(), null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = CONFIG.DRIVE_BACKUP_FILENAME || 'hep-orthographe-feedback.json';
    link.click();
    URL.revokeObjectURL(url);
    state.backupStatus = 'Backup téléchargé.';
    render();
  }

  async function saveToDrive() {
    state.backupBusy = true;
    state.backupStatus = 'Connexion à Google Drive…';
    render();
    try {
      const result = await DRIVE.save(CONFIG, backupDocument());
      state.backupStatus = `Feedback sauvegardé sur Google Drive (${result.name}).`;
    } catch (error) {
      state.backupStatus = error.message;
    } finally {
      state.backupBusy = false;
      render();
    }
  }

  async function restoreFromDrive() {
    state.backupBusy = true;
    state.backupStatus = 'Restauration depuis Google Drive…';
    render();
    try {
      const result = await DRIVE.restore(CONFIG);
      state.feedbacks = ENGINE.restoreFeedback(result.document, BANK);
      persistFeedbacks();
      state.backupStatus = `${Object.keys(state.feedbacks).length} feedback(s) restauré(s) depuis Google Drive.`;
    } catch (error) {
      state.backupStatus = error.message;
    } finally {
      state.backupBusy = false;
      render();
    }
  }

  function choose(choice) {
    if (state.selected != null) return;
    const question = current();
    state.selected = choice;
    state.attempts.push({ question_id: question.id, correct: ENGINE.isCorrect(choice, question) });
    render();
  }

  function next() {
    state.index += 1;
    state.selected = null;
    render();
  }

  function restart() {
    state.index = 0;
    state.selected = null;
    state.attempts = [];
    resetOrders();
    render();
  }

  function renderFeedbackEntry(card, question) {
    const section = element('section', 'feedback-entry');
    const label = element('label', null, 'Feedback sur cette question (facultatif)');
    label.htmlFor = `feedback-${question.id}`;
    const textarea = element('textarea', null);
    textarea.id = `feedback-${question.id}`;
    textarea.rows = 3;
    textarea.maxLength = 1000;
    textarea.placeholder = 'Signale une formulation peu claire, une réponse discutable ou une amélioration.';
    textarea.value = state.feedbacks[question.id] ? state.feedbacks[question.id].comment : '';
    const saveButton = element('button', 'secondary-button', 'Enregistrer le feedback');
    saveButton.type = 'button';
    saveButton.addEventListener('click', () => saveQuestionFeedback(question.id, textarea));
    section.append(label, textarea, saveButton);
    if (state.feedbackStatus) section.append(element('p', 'status-line', state.feedbackStatus));
    card.append(section);
  }

  function renderBackupPanel(card) {
    const panel = element('section', 'backup-panel');
    panel.append(element('h2', null, 'Backup des feedbacks'));
    panel.append(element('p', 'backup-copy', `${Object.keys(state.feedbacks).length} question(s) avec feedback enregistré.`));
    const actions = element('div', 'backup-actions');
    const download = element('button', 'secondary-button', 'Télécharger');
    download.type = 'button';
    download.disabled = state.backupBusy;
    download.addEventListener('click', downloadBackup);
    const saveDrive = element('button', 'secondary-button', 'Sauvegarder sur Google Drive');
    saveDrive.type = 'button';
    saveDrive.disabled = state.backupBusy || !DRIVE.configured(CONFIG);
    saveDrive.addEventListener('click', saveToDrive);
    const restoreDrive = element('button', 'secondary-button', 'Restaurer depuis Google Drive');
    restoreDrive.type = 'button';
    restoreDrive.disabled = state.backupBusy || !DRIVE.configured(CONFIG);
    restoreDrive.addEventListener('click', restoreFromDrive);
    actions.append(download, saveDrive, restoreDrive);
    panel.append(actions);
    if (!DRIVE.configured(CONFIG)) {
      const configBox = element('div', 'oauth-config');
      const label = element('label', null, 'Identifiant client Google OAuth');
      label.htmlFor = 'google-client-id';
      const input = element('input', null);
      input.id = 'google-client-id';
      input.type = 'text';
      input.autocomplete = 'off';
      input.placeholder = '…apps.googleusercontent.com';
      const saveConfig = element('button', 'secondary-button', 'Activer Google Drive');
      saveConfig.type = 'button';
      saveConfig.addEventListener('click', () => saveGoogleClientId(input));
      configBox.append(label, input, saveConfig);
      panel.append(configBox);
      panel.append(element('p', 'status-line', state.backupStatus || 'L’identifiant client est public et reste enregistré uniquement dans ce navigateur.'));
    } else if (state.backupStatus) {
      panel.append(element('p', 'status-line', state.backupStatus));
    }
    card.append(panel);
  }

  function renderSummary() {
    const result = ENGINE.score(state.attempts);
    const card = element('section', 'card summary');
    card.append(element('p', 'eyebrow', 'Séance terminée'));
    card.append(element('h1', null, `${result.correct} / ${BANK.questions.length}`));
    card.append(element('p', 'summary-text', `Tu as répondu correctement à ${result.correct} exercice${result.correct === 1 ? '' : 's'} sur ${BANK.questions.length}.`));
    const button = element('button', 'next-button', 'Recommencer');
    button.type = 'button';
    button.addEventListener('click', restart);
    card.append(button);
    renderBackupPanel(card);
    APP.replaceChildren(card);
  }

  function render() {
    if (!ENGINE || !ENGINE.validateBank(BANK)) {
      APP.replaceChildren(element('p', 'error', 'La banque d’exercices est indisponible.'));
      return;
    }
    if (!current()) {
      renderSummary();
      return;
    }

    const question = current();
    const revealed = state.selected != null;
    const correct = revealed && ENGINE.isCorrect(state.selected, question);
    const card = element('section', 'card');
    const top = element('div', 'topline');
    top.append(element('span', 'eyebrow', 'Orthographe'));
    top.append(element('span', 'progress', `Exercice ${state.index + 1} / ${BANK.questions.length}`));
    card.append(top);
    card.append(element('h1', null, 'Choisis la forme correcte'));
    card.append(element('p', 'sentence', question.prompt));

    const choices = element('div', 'choices');
    choices.setAttribute('role', 'group');
    choices.setAttribute('aria-label', 'Réponses proposées');
    state.orders[question.id].forEach((choice) => {
      const button = element('button', 'choice', choice);
      button.type = 'button';
      if (revealed) {
        button.disabled = true;
        if (ENGINE.isCorrect(choice, question)) button.classList.add('correct-choice');
        else if (choice === state.selected) button.classList.add('wrong-choice');
      }
      button.addEventListener('click', () => choose(choice));
      choices.append(button);
    });
    card.append(choices);
    renderFeedbackEntry(card, question);

    if (revealed) {
      const feedback = element('div', `feedback ${correct ? 'correct' : 'wrong'}`);
      feedback.append(element('h2', null, correct ? 'Correct' : 'À revoir'));
      if (!correct) feedback.append(element('p', null, `Réponse correcte : ${question.answer}`));
      feedback.append(element('h3', null, 'Pourquoi ?'));
      feedback.append(element('p', null, question.application_note));
      const nextButton = element('button', 'next-button', state.index + 1 === BANK.questions.length ? 'Voir le résultat' : 'Question suivante');
      nextButton.type = 'button';
      nextButton.addEventListener('click', next);
      feedback.append(nextButton);
      card.append(feedback);
    }
    renderBackupPanel(card);
    APP.replaceChildren(card);
  }

  if (ENGINE && ENGINE.validateBank(BANK)) {
    loadFeedbacks();
    resetOrders();
  }
  render();
}());
