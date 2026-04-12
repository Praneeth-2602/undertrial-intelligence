import React from 'react'
import styles from './AboutPage.module.css'

const PIPELINE = [
  {
    id: 'input',
    title: 'Case Input',
    desc: 'FIR text, charges, detention duration, court, state',
    color: 'amber',
  },
  {
    id: 'rag',
    title: 'RAG Retrieval',
    desc: 'ChromaDB + nomic-embed-text queries IPC, CrPC, SC judgments',
    color: 'teal',
  },
  {
    id: 'parallel',
    title: 'Parallel Agents',
    desc: 'Eligibility (Groq/Llama 3.3 70B) + Rights (Groq/Llama 3.3 70B) run simultaneously',
    color: 'rust',
    split: true,
  },
  {
    id: 'advocate',
    title: 'Advocate Agent',
    desc: 'Gemini 2.0 Flash drafts the full bail brief from both reports',
    color: 'rust',
  },
  {
    id: 'critic',
    title: 'Critic Agent',
    desc: 'Gemini checks for hallucinations, loops back to advocate if needed',
    color: 'amber',
    loop: true,
  },
  {
    id: 'output',
    title: 'Final Output',
    desc: 'Legal brief + plain-language summary + eligibility & rights reports',
    color: 'teal',
  },
]

const LEGAL_REFS = [
  {
    cite: 'Section 167(2) CrPC',
    desc: 'Mandates filing charge sheet within 60 days (non-heinous) or 90 days (heinous). Failure triggers default bail as a matter of right.',
  },
  {
    cite: 'Section 436A CrPC',
    desc: 'Entitles undertrial to bail upon completing half the maximum sentence of the alleged offence, subject to court discretion.',
  },
  {
    cite: 'Article 21, Constitution of India',
    desc: 'Guarantees right to life and personal liberty. Interpreted to include right to speedy trial - Hussainara Khatoon (1979).',
  },
  {
    cite: 'Article 22, Constitution of India',
    desc: 'Protection against arbitrary arrest and detention. Grounds for challenge when custody exceeds statutory limits without cause.',
  },
  {
    cite: 'Arnesh Kumar v. State of Bihar (2014)',
    desc: 'Supreme Court directed police to satisfy requirements of Section 41 CrPC before arrest. Arrest must not be a default action.',
  },
  {
    cite: 'Sanjay Chandra v. CBI (2012)',
    desc: 'Held that pre-trial detention should be least restrictive and courts must balance individual liberty against societal interests.',
  },
]

export default function AboutPage() {
  return (
    <main className={styles.page}>
      <div className={styles.hero}>
        <div className={styles.heroContent}>
          <div className={styles.heroTag}>About the system</div>
          <h1 className={styles.heroTitle}>
            Professional AI support
            <span> for undertrial bail preparation</span>
          </h1>
          <p className={styles.heroDesc}>
            India holds more than 75% of its prison population as undertrials - people
            who have not been convicted but remain in custody, often for years, due to
            delays in the justice system. This tool exists to close the gap between
            legal entitlement and legal access.
          </p>
        </div>
        <div className={styles.heroBadges}>
          <StatBadge num="75%+" label="Prisoners are undertrials" />
          <StatBadge num="4.5L+" label="Undertrial population" />
          <StatBadge num="60 days" label="167 CrPC charge sheet deadline" />
        </div>
      </div>

      <div className={styles.body}>
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>How it works</h2>
          <p className={styles.sectionDesc}>
            A LangGraph-orchestrated multi-agent pipeline retrieves relevant statutes
            and precedents from a local vector store, then runs specialist agents in
            sequence with a critic loop to catch hallucinations.
          </p>
          <div className={styles.pipeline}>
            {PIPELINE.map((step, index) => (
              <React.Fragment key={step.id}>
                <div className={`${styles.pStep} ${styles[`pStep_${step.color}`]}`}>
                  <div className={styles.pNum}>{String(index + 1).padStart(2, '0')}</div>
                  <div>
                    <div className={styles.pTitle}>{step.title}</div>
                    <div className={styles.pDesc}>{step.desc}</div>
                  </div>
                  {step.loop && (
                    <div className={styles.loopTag}>↺ loops back if needed</div>
                  )}
                </div>
                {index < PIPELINE.length - 1 && (
                  <div className={styles.pArrow}>↓</div>
                )}
              </React.Fragment>
            ))}
          </div>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Legal framework</h2>
          <p className={styles.sectionDesc}>
            The system's reasoning is grounded in the following statutes and precedents,
            all of which are ingested into the vector store.
          </p>
          <div className={styles.legalGrid}>
            {LEGAL_REFS.map((reference) => (
              <div key={reference.cite} className={styles.legalCard}>
                <div className={styles.legalCite}>{reference.cite}</div>
                <div className={styles.legalDesc}>{reference.desc}</div>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Technology stack</h2>
          <p className={styles.sectionDesc}>
            The product is designed as a local-first legal drafting environment with
            traceable retrieval, specialised agent roles, and explicit human review.
          </p>
          <div className={styles.stackGrid}>
            {[
              ['LangGraph', 'Multi-agent orchestration with conditional edges'],
              ['ChromaDB', 'Local vector store - no cloud dependency'],
              ['nomic-embed-text', 'Ollama-hosted embedding model (CPU-safe, 274MB)'],
              ['Groq / Llama 3.3 70B', 'Eligibility & rights analysis (free tier)'],
              ['Gemini 2.0 Flash', 'Advocate + critic agents (free tier)'],
              ['FastAPI', 'REST backend - /analyze, /ingest/pdf, /ingest/kanoon'],
              ['Indian Kanoon API', 'Case law retrieval for vector store seeding'],
              ['React + Vite', 'Frontend, zero external CSS frameworks'],
            ].map(([name, desc]) => (
              <div key={name} className={styles.stackRow}>
                <span className={styles.stackName}>{name}</span>
                <span className={styles.stackDesc}>{desc}</span>
              </div>
            ))}
          </div>
        </section>

        <div className={styles.disclaimer}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <p>
            This system generates legal briefs to assist qualified advocates - it is not a
            substitute for legal counsel. All output must be reviewed and endorsed by a
            licensed advocate before being filed in court. The system may make errors;
            the critic agent reduces but does not eliminate hallucinations.
          </p>
        </div>
      </div>
    </main>
  )
}

function StatBadge({ num, label }) {
  return (
    <div className={styles.statBadge}>
      <div className={styles.statNum}>{num}</div>
      <div className={styles.statLabel}>{label}</div>
    </div>
  )
}
