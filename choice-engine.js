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

  function pathKey(item, generic) {
    const detail = generic ? '' : String(item && item.detail_id || '');
    const tense = generic ? '' : String(item && item.tense_id || '');
    return [String(item && item.family || ''), String(item && item.mechanism_id || ''), detail, tense].join('|');
  }

  function emptyMastery() {
    return { schema_version: 'hep-choice-mastery/1.0', rules: {} };
  }

  function normalizeMastery(value) {
    if (!value || value.schema_version !== 'hep-choice-mastery/1.0' || !value.rules || typeof value.rules !== 'object') {
      return emptyMastery();
    }
    return value;
  }

  function recordAttempt(profile, question, correct, now) {
    const source = normalizeMastery(profile);
    const result = { schema_version: source.schema_version, rules: { ...source.rules } };
    const key = pathKey(question);
    const previous = source.rules[key] || {};
    result.rules[key] = {
      family: question.family,
      mechanism_id: question.mechanism_id,
      detail_id: question.detail_id || null,
      tense_id: question.tense_id || null,
      attempts: Number(previous.attempts || 0) + 1,
      correct: Number(previous.correct || 0) + (correct ? 1 : 0),
      errors: Number(previous.errors || 0) + (correct ? 0 : 1),
      current_correct_streak: correct ? Number(previous.current_correct_streak || 0) + 1 : 0,
      last_answered_at: now,
      last_error_at: correct ? previous.last_error_at || null : now,
    };
    return result;
  }

  function localNeed(row) {
    const attempts = Number(row && row.attempts || 0);
    const errors = Number(row && row.errors || 0);
    if (!attempts) return { failure_rate: 0, confidence: 0, factor: 1 };
    const failureRate = (errors + 1) / (attempts + 4);
    const confidence = Math.min(1, attempts / 6);
    const streak = Math.min(2, Number(row && row.current_correct_streak || 0));
    const recovery = 1 - 0.2 * streak;
    return {
      failure_rate: failureRate,
      confidence,
      recovery,
      factor: 1 + 1.5 * failureRate * confidence * recovery,
    };
  }

  function priorityIndex(document) {
    const index = {};
    if (!document || !Array.isArray(document.priorities)) return index;
    document.priorities.forEach((row) => {
      const key = pathKey(row);
      index[key] = Math.max(Number(index[key] || 1), Number(row.priority || 1));
      if (!row.detail_id && !row.tense_id) index[pathKey(row, true)] = index[key];
    });
    return index;
  }

  function priorityForQuestion(question, qcmIndex) {
    return Number(qcmIndex[pathKey(question)] || qcmIndex[pathKey(question, true)] || 1);
  }

  function rulePriorities(bank, profile, qcmDocument) {
    const mastery = normalizeMastery(profile);
    const qcm = priorityIndex(qcmDocument);
    const rules = new Map();
    bank.questions.forEach((question) => {
      const mechanismKey = pathKey(question, true);
      const qcmFactor = priorityForQuestion(question, qcm);
      const previous = rules.get(mechanismKey) || {
        family: question.family,
        mechanism_id: question.mechanism_id,
        label: question.rule_label || question.mechanism_id,
        questions: 0, attempts: 0, errors: 0, current_correct_streak: 0,
        local_factor: 1, qcm_factor: 1, adjusted_qcm_factor: 1, priority: 1,
        _paths: new Set(),
      };
      previous.questions += 1;
      const exactKey = pathKey(question);
      if (!previous._paths.has(exactKey)) {
        const row = mastery.rules[exactKey] || {};
        const need = localNeed(row);
        previous.attempts += Number(row.attempts || 0);
        previous.errors += Number(row.errors || 0);
        previous.current_correct_streak = Math.max(previous.current_correct_streak, Number(row.current_correct_streak || 0));
        previous.local_factor = Math.max(previous.local_factor, need.factor);
        previous._paths.add(exactKey);
      }
      previous.qcm_factor = Math.max(previous.qcm_factor, qcmFactor);
      rules.set(mechanismKey, previous);
    });
    return Array.from(rules.values()).map((row) => {
      const failureRate = row.attempts ? (row.errors + 1) / (row.attempts + 4) : 0;
      const confidence = Math.min(1, row.attempts / 6);
      const reliableSuccess = row.attempts >= 6 ? (1 - failureRate) * confidence : 0;
      const recoveryFactor = Math.max(0.60, 1 - 0.40 * reliableSuccess);
      const adjustedQcmFactor = 1 + (row.qcm_factor - 1) * recoveryFactor;
      const output = { ...row, adjusted_qcm_factor: adjustedQcmFactor };
      delete output._paths;
      output.priority = Math.max(output.local_factor, adjustedQcmFactor);
      return output;
    }).sort((a, b) => b.priority - a.priority || a.label.localeCompare(b.label, 'fr-CH'));
  }

  function buildPrioritySession(bank, profile, qcmDocument, limit, random) {
    const priorities = rulePriorities(bank, profile, qcmDocument);
    const active = priorities.filter((row) => row.errors > 0 || row.qcm_factor > 1);
    const rank = new Map(active.map((row, index) => [row.mechanism_id, index]));
    const grouped = new Map();
    bank.questions.forEach((question) => {
      if (!rank.has(question.mechanism_id)) return;
      if (!grouped.has(question.mechanism_id)) grouped.set(question.mechanism_id, []);
      grouped.get(question.mechanism_id).push(question);
    });
    const queues = active.map((rule) => shuffled(grouped.get(rule.mechanism_id) || [], random));
    const ordered = [];
    for (let pass = 0; pass < 2; pass += 1) {
      queues.forEach((queue) => { if (queue.length) ordered.push(queue.shift()); });
    }
    queues.forEach((queue) => ordered.push(...queue));
    return ordered.slice(0, Math.max(1, Number(limit || 20)));
  }

  function validatePriorityExport(document, bank) {
    const errors = [];
    const rootKeys = ['schema_version', 'export_id', 'generated_at', 'taxonomy_version', 'priorities'];
    if (document && typeof document === 'object' && Object.keys(document).some((key) => !rootKeys.includes(key))) {
      errors.push('Le fichier contient des données non autorisées.');
    }
    if (!document || document.schema_version !== 'hep-qcm-review-priorities/1.0') errors.push('Version de fichier inconnue.');
    if (!document || typeof document.export_id !== 'string' || !document.export_id.trim() || document.export_id.length > 120) errors.push('Identifiant d’export absent ou invalide.');
    if (!document || typeof document.generated_at !== 'string' || Number.isNaN(Date.parse(document.generated_at))) errors.push('Date d’export invalide.');
    if (!document || document.taxonomy_version !== 'hep-pedagogy-dict/2.0') errors.push('Version de taxonomie incompatible.');
    if (!document || !Array.isArray(document.priorities) || document.priorities.length > 100) errors.push('Liste de priorités absente ou trop longue.');
    if (errors.length) return { valid: false, errors, document: null, unsupported: [] };
    const supported = new Set(bank.questions.map((question) => pathKey(question)));
    const supportedGeneric = new Set(bank.questions.map((question) => pathKey(question, true)));
    const priorities = [];
    const unsupported = [];
    const seen = new Set();
    const shortId = /^[a-z][a-z0-9_]{1,63}$/;
    const rowKeys = ['family', 'mechanism_id', 'detail_id', 'tense_id', 'priority'];
    document.priorities.forEach((row, index) => {
      const validShape = row && typeof row === 'object' &&
        Object.keys(row).length === rowKeys.length && Object.keys(row).every((key) => rowKeys.includes(key)) &&
        shortId.test(row.family) && shortId.test(row.mechanism_id) &&
        (row.detail_id == null || shortId.test(row.detail_id)) &&
        (row.tense_id == null || shortId.test(row.tense_id)) &&
        Number.isFinite(Number(row.priority)) && Number(row.priority) >= 1 && Number(row.priority) <= 4;
      if (!validShape) {
        errors.push(`Priorité ${index + 1} invalide.`);
        return;
      }
      const key = pathKey(row);
      if (seen.has(key)) {
        errors.push(`Priorité ${index + 1} dupliquée.`);
        return;
      }
      seen.add(key);
      const compatible = supported.has(pathKey(row)) || ((!row.detail_id && !row.tense_id) && supportedGeneric.has(pathKey(row, true)));
      (compatible ? priorities : unsupported).push({
        family: row.family,
        mechanism_id: row.mechanism_id,
        detail_id: row.detail_id || null,
        tense_id: row.tense_id || null,
        priority: Number(row.priority),
      });
    });
    if (errors.length) return { valid: false, errors, document: null, unsupported };
    return {
      valid: true,
      errors: [],
      unsupported,
      document: {
        schema_version: document.schema_version,
        export_id: document.export_id,
        generated_at: document.generated_at,
        taxonomy_version: document.taxonomy_version,
        priorities,
      },
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
    return bank.questions.every((question) => {
      const correction = question.correction;
      const falseChoices = question.choices.filter((choice) => !isCorrect(choice, question));
      return typeof question.prompt === 'string' && !question.prompt.includes('___') &&
        Array.isArray(question.choices) && question.choices.length >= 2 && question.choices.length <= 4 &&
        question.choices.filter((choice) => isCorrect(choice, question)).length === 1 &&
        correction && typeof correction.explanation === 'string' &&
        ['Règle :', 'Méthode :', 'Dans cette phrase :', 'Donc :'].every((marker) => correction.explanation.includes(marker)) &&
        Array.isArray(correction.method_steps) && correction.method_steps.length >= 2 &&
        correction.why && typeof correction.why === 'object' &&
        Object.keys(correction.why).length === question.choices.length &&
        question.choices.every((choice) => typeof correction.why[choice] === 'string' && correction.why[choice].length >= 12) &&
        correction.diagnostics && typeof correction.diagnostics === 'object' &&
        Object.keys(correction.diagnostics).length === falseChoices.length &&
        falseChoices.every((choice) => {
          const diagnostic = correction.diagnostics[choice];
          return diagnostic &&
            ['mechanism_id', 'label', 'likely_reasoning', 'reasoning_break', 'decision_test', 'repair_strategy']
              .every((field) => typeof diagnostic[field] === 'string' && diagnostic[field].length >= 3);
        });
    });
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

  return {
    buildPrioritySession, emptyMastery, feedbackDocument, isCorrect, localNeed,
    normalize, normalizeMastery, pathKey, recordAttempt, restoreFeedback,
    rulePriorities, score, shuffled, validateBank, validatePriorityExport,
  };
}));
