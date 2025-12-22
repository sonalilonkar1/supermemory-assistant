'use client'

import React, { useState, useEffect } from 'react'
import api from '@/lib/axios'
import styles from '@/styles/Connectors.module.css'

const CONNECTOR_PROVIDERS = [
  {
    id: 'gmail',
    name: 'Gmail',
    emoji: '📧',
    description: 'Import emails and conversations to build your profile',
    color: '#EA4335'
  },
  {
    id: 'linkedin',
    name: 'LinkedIn',
    emoji: '💼',
    description: 'Import your profile, work experience, and education',
    color: '#0077B5'
  },
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

  const handleDisconnect = async (provider) => {

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

              {connector?.lastSyncAt && (
                <div className={styles.lastSync}>
                  Last synced: {new Date(connector.lastSyncAt).toLocaleDateString()}
                </div>
              )}

              <div className={styles.actions}>
                {!isConnected && !isPending && (
                  <button
                    onClick={() => handleConnect(provider.id)}
                    disabled={isConnecting || isSyncing}
                    className={styles.connectButton}
                    style={{ backgroundColor: provider.color }}
                  >
                    {isConnecting ? 'Connecting...' : 'Connect'}
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

