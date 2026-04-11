import { NavLink } from 'react-router-dom'
import styles from './Header.module.css'

export default function Header({ serverStatus = 'checking' }) {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.brandBlock}>
          <div className={styles.brandMark}>UT</div>
          <div>
            <div className={styles.brand}>Undertrial Intelligence</div>
            <div className={styles.tagline}>Legal research and bail drafting workspace</div>
          </div>
        </div>

        <nav className={styles.nav} aria-label="Primary">
          <NavLink to="/" end className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
            Analysis
          </NavLink>
          <NavLink to="/knowledge" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
            Knowledge Base
          </NavLink>
          <NavLink to="/about" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
            About
          </NavLink>
        </nav>

        <div className={styles.status}>
          <span className={`${styles.dot} ${styles[serverStatus] || styles.checking}`} />
          <span className={styles.statusText}>
            {serverStatus === 'online' ? 'Backend online' : serverStatus === 'offline' ? 'Backend offline' : 'Checking backend'}
          </span>
        </div>
      </div>
    </header>
  )
}
