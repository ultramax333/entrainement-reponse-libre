'use strict';

const assert = require('assert');
global.window = {};
const bank = require('./bank.js');
const engine = require('./choice-engine.js');
const drive = require('./drive-backup.js');

assert(engine.validateBank(bank));
assert.strictEqual(bank.questions.length, 148);
assert(bank.questions.every((question) => question.choices.length >= 2 && question.choices.length <= 4));
assert(bank.questions.every((question) => !question.prompt.includes('___')));
assert(bank.questions.every((question) => engine.isCorrect(question.answer, question)));
assert(bank.questions.every((question) => question.choices.filter((choice) => engine.isCorrect(choice, question)).length === 1));
assert.strictEqual(bank.questions.filter((question) => question.mechanism_id === 'nom_peuple_adjectif_langue').length, 22);
assert.strictEqual(bank.questions.filter((question) => question.mechanism_id === 'ou_ou').length, 6);
assert.strictEqual(bank.questions.filter((question) => question.choices.length === 2).length, 8);
assert(bank.questions.every((question) => question.rule_label));
assert(bank.questions.every((question) => Object.prototype.hasOwnProperty.call(question, 'tense_id')));
assert(bank.questions.every((question) => !Object.prototype.hasOwnProperty.call(question, 'application_note')));
assert(bank.questions.every((question) => {
  const correction = question.correction;
  return correction && ['Règle :', 'Méthode :', 'Dans cette phrase :', 'Donc :']
    .every((marker) => correction.explanation.includes(marker));
}));
assert(bank.questions.every((question) =>
  JSON.stringify(Object.keys(question.correction.why).sort()) === JSON.stringify(question.choices.slice().sort())
));
assert(bank.questions.every((question) => question.choices.every((choice) =>
  choice === question.answer || question.correction.why[choice].includes(`\`${choice}\``)
)));
assert(bank.questions.every((question) => {
  const wrongChoices = question.choices.filter((choice) => choice !== question.answer);
  return JSON.stringify(Object.keys(question.correction.diagnostics).sort()) === JSON.stringify(wrongChoices.sort()) &&
    wrongChoices.every((choice) => {
      const diagnostic = question.correction.diagnostics[choice];
      return diagnostic.likely_reasoning.includes('probablement') &&
        diagnostic.reasoning_break.includes(`« ${choice} »`) &&
        diagnostic.decision_test.length >= 30 && diagnostic.repair_strategy.length >= 30;
    });
}));
const spontaneity = bank.questions.find((question) => question.answer === 'spontanéité');
assert.strictEqual(
  spontaneity.correction.diagnostics.spontanéitée.mechanism_id,
  'nom_feminin_traite_comme_adjectif'
);
assert.deepStrictEqual(engine.score([{ correct: true }, { correct: false }]), { answered: 2, correct: 1 });
const original = ['a', 'b', 'c'];
assert.deepStrictEqual(engine.shuffled(original, () => 0), ['b', 'c', 'a']);
assert.deepStrictEqual(original, ['a', 'b', 'c']);

const backup = engine.feedbackDocument(bank, {
  [bank.questions[0].id]: { comment: '  Formulation à revoir.  ', updated_at: '2026-08-11T10:00:00Z' },
}, '2026-08-11T10:01:00Z');
assert.strictEqual(backup.feedbacks.length, 1);
assert.strictEqual(backup.feedbacks[0].comment, 'Formulation à revoir.');
assert.deepStrictEqual(engine.restoreFeedback(backup, bank)[bank.questions[0].id], {
  comment: 'Formulation à revoir.', updated_at: '2026-08-11T10:00:00Z',
});
assert.strictEqual(drive.configured({ GOOGLE_CLIENT_ID: '' }), false);
assert.strictEqual(drive.configured({ GOOGLE_CLIENT_ID: '123-test.apps.googleusercontent.com' }), true);

let mastery = engine.emptyMastery();
const target = bank.questions[0];
mastery = engine.recordAttempt(mastery, target, false, '2026-08-12T10:00:00Z');
mastery = engine.recordAttempt(mastery, target, false, '2026-08-12T10:01:00Z');
const targetKey = engine.pathKey(target);
assert.strictEqual(mastery.rules[targetKey].attempts, 2);
assert.strictEqual(mastery.rules[targetKey].errors, 2);
assert(engine.localNeed(mastery.rules[targetKey]).factor > 1);
const factorAfterErrors = engine.localNeed(mastery.rules[targetKey]).factor;
mastery = engine.recordAttempt(mastery, target, true, '2026-08-12T10:01:30Z');
mastery = engine.recordAttempt(mastery, target, true, '2026-08-12T10:01:40Z');
assert(engine.localNeed(mastery.rules[targetKey]).factor < factorAfterErrors);

const qcmExport = {
  schema_version: 'hep-qcm-review-priorities/1.0',
  export_id: 'hep-qcm-priorities-test-001',
  generated_at: '2026-08-12T10:02:00Z',
  taxonomy_version: 'hep-pedagogy-dict/2.0',
  priorities: [{
    family: target.family,
    mechanism_id: target.mechanism_id,
    detail_id: null,
    tense_id: null,
    priority: 1.8,
  }],
};
const validatedExport = engine.validatePriorityExport(qcmExport, bank);
assert.strictEqual(validatedExport.valid, true);
assert.strictEqual(validatedExport.document.priorities.length, 1);
const priorities = engine.rulePriorities(bank, mastery, validatedExport.document);
const targetPriority = priorities.find((row) => row.mechanism_id === target.mechanism_id);
assert.strictEqual(targetPriority.attempts, 4);
assert.strictEqual(targetPriority.errors, 2);
assert(targetPriority.priority >= 1.8);
const prioritySession = engine.buildPrioritySession(bank, mastery, validatedExport.document, 20, () => 0.5);
assert(prioritySession.length > 0 && prioritySession.length <= 20);
assert(prioritySession.some((question) => question.mechanism_id === target.mechanism_id));

const invalidExport = { ...qcmExport, taxonomy_version: 'ancienne-version' };
assert.strictEqual(engine.validatePriorityExport(invalidExport, bank).valid, false);
const leakingExport = { ...qcmExport, selected_answer: 'secret' };
assert.strictEqual(engine.validatePriorityExport(leakingExport, bank).valid, false);

console.log('test_choice_app.js: OK — 148 exercices, priorités QCM et maîtrise locale contrôlés.');
