'use strict';

const assert = require('assert');
global.window = {};
const bank = require('./bank.js');
const engine = require('./choice-engine.js');

assert(engine.validateBank(bank));
assert.strictEqual(bank.questions.length, 20);
assert(bank.questions.every((question) => question.choices.length >= 2 && question.choices.length <= 4));
assert(bank.questions.every((question) => !question.prompt.includes('___')));
assert(bank.questions.every((question) => engine.isCorrect(question.answer, question)));
assert(bank.questions.every((question) => question.choices.filter((choice) => engine.isCorrect(choice, question)).length === 1));
assert.deepStrictEqual(engine.score([{ correct: true }, { correct: false }]), { answered: 2, correct: 1 });
const original = ['a', 'b', 'c'];
assert.deepStrictEqual(engine.shuffled(original, () => 0), ['b', 'c', 'a']);
assert.deepStrictEqual(original, ['a', 'b', 'c']);

console.log('test_choice_app.js: OK — 20 exercices à choix contrôlés.');
