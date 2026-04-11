import React, { useState } from 'react'
import { ingestPdf, ingestKanoon } from '../lib/api'
import styles from './KnowledgePage.module.css'

const CATEGORIES = [
  { value: 'statute', label: 'Statute (IPC / CrPC / BNSS)' },
  { value: 'constitutional', label: 'Constitutional law' },
  { value: 'judgment', label: 'Court judgment' },
  { value: 'guideline', label: 'Guideline / Circular' },
]

const SUGGESTED_QUERIES = [
  { query: '"section 436A" ANDD bail undertrial', label: '436A default bail' },
  { query: '"section 167" ANDD "charge sheet" remand', label: '167 CrPC remand' },
  { query: 'Article 21 speedy trial undertrial', label: 'Speedy trial A.21' },
  { query: 'Hussainara Khatoon bail undertrial', label: 'Hussainara Khatoon' },
  { query: 'Arnesh Kumar arrest Section 41 CrPC', label: 'Arnesh Kumar' },
  { query: 'Maneka Gandhi personal liberty Article 21', label: 'Maneka Gandhi' },
  { query: 'Sanjay Chandra pre trial detention bail', label: 'Sanjay Chandra' },
  { query: '"section 437" bail non bailable offence', label: '437 CrPC bail' },
]

const LOG_SEED = [
  { type: 'info', msg: 'Vector store ready - ChromaDB local instance' },
  { type: 'info', msg: 'Embedding model: nomic-embed-text (Ollama)' },
]

export default function KnowledgePage() {
  const [pdfFile, setPdfFile] = useState(null)
  const [pdfCategory, setPdfCategory] = useState('statute')
  const [pdfCourt, setPdfCourt] = useState('')
  const [pdfLoading, setPdfLoading] = useState(false)

  const [kanoonQuery, setKanoonQuery] = useState('')
  const [kanoonText, setKanoonText] = useState('')
  const [kanoonLimit, setKanoonLimit] = useState(5)
  const [kanoonLoading, setKanoonLoading] = useState(false)

  const [log, setLog] = useState(LOG_SEED)

  const addLog = (type, msg) => setLog((current) => [...current, { type, msg, ts: new Date().toLocaleTimeString() }])

  const handlePdfIngest = async () => {
    if (!pdfFile) return
    setPdfLoading(true)
    addLog('info', `Ingesting "${pdfFile.name}" as ${pdfCategory}...`)
    try {
      const res = await ingestPdf(pdfFile, pdfCategory, pdfCourt)
      addLog('success', res.message || `Ingested ${pdfFile.name}`)
      setPdfFile(null)
    } catch (err) {
      addLog('error', err.message)
    } finally {
      setPdfLoading(false)
    }
  }

  const handleKanoonIngest = async () => {
    if (!kanoonQuery.trim()) return
    setKanoonLoading(true)
    addLog('info', `Searching Indian Kanoon: "${kanoonQuery}" (limit ${kanoonLimit})...`)
    try {
      const res = await ingestKanoon(kanoonQuery, kanoonText, kanoonLimit)
      addLog('success', res.message || 'Ingestion complete')
    } catch (err) {
      addLog('error', err.message)
    } finally {
      setKanoonLoading(false)
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>Knowledge Base</h1>
        <p className={styles.pageDesc}>
          Manage the legal documents and case law that power the RAG pipeline.
          Ingest IPC/CrPC PDFs, Supreme Court judgments, or search Indian Kanoon.
        </p>
      </div>

      <div className={styles.grid}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.cardIcon}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="12" y1="12" x2="12" y2="18" />
                <line x1="9" y1="15" x2="15" y2="15" />
              </svg>
            </div>
            <div>
              <div className={styles.cardTitle}>Ingest PDF Document</div>
              <div className={styles.cardSub}>Upload statutes, judgments, or guidelines</div>
            </div>
          </div>
          <div className={styles.cardBody}>
            <div
              className={`${styles.dropzone} ${pdfFile ? styles.dropzoneActive : ''}`}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault()
                const file = event.dataTransfer.files[0]
                if (file?.name.endsWith('.pdf')) setPdfFile(file)
              }}
              onClick={() => document.getElementById('pdf-input').click()}
            >
              <input
                id="pdf-input"
                type="file"
                accept=".pdf"
                style={{ display: 'none' }}
                onChange={(event) => setPdfFile(event.target.files[0] || null)}
              />
              {pdfFile ? (
                <>
                  <div className={styles.dropzoneFile}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    {pdfFile.name}
                  </div>
                  <div className={styles.dropzoneSize}>
                    {(pdfFile.size / 1024).toFixed(0)} KB
                  </div>
                </>
              ) : (
                <>
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" opacity="0.35">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  <div className={styles.dropzoneLabel}>
                    Drop PDF here or <span>browse</span>
                  </div>
                  <div className={styles.dropzoneSub}>IPC, CrPC, BNSS, SC judgments</div>
                </>
              )}
            </div>

            <div className={styles.fieldRow}>
              <div className={styles.field}>
                <label className={styles.label}>Category</label>
                <select value={pdfCategory} onChange={(event) => setPdfCategory(event.target.value)}>
                  {CATEGORIES.map((category) => (
                    <option key={category.value} value={category.value}>{category.label}</option>
                  ))}
                </select>
              </div>
              <div className={styles.field}>
                <label className={styles.label}>Court (optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Supreme Court"
                  value={pdfCourt}
                  onChange={(event) => setPdfCourt(event.target.value)}
                />
              </div>
            </div>

            <button
              className={styles.primaryBtn}
              onClick={handlePdfIngest}
              disabled={!pdfFile || pdfLoading}
            >
              {pdfLoading ? <><span className={styles.spinner} /> Ingesting...</> : 'Ingest Document'}
            </button>
          </div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.cardIcon}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </div>
            <div>
              <div className={styles.cardTitle}>Indian Kanoon Search</div>
              <div className={styles.cardSub}>Fetch case law into the vector store</div>
            </div>
          </div>
          <div className={styles.cardBody}>
            <div className={styles.field}>
              <label className={styles.label}>Search Query</label>
              <input
                type="text"
                placeholder='e.g. "section 436A" ANDD bail undertrial'
                value={kanoonQuery}
                onChange={(event) => setKanoonQuery(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleKanoonIngest()}
              />
            </div>
            <div className={styles.fieldRow}>
              <div className={styles.field}>
                <label className={styles.label}>Full-text filter</label>
                <input
                  type="text"
                  placeholder="e.g. undertrial"
                  value={kanoonText}
                  onChange={(event) => setKanoonText(event.target.value)}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>Limit</label>
                <select value={kanoonLimit} onChange={(event) => setKanoonLimit(+event.target.value)}>
                  {[3, 5, 10, 15].map((limit) => <option key={limit}>{limit}</option>)}
                </select>
              </div>
            </div>

            <div className={styles.suggestionsLabel}>Suggested queries</div>
            <div className={styles.suggestions}>
              {SUGGESTED_QUERIES.map((suggestion) => (
                <button
                  key={suggestion.query}
                  className={styles.suggestion}
                  onClick={() => setKanoonQuery(suggestion.query)}
                >
                  {suggestion.label}
                </button>
              ))}
            </div>

            <button
              className={styles.primaryBtn}
              onClick={handleKanoonIngest}
              disabled={!kanoonQuery.trim() || kanoonLoading}
            >
              {kanoonLoading ? <><span className={styles.spinner} /> Searching...</> : 'Fetch & Ingest'}
            </button>
          </div>
        </div>

        <div className={`${styles.card} ${styles.logCard}`}>
          <div className={styles.cardHeader}>
            <div className={styles.cardIcon}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
            </div>
            <div>
              <div className={styles.cardTitle}>Activity Log</div>
              <div className={styles.cardSub}>Ingestion events &amp; errors</div>
            </div>
            {log.length > 2 && (
              <button className={styles.clearBtn} onClick={() => setLog(LOG_SEED)}>
                Clear
              </button>
            )}
          </div>
          <div className={styles.logBody}>
            {log.map((entry, index) => (
              <div key={index} className={`${styles.logEntry} ${styles[`log_${entry.type}`]}`}>
                <span className={styles.logDot} />
                <span className={styles.logMsg}>{entry.msg}</span>
                {entry.ts && <span className={styles.logTs}>{entry.ts}</span>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  )
}
