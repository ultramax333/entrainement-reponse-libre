(function () {
  'use strict';

  if (typeof document === 'undefined') return;
  const APP = document.getElementById('app');
  const BANK = window.HEP_CHOICE_BANK;
  const ENGINE = window.HEP_CHOICE_ENGINE;
  const DRIVE = window.HEP_DRIVE_BACKUP;
  const CONFIG = window.HEP_CONFIG || {};
  const STORAGE_KEY = 'hep-choice-feedback/1.0';
  const MASTERY_STORAGE_KEY = 'hep-choice-mastery/1.0';
  const QCM_PRIORITY_STORAGE_KEY = 'hep-qcm-review-priorities/1.0';
  const OAUTH_STORAGE_KEY = 'hep-choice-google-client-id/1.0';
  const state = {
    screen: 'menu', selectedMechanism: null, sessionQuestions: null,
    sessionLabel: '', index: 0, selected: null,
    attempts: [], orders: {}, feedbacks: {}, feedbackOpen: {},
    mastery: null, qcmPriorities: null,
    feedbackStatus: '', backupStatus: '', backupBusy: false, priorityStatus: '',
  };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function current() {
    return activeQuestions()[state.index] || null;
  }

  function activeQuestions() {
    if (Array.isArray(state.sessionQuestions)) return state.sessionQuestions;
    return state.selectedMechanism
      ? BANK.questions.filter((question) => question.mechanism_id === state.selectedMechanism)
      : BANK.questions;
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
    try {
      state.mastery = ENGINE.normalizeMastery(JSON.parse(localStorage.getItem(MASTERY_STORAGE_KEY)));
    } catch (_) {
      state.mastery = ENGINE.emptyMastery();
    }
    try {
      const imported = JSON.parse(localStorage.getItem(QCM_PRIORITY_STORAGE_KEY));
      const validation = ENGINE.validatePriorityExport(imported, BANK);
      state.qcmPriorities = validation.valid ? validation.document : null;
    } catch (_) {
      state.qcmPriorities = null;
    }
    if (!CONFIG.GOOGLE_CLIENT_ID) {
      CONFIG.GOOGLE_CLIENT_ID = localStorage.getItem(OAUTH_STORAGE_KEY) || '';
    }
  }

  function persistFeedbacks() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.feedbacks));
  }

  function persistMastery() {
    localStorage.setItem(MASTERY_STORAGE_KEY, JSON.stringify(state.mastery));
  }

  function persistQcmPriorities() {
    if (state.qcmPriorities) localStorage.setItem(QCM_PRIORITY_STORAGE_KEY, JSON.stringify(state.qcmPriorities));
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
    const correct = ENGINE.isCorrect(choice, question);
    const answeredAt = new Date().toISOString();
    state.selected = choice;
    state.attempts.push({ question_id: question.id, correct });
    state.mastery = ENGINE.recordAttempt(state.mastery, question, correct, answeredAt);
    persistMastery();
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

  function startRule(mechanismId) {
    state.screen = 'exercise';
    state.selectedMechanism = mechanismId || null;
    state.sessionQuestions = null;
    state.sessionLabel = mechanismId ? '' : 'Toutes les règles';
    restart();
  }

  function startPrioritySession() {
    const questions = ENGINE.buildPrioritySession(BANK, state.mastery, state.qcmPriorities, 20);
    if (!questions.length) {
      state.priorityStatus = 'Aucune règle prioritaire pour le moment. Fais quelques exercices ou importe un résumé QCM.';
      render();
      return;
    }
    state.screen = 'exercise';
    state.selectedMechanism = null;
    state.sessionQuestions = questions;
    state.sessionLabel = 'Mes priorités';
    restart();
  }

  function openRuleMenu() {
    state.screen = 'menu';
    state.index = 0;
    state.selected = null;
    state.attempts = [];
    state.sessionQuestions = null;
    state.sessionLabel = '';
    render();
  }

  async function importQcmPriorities(file) {
    if (!file) return;
    if (file.size > 1024 * 1024) {
      state.priorityStatus = 'Le fichier dépasse 1 Mo et n’est pas un résumé QCM compact.';
      render();
      return;
    }
    try {
      const raw = JSON.parse(await file.text());
      const result = ENGINE.validatePriorityExport(raw, BANK);
      if (!result.valid) throw new Error(result.errors.join(' '));
      if (state.qcmPriorities && state.qcmPriorities.export_id === result.document.export_id) {
        state.priorityStatus = 'Cet export QCM est déjà importé.';
        render();
        return;
      }
      state.qcmPriorities = result.document;
      persistQcmPriorities();
      const ignored = result.unsupported.length;
      state.priorityStatus = `${result.document.priorities.length} règle(s) QCM importée(s)${ignored ? `, ${ignored} sans exercice disponible ignorée(s)` : ''}.`;
    } catch (error) {
      state.priorityStatus = `Import impossible : ${error.message}`;
    }
    render();
  }

  function formatPriority(row) {
    if (row.errors > 0 && row.qcm_factor > 1) return `${row.errors} erreur(s) ici · priorité QCM ${row.qcm_factor.toFixed(2)}`;
    if (row.errors > 0) return `${row.errors} erreur(s) ici sur ${row.attempts} réponse(s)`;
    if (row.qcm_factor > 1) return `priorité QCM ${row.qcm_factor.toFixed(2)}`;
    if (row.attempts > 0) return `${row.attempts} réponse(s), aucune erreur`;
    return 'pas encore travaillée';
  }

  function renderPriorityPanel(card, priorities) {
    const panel = element('section', 'priority-panel');
    panel.append(element('h2', null, 'Règles à revoir'));
    const active = priorities.filter((row) => row.errors > 0 || row.qcm_factor > 1);
    const priorityButton = element('button', 'next-button priority-start', active.length ? `Mes priorités (${Math.min(20, ENGINE.buildPrioritySession(BANK, state.mastery, state.qcmPriorities, 20, () => 0.5).length)} exercices)` : 'Mes priorités');
    priorityButton.type = 'button';
    priorityButton.disabled = active.length === 0;
    priorityButton.addEventListener('click', startPrioritySession);
    panel.append(priorityButton);
    if (active.length) {
      const list = element('ol', 'priority-list');
      active.slice(0, 5).forEach((row) => {
        const item = element('li', null);
        item.append(element('strong', null, row.label));
        item.append(element('span', null, formatPriority(row)));
        list.append(item);
      });
      panel.append(list);
    } else {
      panel.append(element('p', 'status-line', 'Aucune erreur enregistrée et aucun résumé QCM importé.'));
    }
    const importLabel = element('label', 'secondary-button import-label', 'Importer les règles du QCM');
    importLabel.htmlFor = 'qcm-priority-file';
    const fileInput = element('input', 'visually-hidden');
    fileInput.id = 'qcm-priority-file';
    fileInput.type = 'file';
    fileInput.accept = '.json,application/json';
    fileInput.addEventListener('change', () => importQcmPriorities(fileInput.files && fileInput.files[0]));
    panel.append(importLabel, fileInput);
    if (state.qcmPriorities) {
      const date = new Date(state.qcmPriorities.generated_at).toLocaleString('fr-CH');
      panel.append(element('p', 'status-line', `Export QCM du ${date} · ${state.qcmPriorities.priorities.length} règle(s) compatible(s).`));
    }
    if (state.priorityStatus) panel.append(element('p', 'status-line', state.priorityStatus));
    card.append(panel);
  }

  function renderRuleMenu() {
    const card = element('section', 'card rule-menu');
    card.append(element('p', 'eyebrow', 'Entraînement ciblé'));
    card.append(element('h1', null, 'Choisis une règle'));
    card.append(element('p', 'summary-text', 'Lance toute la banque ou travaille une seule règle.'));
    const priorities = ENGINE.rulePriorities(BANK, state.mastery, state.qcmPriorities);
    renderPriorityPanel(card, priorities);
    const choices = element('div', 'rule-choices');
    const allButton = element('button', 'rule-choice all-rules', `Toutes les règles (${BANK.questions.length} exercices)`);
    allButton.type = 'button';
    allButton.addEventListener('click', () => startRule(null));
    choices.append(allButton);
    priorities.forEach((rule) => {
      const button = element('button', 'rule-choice', `${rule.label} (${rule.questions})`);
      button.type = 'button';
      const meta = element('span', 'rule-meta', formatPriority(rule));
      button.append(meta);
      button.addEventListener('click', () => startRule(rule.mechanism_id));
      choices.append(button);
    });
    card.append(choices);
    renderBackupPanel(card);
    APP.replaceChildren(card);
  }

  function renderFeedbackEntry(card, question) {
    const section = element('section', 'feedback-entry');
    const hasFeedback = Boolean(state.feedbacks[question.id]);
    const toggle = element('button', 'link-button feedback-toggle', hasFeedback ? 'Modifier le feedback' : 'Ajouter un feedback');
    toggle.type = 'button';
    toggle.addEventListener('click', () => {
      state.feedbackOpen[question.id] = !state.feedbackOpen[question.id];
      render();
    });
    section.append(toggle);
    if (!state.feedbackOpen[question.id] && !hasFeedback) {
      card.append(section);
      return;
    }
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
    const questions = activeQuestions();
    const card = element('section', 'card summary');
    card.append(element('p', 'eyebrow', 'Séance terminée'));
    card.append(element('h1', null, `${result.correct} / ${questions.length}`));
    card.append(element('p', 'summary-text', `Tu as répondu correctement à ${result.correct} exercice${result.correct === 1 ? '' : 's'} sur ${questions.length}.`));
    const button = element('button', 'next-button', 'Recommencer');
    button.type = 'button';
    button.addEventListener('click', restart);
    card.append(button);
    const menuButton = element('button', 'secondary-button', 'Choisir une autre règle');
    menuButton.type = 'button';
    menuButton.addEventListener('click', openRuleMenu);
    card.append(menuButton);
    renderBackupPanel(card);
    APP.replaceChildren(card);
  }

  function render() {
    if (!ENGINE || !ENGINE.validateBank(BANK)) {
      APP.replaceChildren(element('p', 'error', 'La banque d’exercices est indisponible.'));
      return;
    }
    if (state.screen === 'menu') {
      renderRuleMenu();
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
    top.append(element('span', 'eyebrow', state.sessionLabel || 'Orthographe'));
    top.append(element('span', 'progress', `Exercice ${state.index + 1} / ${activeQuestions().length}`));
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

    if (revealed) {
      const correction = question.correction;
      const feedback = element('section', `feedback ${correct ? 'correct' : 'wrong'}`);
      feedback.append(element('h2', null, correct ? 'Correct.' : 'Incorrect.'));
      if (!correct) feedback.append(element('p', 'answer-line', `Réponse correcte : ${question.answer}`));
      if (!correct) {
        const diagnostic = correction.diagnostics[state.selected];
        const diagnosticCard = element('section', 'diagnostic-card');
        diagnosticCard.append(element('h3', null, `Ce choix suggère : ${diagnostic.label}`));
        diagnosticCard.append(element('p', null, diagnostic.likely_reasoning));
        diagnosticCard.append(element('p', 'diagnostic-break', `Où le raisonnement dévie : ${diagnostic.reasoning_break}`));
        diagnosticCard.append(element('p', null, `Le test à faire : ${diagnostic.decision_test}`));
        diagnosticCard.append(element('p', null, `Le bon réflexe : ${diagnostic.repair_strategy}`));
        feedback.append(diagnosticCard);
      }
      feedback.append(element('p', 'correction-note', correction.application));
      feedback.append(element('p', 'correction-conclusion', correction.conclusion));
      const details = element('details', 'correction-details');
      details.append(element('summary', null, 'Voir le raisonnement détaillé'));
      details.append(element('h3', null, 'Règle'));
      details.append(element('p', null, correction.rule));
      details.append(element('h3', null, 'Méthode'));
      const steps = element('ol', 'correction-steps');
      correction.method_steps.forEach((step) => steps.append(element('li', null, step)));
      details.append(steps);
      details.append(element('h3', null, 'Pourquoi chaque forme ?'));
      const reasons = element('dl', 'choice-reasons');
      question.choices.forEach((choice) => {
        reasons.append(element('dt', null, choice));
        reasons.append(element('dd', null, correction.why[choice].replaceAll('`', '')));
      });
      details.append(reasons);
      feedback.append(details);
      const nextButton = element('button', 'next-button', state.index + 1 === activeQuestions().length ? 'Voir le résultat' : 'Question suivante');
      nextButton.type = 'button';
      nextButton.addEventListener('click', next);
      feedback.append(nextButton);
      card.append(feedback);
    }
    renderFeedbackEntry(card, question);
    const menuButton = element('button', 'link-button', 'Changer de règle');
    menuButton.type = 'button';
    menuButton.addEventListener('click', openRuleMenu);
    card.append(menuButton);
    APP.replaceChildren(card);
  }

  if (ENGINE && ENGINE.validateBank(BANK)) {
    loadFeedbacks();
    resetOrders();
  }
  render();
}());
