(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.HEP_CHOICE_ENGINE = api;
}(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  function normalize(value) {
    return String(value == null ? '' : value).normalize('NFC').trim();
  }

  function isCorrect(choice, question) {
    return normalize(choice) === normalize(question.answer);
  }

  function score(attempts) {
    const rows = Array.isArray(attempts) ? attempts : [];
    return {
      answered: rows.length,
      correct: rows.filter((item) => item.correct).length,
    };
  }

  function shuffled(values, random) {
    const output = Array.isArray(values) ? values.slice() : [];
    const draw = typeof random === 'function' ? random : Math.random;
    for (let index = output.length - 1; index > 0; index -= 1) {
      const target = Math.floor(draw() * (index + 1));
      [output[index], output[target]] = [output[target], output[index]];
    }
    return output;
  }

  function validateBank(bank) {
    if (!bank || bank.schema_version !== 'hep-choice-bank/1.0') return false;
    if (!Array.isArray(bank.questions) || bank.questions.length === 0) return false;
    return bank.questions.every((question) =>
      typeof question.prompt === 'string' && !question.prompt.includes('___') &&
      Array.isArray(question.choices) && question.choices.length >= 2 && question.choices.length <= 4 &&
      question.choices.filter((choice) => isCorrect(choice, question)).length === 1
    );
  }

  function feedbackDocument(bank, feedbacks, now) {
    const source = feedbacks && typeof feedbacks === 'object' ? feedbacks : {};
    const questions = new Map(bank.questions.map((question) => [question.id, question]));
    const rows = Object.entries(source).flatMap(([questionId, item]) => {
      const question = questions.get(questionId);
      const comment = normalize(item && item.comment);
      if (!question || !comment) return [];
      return [{
        question_id: questionId,
        prompt: question.prompt,
        comment,
        updated_at: item.updated_at || now,
      }];
    });
    return {
      schema_version: 'hep-choice-feedback/1.0',
      bank_release: bank.release,
      saved_at: now,
      feedbacks: rows,
    };
  }

  function restoreFeedback(document, bank) {
    if (!document || document.schema_version !== 'hep-choice-feedback/1.0' || !Array.isArray(document.feedbacks)) {
      throw new Error('Le fichier de sauvegarde n’est pas reconnu.');
    }
    const known = new Set(bank.questions.map((question) => question.id));
    const restored = {};
    document.feedbacks.forEach((item) => {
      if (!item || !known.has(item.question_id)) return;
      const comment = normalize(item.comment);
      if (!comment) return;
      restored[item.question_id] = { comment, updated_at: item.updated_at || document.saved_at || null };
    });
    return restored;
  }

  return { feedbackDocument, isCorrect, normalize, restoreFeedback, score, shuffled, validateBank };
}));
