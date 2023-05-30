import React, { useEffect, useState } from 'react';
import axios from 'axios';
import Question from './Question';

const Quiz = () => {
  const quizId = 'a131bb95-a968-49e9-93ce-771ce70de01d';
  const [quizData, setQuizData] = useState(null);
  const [questionData, setQuestionData] = useState(null);
  const [questionIndex, setQuestionIndex] = useState(0);

  const onUserAnswers = async (userAnswer) => {
    console.log('onUserAnswers', questionIndex, userAnswer);
    // try {
    //   const response = await axios.post(`http://localhost:8000/quiz/${quizId}/${questionIndex}`, data=userAnswer);
    //   setQuestionData(response.data);
    // } catch (error) {
    //   console.error('Error fetching quiz data:', error);
    // }
  }

  useEffect(() => {
    const fetchQuizData = async () => {
      try {
        const response = await axios.get(`http://localhost:8000/quiz/${quizId}`);
        setQuizData(response.data);
        setQuestionIndex(response.data.current_index);
      } catch (error) {
        console.error('Error fetching quiz data:', error);
      }
    };

    fetchQuizData();
  }, [quizId]);

  useEffect(() => {
    if (quizData) {
      const fetchQuestionData = async () => {
        try {
          const response = await axios.get(`http://localhost:8000/quiz/${quizId}/${questionIndex}`);
          setQuestionData(response.data);
        } catch (error) {
          console.error('Error fetching question data:', error);
        }
      };

      fetchQuestionData();
    }
  }, [quizId, quizData]);

  if (!quizData || !questionData) {
    return <div>Loading...</div>;
  }

  const { name, size } = quizData;

  return (
    <div>
      <h1>Quiz: {name}</h1>
      <h2>{questionIndex + 1}/{size}</h2>
      <Question quiz_question={questionData} onUserAnswers={onUserAnswers} />
    </div>
  );
};

export default Quiz;
