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

  return { normalize, isCorrect, score, shuffled, validateBank };
}));
