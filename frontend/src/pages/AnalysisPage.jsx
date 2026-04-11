import React, { useState } from 'react'
import CaseForm from '../components/CaseForm'
import BriefViewer from '../components/BriefViewer'
import { analyzeCase } from '../lib/api'
import styles from './AnalysisPage.module.css'

const PIPELINE_STEPS = [
  { id: 'ingest', label: 'Ingesting case details into vector store' },
  { id: 'eligibility', label: 'Eligibility agent - checking 167/436A CrPC' },
  { id: 'rights', label: 'Rights agent - Article 21/22 analysis' },
  { id: 'advocate', label: 'Advocate agent - drafting bail brief' },
  { id: 'critic', label: 'Critic agent - reviewing for hallucinations' },
  { id: 'finalise', label: 'Finalising output' },
]

export default function AnalysisPage() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [pipelineStep, setPipelineStep] = useState(-1)

  const handleSubmit = async (caseData) => {
    setLoading(true)
    setError(null)
    setResult(null)
    setPipelineStep(0)

    const stepInterval = setInterval(() => {
      setPipelineStep((current) => {
        if (current >= PIPELINE_STEPS.length - 2) {
          clearInterval(stepInterval)
          return current
        }
        return current + 1
      })
    }, 8000)

    try {
      const data = await analyzeCase(caseData)
      clearInterval(stepInterval)
      setPipelineStep(PIPELINE_STEPS.length - 1)
      await new Promise((resolve) => setTimeout(resolve, 600))
      setResult(data)
    } catch (err) {
      clearInterval(stepInterval)
      setError(err.message)
    } finally {
      setLoading(false)
      setPipelineStep(-1)
    }
  }

  return (
    <main className={styles.page}>
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <div className={styles.kicker}>Case Intake</div>
          <h2 className={styles.sidebarTitle}>New Case</h2>
          <p className={styles.sidebarDesc}>
            Enter case details to generate an AI-assisted bail application brief,
            eligibility analysis, and constitutional rights report.
          </p>
          <div className={styles.sidebarMeta}>
            <span>Structured intake</span>
            <span>RAG-backed reasoning</span>
            <span>Advocate review required</span>
          </div>
        </div>
        <div className={styles.formCard}>
          <CaseForm onSubmit={handleSubmit} loading={loading} />
        </div>
      </aside>

      <section className={styles.main}>
        {loading && (
          <div className={styles.pipelinePanel}>
            <div className={styles.pipelineTitle}>
              <span className={styles.pipelineSpinner} />
              Running multi-agent pipeline
            </div>
            <div className={styles.steps}>
              {PIPELINE_STEPS.map((step, index) => (
                <div
                  key={step.id}
                  className={`${styles.step} ${
                    index < pipelineStep ? styles.stepDone :
                    index === pipelineStep ? styles.stepActive : styles.stepPending
                  }`}
                >
                  <div className={styles.stepDot} />
                  <span>{step.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && !loading && (
          <div className={styles.errorPanel}>
            <div className={styles.errorTitle}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              Analysis failed
            </div>
            <p className={styles.errorMsg}>{error}</p>
            <p className={styles.errorHint}>
              Make sure the backend is running at <code>localhost:8000</code> and your API keys are configured.
            </p>
          </div>
        )}

        {result && !loading && <BriefViewer result={result} />}

        {!loading && !result && !error && <EmptyState />}
      </section>
    </main>
  )
}

function EmptyState() {
  return (
    <div className={styles.empty}>
      <div className={styles.emptyGlyph}>
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 3v18" />
          <path d="M5 7h14" />
          <path d="M7.5 7 4 13a3.5 3.5 0 0 0 7 0L7.5 7Z" />
          <path d="m16.5 7-3.5 6a3.5 3.5 0 0 0 7 0l-3.5-6Z" />
          <path d="M9 21h6" />
        </svg>
      </div>
      <h3 className={styles.emptyTitle}>No analysis yet</h3>
      <p className={styles.emptyDesc}>
        Fill in the case details on the left to generate a bail application brief,
        eligibility report, and constitutional rights analysis.
      </p>
      <div className={styles.emptyFeatures}>
        {[
          ['167/436A CrPC', 'Default bail eligibility check'],
          ['Article 21/22', 'Constitutional rights analysis'],
          ['Precedent-backed', 'Citations from Indian Kanoon RAG'],
          ['Critic-reviewed', 'Hallucination detection loop'],
        ].map(([tag, desc]) => (
          <div key={tag} className={styles.featurePill}>
            <span className={styles.featureTag}>{tag}</span>
            <span className={styles.featureDesc}>{desc}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
