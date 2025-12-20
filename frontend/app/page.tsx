'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Chat from '@/components/Chat'
import Memories from '@/components/Memories'
import MemoryGraph from '@/components/MemoryGraph'
import ModeSelector from '@/components/ModeSelector'
import { isAuthenticated, getUser, clearAuth } from '@/lib/auth'
import styles from '@/styles/App.module.css'

const MODES = [
  { id: 'student', name: 'Student Assistant', emoji: '🎓' },
  { id: 'parent', name: 'Parent / Family Planner', emoji: '👨‍👩‍👧' },
  { id: 'job', name: 'Job-Hunt Assistant', emoji: '💼' }
]

export default function Home() {
  const router = useRouter()
  const [currentMode, setCurrentMode] = useState('student')
  const [activeTab, setActiveTab] = useState('chat')
  const [user, setUser] = useState(getUser())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check authentication
    if (!isAuthenticated()) {
      router.push('/login')
    } else {
      setUser(getUser())
      setLoading(false)
    }
  }, [router])

  const handleLogout = () => {
    clearAuth()
    router.push('/login')
  }

  if (loading) {
    return (
      <div className={styles.app}>
        <div style={{ textAlign: 'center', padding: '4rem' }}>
          <p>Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return null // Will redirect
  }

  return (
    <div className={styles.app}>
      <header className={styles['app-header']}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
          <h1>Supermemory Assistant</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '0.9rem', opacity: 0.9 }}>{user.name || user.email}</span>
            <button
              onClick={handleLogout}
              style={{
                padding: '0.5rem 1rem',
                background: 'rgba(255, 255, 255, 0.2)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                borderRadius: '8px',
                color: 'white',
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontWeight: 500,
                transition: 'all 0.2s ease',
                position: 'relative',
                zIndex: 1
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.3)'
                e.currentTarget.style.transform = 'translateY(-1px)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.2)'
                e.currentTarget.style.transform = 'translateY(0)'
              }}
            >
              🚪 Logout
            </button>
          </div>
        </div>
        <ModeSelector
          modes={MODES}
          currentMode={currentMode}
          onModeChange={setCurrentMode}
        />
      </header>

      <nav className={styles['app-nav']} style={{ display: 'flex', gap: '1rem', padding: '1.5rem 2rem' }}>
        <button
          className={activeTab === 'chat' ? styles.active : ''}
          onClick={() => setActiveTab('chat')}
          style={{
            padding: '0.875rem 1.75rem',
            margin: 0,
            border: '2px solid transparent',
            borderRadius: '12px',
            fontSize: '0.95rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.3s ease',
            background: activeTab === 'chat' ? '#667eea' : 'transparent',
            color: activeTab === 'chat' ? 'white' : 'inherit'
          }}
        >
          💬 Chat
        </button>
        <button
          className={activeTab === 'memories' ? styles.active : ''}
          onClick={() => setActiveTab('memories')}
          style={{
            padding: '0.875rem 1.75rem',
            margin: 0,
            border: '2px solid transparent',
            borderRadius: '12px',
            fontSize: '0.95rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.3s ease',
            background: activeTab === 'memories' ? '#667eea' : 'transparent',
            color: activeTab === 'memories' ? 'white' : 'inherit'
          }}
        >
          🧠 Memories
        </button>
        <button
          className={activeTab === 'graph' ? styles.active : ''}
          onClick={() => setActiveTab('graph')}
          style={{
            padding: '0.875rem 1.75rem',
            margin: 0,
            border: '2px solid transparent',
            borderRadius: '12px',
            fontSize: '0.95rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.3s ease',
            background: activeTab === 'graph' ? '#667eea' : 'transparent',
            color: activeTab === 'graph' ? 'white' : 'inherit'
          }}
        >
          📊 Memory Graph
        </button>
      </nav>

      <main className={styles['app-main']}>
        <div style={{ display: activeTab === 'chat' ? 'block' : 'none' }}>
          <Chat mode={currentMode} userId={user.id} />
        </div>
        <div style={{ display: activeTab === 'memories' ? 'block' : 'none' }}>
          <Memories mode={currentMode} userId={user.id} />
        </div>
        <div style={{ display: activeTab === 'graph' ? 'block' : 'none' }}>
          <MemoryGraph mode={currentMode} userId={user.id} />
        </div>
      </main>
    </div>
  )
}

