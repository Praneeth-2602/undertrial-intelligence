import React, { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import AnalysisPage from './pages/AnalysisPage'
import KnowledgePage from './pages/KnowledgePage'
import AboutPage from './pages/AboutPage'
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
        <Route path="/about" element={<AboutPage />} />
      </Routes>
    </BrowserRouter>
  )
}
