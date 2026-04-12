import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { listReviews, submitReview, getCaseReview } from '../lib/api'
import styles from './ReviewPage.module.css'

const VERDICT_META = {
  approved: { label: 'Approved', color: 'success', icon: '✓' },
  flagged: { label: 'Flagged', color: 'danger', icon: '⚑' },
  needs_revision: { label: 'Needs revision', color: 'warning', icon: '↩' },
  pending: { label: 'Pending review', color: 'neutral', icon: '○' },
}

function CasePanel({ caseId, onClose }) {
  const [brief, setBrief] = useState(null)
  const [review, setReview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ verdict: '', note: '', reviewer: '' })
  const [saved, setSaved] = useState(false)
  const [activeTab, setActiveTab] = useState('brief')

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(`brief:${caseId}`)
      if (stored) setBrief(JSON.parse(stored))
    } catch {
      // Brief not cached in session storage.
    }
  }, [caseId])

  useEffect(() => {
    getCaseReview(caseId)
      .then((r) => {
        setReview(r)
        if (r) setForm({ verdict: r.verdict, note: r.note, reviewer: r.reviewer })
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [caseId])

  const handleSubmit = async () => {
    if (!form.verdict) {
      setError('Please select a verdict.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const record = await submitReview({ case_id: caseId, ...form })
      setReview(record)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const tabs = [
    { id: 'brief', label: 'Brief' },
    { id: 'eligibility', label: 'Eligibility' },
    { id: 'rights', label: 'Rights' },
    { id: 'sources', label: 'Sources' },
  ]

  const tabContent = brief
    ? {
        brief: brief.final_brief,
        eligibility: brief.eligibility_report,
        rights: brief.rights_report,
      }
    : {}

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <div>
          <div className={styles.panelCaseId}>{caseId}</div>
          {review && (
            <div className={`${styles.verdictBadge} ${styles[VERDICT_META[review.verdict]?.color]}`}>
              {VERDICT_META[review.verdict]?.icon} {VERDICT_META[review.verdict]?.label}
              {review.reviewer ? ` · ${review.reviewer}` : ''}
            </div>
          )}
        </div>
        <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
          ✕
        </button>
      </div>

      {loading ? (
        <div className={styles.panelLoading}>Loading...</div>
      ) : (
        <div className={styles.panelBody}>
          {brief ? (
            <div className={styles.briefSection}>
              <div className={styles.tabBar}>
                {tabs.map((t) => (
                  <button
                    key={t.id}
                    className={`${styles.tab} ${activeTab === t.id ? styles.tabActive : ''}`}
                    onClick={() => setActiveTab(t.id)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div className={styles.tabContent}>
                {activeTab === 'sources' ? (
                  <div className={styles.sourceList}>
                    {(brief.retrieved_sources || []).length === 0 ? (
                      <div className={styles.emptyNote}>No sources recorded.</div>
                    ) : (
                      (brief.retrieved_sources || []).map((s, i) => (
                        <div key={i} className={styles.sourceCard}>
                          <div className={styles.sourceTitle}>{s.title}</div>
                          <div className={styles.sourceMeta}>
                            {[s.source, s.category, s.court, s.document_id].filter(Boolean).join(' · ')}
                          </div>
                          <div className={styles.sourceExcerpt}>{s.excerpt}</div>
                          <div className={styles.sourceTags}>
                            {(s.used_by || []).map((tag) => (
                              <span key={tag} className={styles.sourceTag}>
                                {tag}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                ) : (
                  <div className={styles.markdown}>
                    <ReactMarkdown>{tabContent[activeTab] || '_No content available._'}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className={styles.noBrief}>
              <p>Brief not cached in this session.</p>
              <p className={styles.noBriefHint}>
                Run the analysis first from the Analysis page - the brief will appear here automatically.
              </p>
            </div>
          )}

          <div className={styles.reviewForm}>
            <div className={styles.reviewFormTitle}>Lawyer verdict</div>

            <div className={styles.verdictGroup}>
              {Object.entries(VERDICT_META)
                .filter(([k]) => k !== 'pending')
                .map(([val, meta]) => (
                  <label
                    key={val}
                    className={`${styles.verdictOption} ${styles[meta.color]} ${form.verdict === val ? styles.verdictSelected : ''}`}
                  >
                    <input
                      type="radio"
                      name="verdict"
                      value={val}
                      checked={form.verdict === val}
                      onChange={(e) => setForm((f) => ({ ...f, verdict: e.target.value }))}
                    />
                    <span className={styles.verdictIcon}>{meta.icon}</span>
                    {meta.label}
                  </label>
                ))}
            </div>

            <textarea
              className={styles.noteInput}
              placeholder="Notes for the advocate (optional)"
              value={form.note}
              onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))}
              rows={3}
            />

            <div className={styles.reviewFooter}>
              <input
                className={styles.reviewerInput}
                placeholder="Your name or initials"
                value={form.reviewer}
                onChange={(e) => setForm((f) => ({ ...f, reviewer: e.target.value }))}
              />
              <button className={`${styles.submitBtn} ${saved ? styles.submitSaved : ''}`} onClick={handleSubmit} disabled={saving}>
                {saving ? 'Saving...' : saved ? 'Saved' : review ? 'Update verdict' : 'Submit verdict'}
              </button>
            </div>
            {error && <div className={styles.formError}>{error}</div>}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ReviewPage() {
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    listReviews()
      .then(setReviews)
      .catch(() => setReviews([]))
      .finally(() => setLoading(false))
  }, [])

  const sessionCaseIds = (() => {
    try {
      return Object.keys(sessionStorage)
        .filter((k) => k.startsWith('brief:'))
        .map((k) => k.slice(6))
    } catch {
      return []
    }
  })()

  const reviewedIds = new Set(reviews.map((r) => r.case_id))
  const pendingIds = sessionCaseIds.filter((id) => !reviewedIds.has(id))
  const pendingRows = pendingIds.map((id) => ({ case_id: id, verdict: 'pending' }))

  const allRows = [...reviews, ...pendingRows]

  const counts = {
    all: allRows.length,
    pending: allRows.filter((r) => r.verdict === 'pending').length,
    approved: reviews.filter((r) => r.verdict === 'approved').length,
    flagged: reviews.filter((r) => r.verdict === 'flagged').length,
    needs_revision: reviews.filter((r) => r.verdict === 'needs_revision').length,
  }

  const filtered = filter === 'all' ? allRows : allRows.filter((r) => r.verdict === filter)

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>Lawyer review</h1>
          <p className={styles.pageSubtitle}>Review AI-generated briefs, verify citations, and record your verdict before filing.</p>
        </div>
        <div className={styles.statsRow}>
          {[
            { key: 'all', label: 'Total' },
            { key: 'pending', label: 'Pending' },
            { key: 'approved', label: 'Approved' },
            { key: 'flagged', label: 'Flagged' },
            { key: 'needs_revision', label: 'Needs revision' },
          ].map(({ key, label }) => (
            <button
              key={key}
              className={`${styles.statChip} ${filter === key ? styles.statActive : ''}`}
              onClick={() => setFilter(key)}
            >
              <span className={styles.statCount}>{counts[key] ?? 0}</span>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.layout}>
        <div className={styles.caseList}>
          {loading ? (
            <div className={styles.listLoading}>Loading reviews...</div>
          ) : filtered.length === 0 ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>⚖</div>
              <div className={styles.emptyTitle}>{filter === 'all' ? 'No cases yet' : `No ${filter.replace('_', ' ')} cases`}</div>
              <div className={styles.emptyHint}>Analyze a case from the Analysis page - it will appear here for review.</div>
            </div>
          ) : (
            filtered.map((row) => {
              const meta = VERDICT_META[row.verdict] || VERDICT_META.pending
              const isOpen = selected === row.case_id
              return (
                <div
                  key={row.case_id}
                  className={`${styles.caseRow} ${isOpen ? styles.caseRowOpen : ''}`}
                  onClick={() => setSelected(isOpen ? null : row.case_id)}
                >
                  <div className={styles.caseRowLeft}>
                    <div className={styles.caseRowId}>{row.case_id}</div>
                    {row.reviewed_at && (
                      <div className={styles.caseRowDate}>
                        {new Date(row.reviewed_at).toLocaleDateString('en-IN', {
                          day: 'numeric',
                          month: 'short',
                          year: 'numeric',
                        })}
                        {row.reviewer ? ` · ${row.reviewer}` : ''}
                      </div>
                    )}
                  </div>
                  <div className={styles.caseRowRight}>
                    <span className={`${styles.verdictBadge} ${styles[meta.color]}`}>
                      {meta.icon} {meta.label}
                    </span>
                    <span className={styles.chevron}>{isOpen ? '▲' : '▼'}</span>
                  </div>
                </div>
              )
            })
          )}
        </div>

        {selected && <CasePanel key={selected} caseId={selected} onClose={() => setSelected(null)} />}
      </div>
    </div>
  )
}
