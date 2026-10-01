/** Static UI configuration and copy (not backend data). */

export const ROLES = ['AI Engineer', 'Machine Learning Engineer', 'Data Scientist', 'Software Engineer', 'Backend Developer', 'Frontend Developer', 'Data Analyst'];

export const INTERVIEW_TYPES = [
  { value: 'Technical', description: 'Skills & problem solving' },
  { value: 'Behavioral', description: 'Past experience & soft skills' },
  { value: 'Mixed', description: 'A balanced blend' },
];
export const DIFFICULTIES = ['Beginner', 'Intermediate', 'Advanced'];
export const QUESTION_COUNTS = [5, 10, 15];
export const HISTORY_FILTERS = ['All', 'Technical', 'Behavioral', 'Mixed'];

export const DEFAULT_CONFIG = { role: 'AI Engineer', type: 'Technical', diff: 'Intermediate', n: 10 };

export const MINUTES_PER_QUESTION = 3;
export const MIN_ANSWER_LENGTH = 30;
export const MAX_ANSWER_LENGTH = 1500;
export const MIN_CUSTOM_ROLE_LENGTH = 3;
export const CV_ACCEPTED_EXTENSIONS = ['pdf', 'docx'];
export const CV_MAX_SIZE_MB = 5;

export const NAV_ITEMS = [
  { path: '/dashboard', label: 'Dashboard', short: 'Dashboard', icon: '◧' },
  { path: '/cv-upload', label: 'New Interview', short: 'New', icon: '＋' },
  { path: '/history', label: 'History', short: 'History', icon: '☰' },
  { path: '/performance', label: 'Performance', short: 'Performance', icon: '↗' },
  { path: '/profile', label: 'Profile', short: 'Profile', icon: '⚙' },
];

export const LANDING_FEATURES = [
  { icon: '📄', title: 'CV-Aware Interview Questions', text: 'Questions generated from your own experience and target role.' },
  { icon: '🧠', title: 'AI Answer Evaluation', text: 'Semantic scoring of every answer against strong responses.' },
  { icon: '🎯', title: 'Personalized Feedback', text: 'Strengths, weaknesses and ideal-answer examples.' },
  { icon: '📈', title: 'Performance Tracking', text: 'See your confidence and skills improve session by session.' },
];
export const HOW_IT_WORKS = ['Upload your CV', 'Choose a target role', 'Answer tailored questions', 'Get AI coaching'];

export const COACH_TIPS = ['Aim for 1–2 minutes', 'Use specific numbers', 'Mention your role'];
export const THINKING_MESSAGES = [
  'Scoring relevance, clarity and technical depth',
  'Comparing against strong example answers',
  'Preparing your feedback',
];
