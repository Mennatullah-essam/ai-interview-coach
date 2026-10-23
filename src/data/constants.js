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

export const DEFAULT_CONFIG = { role: 'AI Engineer', type: 'Technical', diff: 'Intermediate', n: 10, jobDescription: '', adaptive: false };
export const MAX_JOB_DESCRIPTION_LENGTH = 5000;
export const EXPERIENCE_LEVELS = [
  { value: 'student', label: 'Student' },
  { value: 'entry', label: 'Entry level' },
  { value: 'junior', label: 'Junior' },
  { value: 'mid', label: 'Mid level' },
  { value: 'senior', label: 'Senior' },
];
/** Why a question was asked, as a short label. */
export const QUESTION_CATEGORIES = {
  core: 'Role core',
  cv_skill: 'From your CV',
  project: 'Your project',
  skill_gap: 'Skill gap',
  coverage: 'Role requirement',
  behavioral: 'Behavioral',
  follow_up: 'Follow-up',
};

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
  { icon: '📄', title: 'CV-Aware Interview Questions', text: 'Questions selected from a curated bank and tailored to your CV skills and target role.' },
  { icon: '🧠', title: 'Automated Answer Evaluation', text: 'Every answer is scored on six explained dimensions: relevance, key concepts, technical accuracy, structure, evidence and communication.' },
  { icon: '🎯', title: 'Actionable Feedback', text: 'Missing concepts, concrete suggestions, an answer outline and a personal improvement plan.' },
  { icon: '📈', title: 'Performance Tracking', text: 'See your scores and skills improve session by session.' },
];
export const HOW_IT_WORKS = ['Create your account', 'Upload your CV', 'Answer tailored questions', 'Get automated coaching'];

export const COACH_TIPS = ['Aim for 1–2 minutes', 'Use specific numbers', 'Mention your role'];
export const THINKING_MESSAGES = [
  'Scoring relevance, clarity, depth and structure',
  'Comparing against strong example answers',
  'Preparing your feedback',
];
