/**
 * Demo data used by the mock service layer (src/services/api.js).
 * Everything here is replaced by real backend responses later.
 */

export const DEMO_USER = { name: 'Alex Morgan', email: 'alex.morgan@email.com' };

export const QUESTION_BANK = [
  { text: 'Can you explain a machine learning project you worked on and the impact it had?', type: 'Technical' },
  { text: 'Your CV mentions a transformer-based classifier. How did you choose and evaluate the model?', type: 'Technical' },
  { text: 'Tell me about a time you disagreed with a teammate on a technical decision.', type: 'Behavioral' },
  { text: 'How would you handle an imbalanced dataset in a classification task?', type: 'Technical' },
  { text: 'Describe how you deployed a model or service to the cloud.', type: 'Technical' },
  { text: 'Tell me about a deadline you nearly missed. What did you do?', type: 'Behavioral' },
  { text: 'What is the difference between BERT and Sentence Transformers for similarity tasks?', type: 'Technical' },
  { text: "How do you monitor a model's performance after deployment?", type: 'Technical' },
  { text: 'Describe a time you had to learn a new tool quickly.', type: 'Behavioral' },
  { text: 'Why do you want to work as an AI Engineer, and where do you see yourself in 3 years?', type: 'Behavioral' },
];

export const FOLLOW_UP_SUFFIX = ' (Follow-up: go deeper on the trade-offs.)';

export const INTERVIEW_HISTORY = [
  { id: 'h4', date: 'Sep 24, 2026', role: 'AI Engineer', type: 'Technical', diff: 'Intermediate', n: 10, score: 84, status: 'Completed' },
  { id: 'h3', date: 'Sep 17, 2026', role: 'Machine Learning Engineer', type: 'Mixed', diff: 'Intermediate', n: 10, score: 82, status: 'Completed' },
  { id: 'h2', date: 'Sep 9, 2026', role: 'Data Scientist', type: 'Behavioral', diff: 'Beginner', n: 5, score: 80, status: 'Completed' },
  { id: 'h1', date: 'Aug 30, 2026', role: 'AI Engineer', type: 'Technical', diff: 'Intermediate', n: 15, score: 83, status: 'Completed' },
];

export const SKILLS = {
  Communication: 88,
  Relevance: 86,
  Confidence: 82,
  Clarity: 81,
  'Technical Depth': 76,
};

/** Per-question score offsets used when rebuilding results for a past interview. */
export const SCORE_OFFSETS = [4, -8, 7, -3, 5, -10, 2, 6, -5, 3];

export const EVAL_TEMPLATES = {
  weaknesses: [
    'Could quantify the project impact more clearly.',
    'The answer could be more structured.',
    'Some technical details were missing.',
  ],
  briefAnswerWeakness: 'The answer was brief; add more depth and detail.',
  strengths: {
    Technical: ['Clearly explained the technical approach.', 'Demonstrated practical experience.', 'Provided relevant examples.'],
    Behavioral: ['Showed strong ownership and self-awareness.', 'Kept a clear, logical narrative.', 'Communicated professionally and calmly.'],
  },
  tips: {
    Technical: 'Use the STAR method (Situation, Task, Action, Result) and close with a measurable outcome.',
    Behavioral: 'Structure this with STAR and end with what you learned.',
  },
  idealAnswers: {
    Technical:
      '"At my last internship I built a ticket-routing classifier. The problem was 30% manual triage delay, so I fine-tuned DistilBERT on 40k labelled tickets, compared it against a TF-IDF baseline, and tracked macro-F1. Accuracy rose from 71% to 89%, cutting triage time by about 30%. I deployed it behind a FastAPI service and monitored drift weekly."',
    Behavioral:
      '"In a group project, my teammate and I disagreed on the model architecture. I suggested we run a quick two-day benchmark on both. The results favoured his approach, so we adopted it, and I documented the comparison. We shipped on time and I learned to settle debates with data."',
  },
};

export const RESULT_SUMMARY_COPY = {
  extraStrength: 'Relevant, practical examples',
  extraImprovement: 'Quantifying impact',
  recommendations: [
    'Explain technical projects in under 2 minutes.',
    'Give measurable results for past projects.',
    'Structure behavioral answers using STAR.',
  ],
};
