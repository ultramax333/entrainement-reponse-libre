(function () {
  'use strict';

  if (typeof document === 'undefined') return;
  const APP = document.getElementById('app');
  const BANK = window.HEP_CHOICE_BANK;
  const ENGINE = window.HEP_CHOICE_ENGINE;
  const state = { index: 0, selected: null, attempts: [], orders: {} };

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
    APP.replaceChildren(card);
  }

  if (ENGINE && ENGINE.validateBank(BANK)) resetOrders();
  render();
}());
