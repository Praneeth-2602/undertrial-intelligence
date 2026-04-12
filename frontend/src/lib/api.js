const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })

  const text = await response.text()
  const payload = text ? safeJsonParse(text) : null

  if (!response.ok) {
    const message = payload?.detail || payload?.message || response.statusText || 'Request failed'
    throw new Error(message)
  }

  return payload
}

function safeJsonParse(text) {
  try {
    return JSON.parse(text)
  } catch {
    return { message: text }
  }
}

export async function healthCheck() {
  return requestJson('/health')
}

export async function analyzeCase(caseData) {
  return requestJson('/analyze', {
    method: 'POST',
    body: JSON.stringify(caseData),
  })
}

export async function ingestPdf(file, category = 'statute', court = '') {
  const formData = new FormData()
  formData.append('file', file)

  const params = new URLSearchParams()
  if (category) params.set('category', category)
  if (court) params.set('court', court)

  const response = await fetch(`${API_BASE}/ingest/pdf?${params.toString()}`, {
    method: 'POST',
    body: formData,
  })

  const text = await response.text()
  const payload = text ? safeJsonParse(text) : null

  if (!response.ok) {
    const message = payload?.detail || payload?.message || response.statusText || 'Request failed'
    throw new Error(message)
  }

  return payload
}

export async function ingestKanoon(query, text = '', limit = 5) {
  return requestJson('/ingest/kanoon', {
    method: 'POST',
    body: JSON.stringify({ query, text, limit }),
  })
}

export async function submitReview({ case_id, verdict, note = '', reviewer = '' }) {
  return requestJson('/review', {
    method: 'POST',
    body: JSON.stringify({ case_id, verdict, note, reviewer }),
  })
}

export async function getCaseReview(caseId) {
  return requestJson(`/review/${encodeURIComponent(caseId)}`)
}

export async function listReviews() {
  return requestJson('/reviews')
}
