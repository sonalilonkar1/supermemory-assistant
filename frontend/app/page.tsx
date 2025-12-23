'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Chat from '@/components/Chat'
import Memories from '@/components/Memories'
import MemoryGraph from '@/components/MemoryGraph'
import ModeSelector from '@/components/ModeSelector'
import Connectors from '@/components/Connectors'
import { isAuthenticated, getUser, clearAuth } from '@/lib/auth'
import api from '@/lib/axios'
import styles from '@/styles/App.module.css'

export default function Home() {
  const router = useRouter()
  const [currentMode, setCurrentMode] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'chat' | 'memories' | 'graph' | 'upcoming' | 'connectors'>('chat')
  const [user, setUser] = useState(getUser())
  const [loading, setLoading] = useState(true)
  const [modes, setModes] = useState<any[]>([])
  const [templates, setTemplates] = useState<any[]>([])
  const [events, setEvents] = useState<any[]>([])
  const [eventsLoading, setEventsLoading] = useState(false)
  const currentModeObj = modes.find((m: any) => m.id === currentMode) || null

  useEffect(() => {
    // Check authentication
    if (!isAuthenticated()) {
      router.push('/login')
    } else {
      setUser(getUser())
      setLoading(false)
    }
  }, [router])

  useEffect(() => {
    // Fetch user-defined modes from backend (empty means user hasn't created any)
    const loadModes = async () => {
      try {
        const res = await api.get('/modes')
        const fetched = res.data?.modes
        const list = Array.isArray(fetched) ? fetched : []
        setModes(list)
        if (list.length && !currentMode) setCurrentMode(list[0].id)
        if (list.length && currentMode && !list.some((m: any) => m.id === currentMode)) setCurrentMode(list[0].id)
      } catch (e) {
        setModes([])
      }
    }
    if (isAuthenticated()) loadModes()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id])

  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const res = await api.get('/mode-templates')
        setTemplates(Array.isArray(res.data?.templates) ? res.data.templates : [])
      } catch (e) {
        setTemplates([])
      }
    }
    if (isAuthenticated()) loadTemplates()
  }, [])

  const loadUpcomingEvents = async () => {
    try {
      setEventsLoading(true)
      const res = await api.get('/events/upcoming', { params: { limit: 50 } })
      setEvents(Array.isArray(res.data?.events) ? res.data.events : [])
    } catch (e) {
      setEvents([])
    } finally {
      setEventsLoading(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'upcoming') loadUpcomingEvents()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab])

  const [deleteProfileConfirm, setDeleteProfileConfirm] = useState(false)
  const [deletingProfile, setDeletingProfile] = useState(false)

  const handleLogout = () => {
    clearAuth()
    router.push('/login')
  }

  const handleDeleteProfile = async () => {
    if (!deleteProfileConfirm) {
      setDeleteProfileConfirm(true)
      return
    }
    
    if (!confirm('Are you sure you want to delete your profile? This will permanently delete all your data including modes, memories, conversations, and cannot be undone.')) {
      setDeleteProfileConfirm(false)
      return
    }
    
    try {
      setDeletingProfile(true)
      await api.delete('/auth/delete-profile')
      clearAuth()
      router.push('/login')
    } catch (e) {
      alert(e?.response?.data?.error || 'Failed to delete profile')
      setDeleteProfileConfirm(false)
    } finally {
      setDeletingProfile(false)
    }
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

  // First-run onboarding: user must create at least one mode (templates are optional suggestions)
  if (!currentMode) {
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
                }}
              >
                🚪 Logout
              </button>
              <button
                onClick={handleDeleteProfile}
                disabled={deletingProfile}
                style={{
                  padding: '0.5rem 1rem',
                  background: deleteProfileConfirm ? '#dc2626' : 'rgba(220, 38, 38, 0.2)',
                  border: '1px solid rgba(220, 38, 38, 0.3)',
                  borderRadius: '8px',
                  color: 'white',
                  cursor: deletingProfile ? 'not-allowed' : 'pointer',
                  fontSize: '0.85rem',
                  fontWeight: 500,
                  opacity: deletingProfile ? 0.6 : 1,
                }}
                title={deleteProfileConfirm ? 'Click again to confirm delete profile' : 'Delete profile'}
              >
                {deleteProfileConfirm ? '⚠️ Confirm Delete' : '🗑️ Delete Profile'}
              </button>
            </div>
          </div>
        </header>

        <main className={styles['app-main']} style={{ padding: '2rem' }}>
          <div style={{ maxWidth: 960, margin: '0 auto' }}>
            <h2 style={{ marginBottom: '0.5rem' }}>What parts of your life do you want help with?</h2>
            <p style={{ marginBottom: '1.25rem', color: '#6c757d' }}>
              Create modes for your roles (e.g., “Job Hunt – Spring 2026”, “Marathon training”, etc). Nothing is pre-added.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
              {templates.map((t) => (
                <button
                  key={t.key}
                  onClick={async () => {
                    const res = await api.post('/modes', {
                      name: t.name,
                      emoji: t.emoji,
                      baseRole: t.baseRole,
                      description: t.description,
                      defaultTags: t.defaultTags || [],
                      crossModeSources: t.crossModeSources || [],
                      key: t.key,
                    })
                    const created = res.data?.mode
                    if (created) {
                      setModes([created])
                      setCurrentMode(created.id)
                    }
                  }}
                  style={{
                    padding: '1rem',
                    borderRadius: 16,
                    border: '1px solid #e9ecef',
                    background: 'white',
                    cursor: 'pointer',
                    textAlign: 'left',
                    boxShadow: '0 2px 10px rgba(0,0,0,0.08)',
                  }}
                >
                  <div style={{ fontSize: '1.6rem' }}>{t.emoji}</div>
                  <div style={{ fontWeight: 800, marginTop: '0.35rem' }}>{t.name}</div>
                  <div style={{ fontSize: '0.9rem', color: '#6c757d', marginTop: '0.35rem' }}>{t.description}</div>
                </button>
              ))}
            </div>

            <div style={{ marginTop: '1.25rem' }}>
              <p style={{ marginBottom: '0.5rem', fontWeight: 700 }}>Or create your own:</p>
              <ModeSelector
                modes={[]}
                currentMode={''}
                onModeChange={() => {}}
                onModeCreated={(createdMode: any) => {
                  setModes([createdMode])
                  setCurrentMode(createdMode.id)
                }}
                onModeDeleted={() => {}}
              />
            </div>
          </div>
        </main>
      </div>
    )
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
            <button
              onClick={handleDeleteProfile}
              disabled={deletingProfile}
              style={{
                padding: '0.5rem 1rem',
                background: deleteProfileConfirm ? '#dc2626' : 'rgba(220, 38, 38, 0.2)',
                border: '1px solid rgba(220, 38, 38, 0.3)',
                borderRadius: '8px',
                color: 'white',
                cursor: deletingProfile ? 'not-allowed' : 'pointer',
                fontSize: '0.85rem',
                fontWeight: 500,
                opacity: deletingProfile ? 0.6 : 1,
                transition: 'all 0.2s ease',
              }}
              title={deleteProfileConfirm ? 'Click again to confirm delete profile' : 'Delete profile'}
            >
              {deleteProfileConfirm ? '⚠️ Confirm Delete' : '🗑️ Delete Profile'}
            </button>
          </div>
        </div>
        <ModeSelector
          modes={modes}
          currentMode={currentMode}
          onModeChange={setCurrentMode}
          onModeCreated={(createdMode: any) => {
            setModes((prev: any[]) => [...prev, createdMode])
          }}
          onModeDeleted={(deletedModeId: string) => {
            setModes((prev: any[]) => prev.filter((m: any) => m.id !== deletedModeId))
            // Reload modes to get updated list
            const loadModes = async () => {
              try {
                const res = await api.get('/modes')
                const fetched = res.data?.modes
                const list = Array.isArray(fetched) ? fetched : []
                setModes(list)
                if (list.length && currentMode === deletedModeId) {
                  setCurrentMode(list[0].id)
                }
              } catch (e) {
                setModes([])
              }
            }
            loadModes()
          }}
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

        <button
          className={activeTab === 'upcoming' ? styles.active : ''}
          onClick={() => setActiveTab('upcoming')}
          style={{
            padding: '0.875rem 1.75rem',
            margin: 0,
            border: '2px solid transparent',
            borderRadius: '12px',
            fontSize: '0.95rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.3s ease',
            background: activeTab === 'upcoming' ? '#667eea' : 'transparent',
            color: activeTab === 'upcoming' ? 'white' : 'inherit'
          }}
        >
          📅 Upcoming
        </button>

        <button
          className={activeTab === 'connectors' ? styles.active : ''}
          onClick={() => setActiveTab('connectors')}
          style={{
            padding: '0.875rem 1.75rem',
            margin: 0,
            border: '2px solid transparent',
            borderRadius: '12px',
            fontSize: '0.95rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.3s ease',
            background: activeTab === 'connectors' ? '#667eea' : 'transparent',
            color: activeTab === 'connectors' ? 'white' : 'inherit'
          }}
        >
          🔌 Connectors
        </button>
      </nav>

      <main className={styles['app-main']}>
        <div style={{ display: activeTab === 'chat' ? 'block' : 'none' }}>
          <Chat mode={currentMode} modeLabel={currentModeObj?.name} userId={user.id} />
        </div>
        <div style={{ display: activeTab === 'memories' ? 'block' : 'none' }}>
          <Memories mode={currentMode} modeLabel={currentModeObj?.name} userId={user.id} />
        </div>
        <div style={{ display: activeTab === 'graph' ? 'block' : 'none' }}>
          <MemoryGraph mode={currentMode} modeLabel={currentModeObj?.name} userId={user.id} />
        </div>
        <div style={{ display: activeTab === 'upcoming' ? 'block' : 'none' }}>
          <div style={{ padding: '2rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0 }}>Upcoming Events (All Modes)</h2>
              <button
                onClick={loadUpcomingEvents}
                style={{
                  padding: '0.6rem 1rem',
                  background: '#667eea',
                  color: 'white',
                  border: 'none',
                  borderRadius: '10px',
                  cursor: 'pointer',
                  fontWeight: 700
                }}
              >
                🔄 Refresh
              </button>
            </div>

            {eventsLoading ? (
              <div style={{ padding: '1.5rem 0', color: '#6c757d' }}>Loading events...</div>
            ) : events.length === 0 ? (
              <div style={{ padding: '1.5rem 0', color: '#6c757d' }}>
                No upcoming events yet. Add dates like “Interview on 2026-03-07” or “Exam on March 5”.
              </div>
            ) : (
              <div style={{ marginTop: '1rem', display: 'grid', gap: '0.75rem' }}>
                {events.map((e, idx) => (
                  <div
                    key={e.id || `event-${idx}`}
                    style={{
                      background: 'white',
                      border: '1px solid #e9ecef',
                      borderRadius: 14,
                      padding: '1rem 1.25rem',
                      boxShadow: '0 2px 10px rgba(0,0,0,0.06)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '1rem',
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: '1rem', color: '#111827', marginBottom: '0.35rem' }}>
                        {e.title || 'Event'}
                      </div>
                      <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>
                        📅 {new Date(e.date).toLocaleDateString('en-US', { 
                          weekday: 'short', 
                          year: 'numeric', 
                          month: 'short', 
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                    </div>
                    <div style={{ 
                      alignSelf: 'center', 
                      fontWeight: 600,
                      fontSize: '0.875rem',
                      color: '#667eea',
                      padding: '0.4rem 0.75rem',
                      background: '#f3f4f6',
                      borderRadius: '8px'
                    }}>
                      {e.modeEmoji} {e.modeName}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <div style={{ display: activeTab === 'connectors' ? 'block' : 'none' }}>
          <Connectors userId={user.id} />
        </div>
      </main>
    </div>
  )
}

