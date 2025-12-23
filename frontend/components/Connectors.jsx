'use client'

import React, { useState, useEffect } from 'react'
import api from '@/lib/axios'
import styles from '@/styles/Connectors.module.css'

const SUPPORTED_PROVIDERS = ['notion', 'google-drive', 'onedrive', 'web-crawler', 'github']

const CONNECTOR_PROVIDERS = [
  {
    id: 'google-drive',
    name: 'Google Drive',
    emoji: '📁',
    description: 'Sync documents from your Google Drive',
    color: '#4285F4'
  },
  {
    id: 'notion',
    name: 'Notion',
    emoji: '📝',
    description: 'Import notes and pages from Notion',
    color: '#000000'
  },
  {
    id: 'onedrive',
    name: 'OneDrive',
    emoji: '☁️',
    description: 'Sync documents from Microsoft OneDrive',
    color: '#0078D4'
  },
  {
    id: 'web-crawler',
    name: 'Web Crawler',
    emoji: '🕷️',
    description: 'Crawl websites and import content',
    color: '#6366F1'
  },
  {
    id: 'github',
    name: 'GitHub',
    emoji: '🐙',
    description: 'Ingest issues and repos (via Supermemory connector)',
    color: '#24292e'
  }
]

function Connectors({ userId }) {
  const [connectors, setConnectors] = useState([])
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(null)
  const [syncing, setSyncing] = useState(null)
  const [calendarUploading, setCalendarUploading] = useState(false)
  const calendarInputRef = React.useRef(null)

  useEffect(() => {
    loadConnectors()
  }, [userId])

  const loadConnectors = async () => {
    try {
      const response = await api.get('/connectors')
      setConnectors(response.data.connectors || [])
    } catch (error) {
      console.error('Error loading connectors:', error)
      setConnectors([])
    } finally {
      setLoading(false)
    }
  }

  const getConnectorStatus = (provider) => {
    const connector = connectors.find(c => c.provider === provider)
    return connector ? connector.status : 'disconnected'
  }

  const handleConnect = async (provider) => {
    if (!SUPPORTED_PROVIDERS.includes(provider)) {
      alert(`${provider} connector is not yet supported by the Supermemory API. Coming soon.`);
      setConnecting(null)
      return
    }
    setConnecting(provider)
    try {
      const redirectUrl = `${window.location.origin}/connectors/callback`
      const response = await api.post(`/connectors/${provider}/connect`, {
        redirectUrl
      })

      if (response.data.requiresOAuth && response.data.authUrl) {
        // Open OAuth flow in new window
        const authWindow = window.open(
          response.data.authUrl,
          'oauth',
          'width=600,height=700,scrollbars=yes'
        )

        // Poll for window close (OAuth completion)
        const pollTimer = setInterval(() => {
          if (authWindow.closed) {
            clearInterval(pollTimer)
            // Wait a moment for callback to process, then reload
            setTimeout(() => {
              loadConnectors()
              setConnecting(null)
            }, 2000)
          }
        }, 500)

        // Timeout after 5 minutes
        setTimeout(() => {
          clearInterval(pollTimer)
          if (!authWindow.closed) {
            authWindow.close()
          }
          setConnecting(null)
        }, 300000)
      } else {
        // Non-OAuth connector (like web-crawler) - connected immediately
        await loadConnectors()
        setConnecting(null)
      }
    } catch (error) {
      console.error(`Error connecting ${provider}:`, error)
      alert(`Failed to connect ${provider}: ${error.response?.data?.error || error.message}`)
      setConnecting(null)
    }
  }

  const handleSync = async (provider) => {
    setSyncing(provider)
    try {
      const response = await api.post(`/connectors/${provider}/sync`)
      if (response.data.success) {
        await loadConnectors()
        alert('Sync completed successfully!')
      } else {
        alert(`Sync failed: ${response.data.error || 'Unknown error'}`)
      }
    } catch (error) {
      console.error(`Error syncing ${provider}:`, error)
      alert(`Failed to sync: ${error.response?.data?.error || error.message}`)
    } finally {
      setSyncing(null)
    }
  }

  const handleCalendarUpload = async (file) => {
    if (!file) return
    setCalendarUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('mode', 'default')
      const res = await api.post('/calendar/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      alert(`Imported ${res.data?.imported || 0} events`)
    } catch (error) {
      console.error('Error importing calendar:', error)
      alert(`Failed to import calendar: ${error.response?.data?.error || error.message}`)
    } finally {
      setCalendarUploading(false)
      if (calendarInputRef.current) calendarInputRef.current.value = ''
    }
  }

  const handleDisconnect = async (provider) => {
    if (!confirm(`Are you sure you want to disconnect ${provider}?`)) {
      return
    }

    try {
      await api.delete(`/connectors/${provider}`)
      await loadConnectors()
      alert('Disconnected successfully')
    } catch (error) {
      console.error(`Error disconnecting ${provider}:`, error)
      alert(`Failed to disconnect: ${error.response?.data?.error || error.message}`)
    }
  }

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Loading connectors...</div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>🔌 Connectors</h2>
        <p className={styles.subtitle}>
          Connect your accounts to automatically build your profile and import data
        </p>
      </div>

      <div className={styles.grid}>
        {CONNECTOR_PROVIDERS.map(provider => {
          const status = getConnectorStatus(provider.id)
          const connector = connectors.find(c => c.provider === provider.id)
          const isConnected = status === 'connected'
          const isPending = status === 'pending'
          const isConnecting = connecting === provider.id
          const isSyncing = syncing === provider.id
          const comingSoon = provider.comingSoon === true

          return (
            <div
              key={provider.id}
              className={`${styles.card} ${isConnected ? styles.connected : ''}`}
              style={{ borderColor: provider.color }}
            >
              <div className={styles.cardHeader}>
                <span className={styles.emoji}>{provider.emoji}</span>
                <h3>{provider.name}</h3>
                <span
                  className={`${styles.status} ${styles[status]}`}
                  title={status}
                >
                  {isConnected ? '✓' : isPending ? '⏳' : '○'}
                </span>
              </div>

              <p className={styles.description}>{provider.description}</p>
              {comingSoon && <div className={styles.comingSoon}>Coming soon</div>}

              {connector?.lastSyncAt && (
                <div className={styles.lastSync}>
                  Last synced: {new Date(connector.lastSyncAt).toLocaleDateString()}
                </div>
              )}

              <div className={styles.actions}>
                {!isConnected && !isPending && (
                  <button
                    onClick={() => handleConnect(provider.id)}
                    disabled={isConnecting || isSyncing || comingSoon}
                    className={styles.connectButton}
                    style={{ backgroundColor: provider.color }}
                  >
                    {comingSoon ? 'Unavailable' : isConnecting ? 'Connecting...' : 'Connect'}
                  </button>
                )}

                {isPending && (
                  <div className={styles.pending}>
                    <span>⏳ Authorization pending...</span>
                  </div>
                )}

                {isConnected && (
                  <>
                    <button
                      onClick={() => handleSync(provider.id)}
                      disabled={isSyncing}
                      className={styles.syncButton}
                    >
                      {isSyncing ? 'Syncing...' : '🔄 Sync Now'}
                    </button>
                    <button
                      onClick={() => handleDisconnect(provider.id)}
                      className={styles.disconnectButton}
                    >
                      Disconnect
                    </button>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>


      <div className={styles.grid}>
        <div
          className={`${styles.card}`}
          style={{ borderColor: '#2563eb' }}
        >
          <div className={styles.cardHeader}>
            <span className={styles.emoji}>📅</span>
            <h3>Calendar (.ics)</h3>
            <span className={`${styles.status} ${styles.connected}`} title="manual">
              ●
            </span>
          </div>
          <p className={styles.description}>Import events from an ICS file to create event memories.</p>
          <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.5rem', padding: '0.75rem', background: '#f9fafb', borderRadius: '8px' }}>
            <strong>How to get .ics file:</strong>
            <ul style={{ margin: '0.5rem 0 0 1.25rem', padding: 0 }}>
              <li><strong>Google Calendar:</strong> Settings → Import & export → Export</li>
              <li><strong>Apple Calendar:</strong> File → Export → Export...</li>
              <li><strong>Outlook:</strong> Settings → Calendar → Publish calendar → Copy ICS link</li>
            </ul>
            <div style={{ marginTop: '0.5rem', fontSize: '0.75rem' }}>
              💡 Tip: For automated sync, use n8n workflow (see docs)
            </div>
          </div>
          <div className={styles.actions}>
            <input
              type="file"
              accept=".ics,text/calendar"
              ref={calendarInputRef}
              style={{ display: 'none' }}
              onChange={(e) => handleCalendarUpload(e.target.files?.[0])}
            />
            <button
              onClick={() => calendarInputRef.current?.click()}
              disabled={calendarUploading}
              className={styles.syncButton}
            >
              {calendarUploading ? 'Importing...' : '📥 Import .ics'}
            </button>
          </div>
        </div>
      </div>

      {connectors.length === 0 && (
        <div className={styles.empty}>
          <p>No connectors connected yet. Connect your accounts to get started!</p>
        </div>
      )}
    </div>
  )
}

export default Connectors

