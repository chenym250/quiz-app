import React, { useState } from 'react';
import './Question.css';

const Question = ({ quiz_question, onUserAnswers }) => {

  const [ showSubmitButton, setShowSubmitButton ] = useState(false);

  const { status, user_answer } = quiz_question;

  const { number, text, choices, of_type, answer, explain } = quiz_question.question;

  const [userAnswers, setUserAnswers] = useState(new Set());

  const handleChoiceClick = (choice) => {
    if (status != 'NOT_ANSWERED') {
      return
    }
    if (of_type === 'MULTI_CHOICE') {
      // Can only be one answer.
      const mSet = new Set([choice.letter]);
      setUserAnswers(mSet);
      // Callback right away.
      onUserAnswers(mSet);
    } else if (of_type === 'MULTI_ANSWER') {
      const selected = new Set(userAnswers);
      if (selected.has(choice.letter)) {
        selected.delete(choice.letter);
      } else {
        selected.add(choice.letter);
      }
      setUserAnswers(selected);
      setShowSubmitButton(selected.size != 0);
    } else {
      console.log('Cannot handle question type:', of_type);
    }
  };

  const handleSubmitClick = () => {
    console.log('handleSubmitClick', status, of_type);
    console.log('handleSubmitClick', status === 'NOT_ANSWERED' && (of_type === 'MULTI_ANSWER' || of_type === 'SHORT_ANSWER'));
    if (status === 'NOT_ANSWERED' && (of_type === 'MULTI_ANSWER' || of_type === 'SHORT_ANSWER')) {
      onUserAnswers(userAnswers);
    }
  }

  const getClassNameForChoice = (choice) => {
    if (status === 'NOT_ANSWERED') {
      if (userAnswers.has(choice.letter)) {
        return 'selected';
      }
    } else if (of_type === 'MULTI_CHOICE') {
      if (choice.letter === answer) {
        return 'correct';
      }
      if (user_answer.includes(choice.letter)) {
        return 'wrong';
      }
    } else if (of_type === 'MULTI_ANSWER') {
      const inAnswer = answer.includes(choice.letter);
      const inUserAnswer = user_answer.includes(choice.letter);
      if (inAnswer && inUserAnswer) {
        return 'correct';
      }
      if (inAnswer && !inUserAnswer) {
        return 'missing';
      }
      if (!inAnswer && inUserAnswer) {
        return 'wrong';
      }
    }
    return '';
  }

  const renderChoices = () => {
    return choices.map((choice) => (
      <li
        key={choice.letter}
        className={getClassNameForChoice(choice)}
        onClick={() => handleChoiceClick(choice)}
      >
        {choice.letter}. {choice.text}
      </li>
    ));
  };

  return (
    <div className='question'>
      <div>{number}. {text}</div>
      <ul> {renderChoices()} </ul>
      <button
        className={showSubmitButton ? '' : 'hidden'}
        onClick={handleSubmitClick}
      >submit</button>
    </div>
  );
};

export default Question;
