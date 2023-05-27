import React, { useState } from 'react';
import './Question.css';

const Question = ({ question }) => {

  const { number, text, choices } = question;

  const [selectedChoice, setSelectedChoice] = useState(null);

  const handleChoiceClick = (choice) => {
    setSelectedChoice(choice);
  };

  const renderChoices = () => {
    return choices.map((choice) => (
      <li
        key={choice.letter}
        className={selectedChoice === choice ? 'selected' : ''}
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
    </div>
  );
};

export default Question;
