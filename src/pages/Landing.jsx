import { motion, useReducedMotion } from 'framer-motion';
import Navbar from '../components/Navbar';
import Button from '../components/Button';
import Card from '../components/Card';
import Chip from '../components/Chip';
import { Reveal, Stagger, StaggerItem } from '../components/Reveal';
import { HOW_IT_WORKS, LANDING_FEATURES } from '../data/constants';
import { ease, fadeUp, staggerContainer } from '../animations/variants';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

const HEADLINE = ['Walk', 'into', 'every', 'interview'];
const word = {
  hidden: { opacity: 0, y: 22, filter: 'blur(6px)' },
  show: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.6, ease } },
};

function HeroBackdrop() {
  const loop = (x, y, duration) => ({
    animate: { x: [0, x, -x / 2, 0], y: [0, y, -y / 2, 0], scale: [1, 1.08, 0.96, 1] },
    transition: { duration, repeat: Infinity, ease: 'easeInOut' },
  });
  return (
    <div className="hero-bg" aria-hidden="true">
      <motion.span className="blob a" {...loop(40, -24, 18)} />
      <motion.span className="blob b" {...loop(-36, 28, 22)} />
    </div>
  );
}

export default function Landing() {
  useDocumentTitle('');
  const reduce = useReducedMotion();
  const scrollToHow = () => document.getElementById('how')?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth' });

  return (
    <>
      <a href="#main" className="skip-link">Skip to content</a>
      <Navbar variant="landing" />
      <main id="main" tabIndex={-1} className="wrap">
        <section className="hero">
          <HeroBackdrop />
          <Stagger className="hero-inner" gap={0.1}>
            <StaggerItem>
              <motion.span className="chip" style={{ display: 'inline-block' }} animate={{ y: [0, -4, 0] }} transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut', delay: 1 }}>
                ✨ Your personal AI interview coach
              </motion.span>
            </StaggerItem>
            <motion.h1 className="mt-md" variants={staggerContainer(0.07, 0.1)} aria-label="Walk into every interview prepared and confident.">
              <span className="word-line" aria-hidden="true">
                {HEADLINE.map((w) => <motion.span key={w} className="word" variants={word}>{w}&nbsp;</motion.span>)}
              </span>
              <motion.span className="word-line" aria-hidden="true" variants={fadeUp}>
                <span className="grad">prepared and confident.</span>
              </motion.span>
            </motion.h1>
            <StaggerItem as="p" className="sub">
              Upload your CV, pick your dream role, and practice with questions built around your experience. Get objective scoring and actionable coaching in real time.
            </StaggerItem>
            <StaggerItem className="row center">
              <Button variant="primary" to="/cv-upload">Start Interview →</Button>
              <Button onClick={scrollToHow}>How It Works</Button>
            </StaggerItem>
          </Stagger>
        </section>

        <Stagger className="g g4" inView gap={0.1}>
          {LANDING_FEATURES.map((f) => (
            <Card key={f.title} hover>
              <motion.div className="ico" whileHover={{ rotate: -8, scale: 1.12, y: -2 }} transition={{ type: 'spring', stiffness: 400, damping: 14 }} aria-hidden="true">{f.icon}</motion.div>
              <h3>{f.title}</h3>
              <p className="mut mt-sm">{f.text}</p>
            </Card>
          ))}
        </Stagger>

        <section id="how" style={{ padding: '70px 0 0' }} aria-labelledby="how-title">
          <Reveal as="h2" id="how-title" className="center mb-lg">How it works</Reveal>
          <Stagger className="g g4" inView gap={0.12}>
            {HOW_IT_WORKS.map((step, i) => (
              <Card key={step}>
                <Chip selected>{i + 1}</Chip>
                <h3 className="mt-md">{step}</h3>
              </Card>
            ))}
          </Stagger>
          <Reveal className="center mt-xl" delay={0.1}>
            <Button variant="primary" to="/cv-upload">Get started</Button>
          </Reveal>
        </section>
      </main>
    </>
  );
}
