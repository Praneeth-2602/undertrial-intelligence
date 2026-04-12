// api_review.js — add these functions to your existing frontend/src/lib/api.js
//
// HOW TO PLUG IN:
//   Copy the three functions below and paste them at the bottom of api.js.
//   Nothing else needs to change in api.js.

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  const text = await response.text()
  const payload = text ? JSON.parse(text) : null
  if (!response.ok) {
    const message = payload?.detail || payload?.message || response.statusText || 'Request failed'
    throw new Error(message)
  }
  return payload
}

// Submit or update a lawyer review verdict for a case.
// verdict: "approved" | "flagged" | "needs_revision"
export async function submitReview({ case_id, verdict, note, reviewer }) {
  return requestJson('/review', {
    method: 'POST',
    body: JSON.stringify({ case_id, verdict, note, reviewer }),
  })
}

// Fetch the current review for a single case (returns null if not reviewed yet).
export async function getCaseReview(case_id) {
  return requestJson(`/review/${encodeURIComponent(case_id)}`)
}

// List all reviews — used by the review dashboard page.
export async function listReviews() {
  return requestJson('/reviews')
}
