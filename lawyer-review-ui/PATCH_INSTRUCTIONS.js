// ─────────────────────────────────────────────────────────────────────────────
// PATCH INSTRUCTIONS — 3 small edits to wire in the review page
// ─────────────────────────────────────────────────────────────────────────────

// ── 1. frontend/src/pages/AnalysisPage.jsx ───────────────────────────────────
//
// After line 43 (the setResult(data) call), add ONE line to cache the brief:
//
//   setResult(data)
//   sessionStorage.setItem(`brief:${data.case_id}`, JSON.stringify(data))  // ← ADD
//
// This is all AnalysisPage needs — no other changes.


// ── 2. frontend/src/App.jsx ───────────────────────────────────────────────────
//
// Replace the existing App.jsx with this:

import React, { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import AnalysisPage from './pages/AnalysisPage'
import KnowledgePage from './pages/KnowledgePage'
import AboutPage from './pages/AboutPage'
import ReviewPage from './pages/ReviewPage'        // ← NEW
import { healthCheck } from './lib/api'

export default function App() {
  const [serverStatus, setServerStatus] = useState('checking')

  useEffect(() => {
    const check = async () => {
      try {
        await healthCheck()
        setServerStatus('online')
      } catch {
        setServerStatus('offline')
      }
    }

    check()
    const interval = setInterval(check, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <BrowserRouter>
      <Header serverStatus={serverStatus} />
      <Routes>
        <Route path="/" element={<AnalysisPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/review" element={<ReviewPage />} />         {/* ← NEW */}
        <Route path="/about" element={<AboutPage />} />
      </Routes>
    </BrowserRouter>
  )
}


// ── 3. frontend/src/components/Header.jsx ────────────────────────────────────
//
// Add one NavLink for the Review page.
// Replace the entire <nav> block (the three NavLinks) with this:

/*
  <nav className={styles.nav} aria-label="Primary">
    <NavLink to="/" end className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
      Analysis
    </NavLink>
    <NavLink to="/knowledge" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
      Knowledge Base
    </NavLink>
    <NavLink to="/review" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
      Lawyer Review
    </NavLink>
    <NavLink to="/about" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
      About
    </NavLink>
  </nav>
*/
