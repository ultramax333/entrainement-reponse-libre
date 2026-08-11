'use strict';

const assert = require('assert');
global.window = {};
const bank = require('./bank.js');
const engine = require('./choice-engine.js');
const drive = require('./drive-backup.js');

assert(engine.validateBank(bank));
assert.strictEqual(bank.questions.length, 40);
assert(bank.questions.every((question) => question.choices.length >= 2 && question.choices.length <= 4));
assert(bank.questions.every((question) => !question.prompt.includes('___')));
assert(bank.questions.every((question) => engine.isCorrect(question.answer, question)));
assert(bank.questions.every((question) => question.choices.filter((choice) => engine.isCorrect(choice, question)).length === 1));
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

console.log('test_choice_app.js: OK — 40 exercices et backup feedback contrôlés.');
