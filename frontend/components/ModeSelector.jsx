'use client'

import React, { useEffect, useMemo, useState } from 'react'
import api from '@/lib/axios'
import styles from '@/styles/ModeSelector.module.css'

function ModeSelector({ modes, currentMode, onModeChange, onModeCreated, onModeDeleted }) {
  const [isOpen, setIsOpen] = useState(false)
  const [name, setName] = useState('')
  const [emoji, setEmoji] = useState('✨')
  const [baseRole, setBaseRole] = useState('')
  const [description, setDescription] = useState('')
  const [defaultTags, setDefaultTags] = useState('') // comma-separated
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [templates, setTemplates] = useState([])
  const [templatesLoaded, setTemplatesLoaded] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [deleting, setDeleting] = useState(false)

  if (!modes || modes.length === 0) {
    return <div style={{ color: 'white', padding: '1rem' }}>No modes available</div>
  }

  const availableBorrowSources = useMemo(() => {
    const byId = new Map()
    ;(modes || []).forEach((m) => byId.set(m.id, m))
    ;(templates || []).forEach((t) => {
      if (!byId.has(t.key)) {
        byId.set(t.key, { id: t.key, name: t.name, emoji: t.emoji })
      }
    })
    return Array.from(byId.values())
  }, [modes, templates])

  const resetForm = () => {
    setName('')
    setEmoji('✨')
    setBaseRole('')
    setDescription('')
    setDefaultTags('')
    setError('')
  }

  const close = () => {
    setIsOpen(false)
    resetForm()
  }

  const loadTemplates = async () => {
    if (templatesLoaded) return
    try {
      const res = await api.get('/mode-templates')
      const list = Array.isArray(res.data?.templates) ? res.data.templates : []
      setTemplates(list)
    } catch (e) {
      setTemplates([])
    } finally {
      setTemplatesLoaded(true)
    }
  }

  useEffect(() => {
    if (isOpen) loadTemplates()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  const applyTemplate = (t) => {
    // Pre-fill but keep editable
    setName(t.name || '')
    setEmoji(t.emoji || '✨')
    // Auto-set baseRole to match template key (e.g., fitness template -> baseRole: "fitness")
    setBaseRole(t.key || t.baseRole || '')
    setDescription(t.description || '')
    setDefaultTags(Array.isArray(t.defaultTags) ? t.defaultTags.join(', ') : '')
    setError('')
  }

  const handleCreate = async () => {
    setError('')
    if (!name.trim()) {
      setError('Mode name is required')
      return
    }
    try {
      setSaving(true)
      // Auto-generate baseRole from mode name if not set (slugify: lowercase, replace spaces with hyphens)
      const modeKey = name.trim().toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
      const finalBaseRole = baseRole || modeKey
      
      const res = await api.post('/modes', {
        name: name.trim(),
        emoji: emoji.trim() || '✨',
        baseRole: finalBaseRole,
        description: description.trim(),
        defaultTags: defaultTags
          .split(',')
          .map(s => s.trim())
          .filter(Boolean),
      })
      const created = res.data?.mode
      if (created && onModeCreated) {
        onModeCreated(created)
        onModeChange(created.id)
      }
      close()
    } catch (e) {
      setError(e?.response?.data?.error || e.message || 'Failed to create mode')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (modeId, modeName) => {
    if (deleteConfirm !== modeId) {
      setDeleteConfirm(modeId)
      return
    }
    
    try {
      setDeleting(true)
      // Use mode.key if available, otherwise use mode.id
      const mode = modes.find(m => m.id === modeId)
      const modeKey = mode?.key || modeId
      await api.delete(`/modes/${modeKey}`)
      if (onModeDeleted) {
        onModeDeleted(modeId)
      }
      // If deleted mode was current, switch to first available mode
      if (currentMode === modeId && modes.length > 1) {
        const remainingModes = modes.filter(m => m.id !== modeId)
        if (remainingModes.length > 0) {
          onModeChange(remainingModes[0].id)
        }
      }
      setDeleteConfirm(null)
    } catch (e) {
      setError(e?.response?.data?.error || e.message || 'Failed to delete mode')
      setDeleteConfirm(null)
    } finally {
      setDeleting(false)
    }
  }
  
  const canDeleteMode = (modeId) => {
    // Cannot delete core built-in modes
    const mode = modes.find(m => m.id === modeId)
    if (!mode) return false
    
    // Check both id and key fields
    const modeKey = mode.key || mode.id
    const protectedModes = ['student', 'parent', 'job', 'default']
    
    // Also check if it's marked as not custom (template mode)
    if (mode.isCustom === false) {
      return false
    }
    
    return !protectedModes.includes(modeKey)
  }
  
  return (
    <div className={styles['mode-selector']} style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
      {modes.map(mode => (
        <div
          key={mode.id}
          style={{
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem'
          }}
        >
          <button
            className={`${styles['mode-button']} ${currentMode === mode.id ? styles.active : ''}`}
            onClick={() => onModeChange(mode.id)}
            type="button"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.625rem',
              padding: '0.875rem 1.75rem',
              border: '2px solid white',
              background: currentMode === mode.id ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'white',
              color: currentMode === mode.id ? 'white' : '#667eea',
              borderRadius: '12px',
              cursor: 'pointer',
              fontWeight: 700,
              minWidth: '180px',
              justifyContent: 'center',
              boxShadow: currentMode === mode.id ? '0 4px 20px rgba(102, 126, 234, 0.4)' : '0 2px 10px rgba(0, 0, 0, 0.25)',
              transition: 'all 0.3s ease',
              fontSize: '0.95rem',
              opacity: 1,
              visibility: 'visible'
            }}
            onMouseEnter={(e) => {
              if (currentMode !== mode.id) {
                e.currentTarget.style.background = '#f8f9fa'
                e.currentTarget.style.transform = 'translateY(-2px)'
                e.currentTarget.style.boxShadow = '0 4px 16px rgba(0, 0, 0, 0.3)'
              }
            }}
            onMouseLeave={(e) => {
              if (currentMode !== mode.id) {
                e.currentTarget.style.background = 'white'
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.25)'
              } else {
                e.currentTarget.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
              }
            }}
          >
            <span style={{ fontSize: '1.3rem' }}>{mode.emoji}</span>
            <span>{mode.name}</span>
          </button>
          {canDeleteMode(mode.id) && (
            <button
              type="button"
              onClick={() => handleDelete(mode.id, mode.name)}
              disabled={deleting}
              style={{
                padding: '0.5rem',
                border: 'none',
                background: deleteConfirm === mode.id ? '#dc2626' : 'transparent',
                color: deleteConfirm === mode.id ? 'white' : '#6b7280',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '1rem',
                minWidth: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s ease'
              }}
              title={deleteConfirm === mode.id ? 'Click again to confirm delete' : 'Delete mode'}
            >
              {deleteConfirm === mode.id ? '✓' : '🗑️'}
            </button>
          )}
        </div>
      ))}

      <button
        type="button"
        onClick={() => setIsOpen(true)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.625rem',
          padding: '0.875rem 1.75rem',
          border: '2px dashed #667eea',
          background: 'white',
          color: '#667eea',
          borderRadius: '12px',
          cursor: 'pointer',
          fontWeight: 700,
          minWidth: '180px',
          justifyContent: 'center',
          boxShadow: '0 2px 10px rgba(0, 0, 0, 0.25)',
        }}
      >
        <span style={{ fontSize: '1.3rem' }}>➕</span>
        <span>Add Mode</span>
      </button>

      {isOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem',
            zIndex: 9999,
          }}
          onClick={close}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '520px',
              background: 'white',
              borderRadius: '16px',
              padding: '1.25rem 1.25rem 1rem',
              boxShadow: '0 16px 40px rgba(0,0,0,0.25)',
              maxHeight: '85vh',
              overflowY: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Add a new mode</h3>
              <button
                type="button"
                onClick={close}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '1.1rem' }}
              >
                ✕
              </button>
            </div>

            <div style={{ marginTop: '1rem', display: 'grid', gap: '0.75rem' }}>
              {/* Template gallery */}
              <div style={{ display: 'grid', gap: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: '0.9rem', fontWeight: 800 }}>Templates</span>
                  <span style={{ fontSize: '0.8rem', color: '#6b7280' }}>Click to pre-fill</span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: '0.5rem',
                  }}
                >
                  {(templates || []).map((t) => (
                    <button
                      key={t.key}
                      type="button"
                      onClick={() => applyTemplate(t)}
                      style={{
                        border: '1px solid #e5e7eb',
                        borderRadius: 12,
                        padding: '0.6rem 0.7rem',
                        background: 'white',
                        cursor: 'pointer',
                        textAlign: 'left',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '1.2rem' }}>{t.emoji}</span>
                        <span style={{ fontWeight: 800, fontSize: '0.9rem' }}>{t.name}</span>
                      </div>
                      {t.description ? (
                        <div style={{ marginTop: '0.25rem', fontSize: '0.8rem', color: '#6b7280' }}>
                          {t.description}
                        </div>
                      ) : null}
                    </button>
                  ))}
                </div>
              </div>

              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Mode name</span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Fitness Coach"
                  style={{
                    padding: '0.65rem 0.75rem',
                    borderRadius: '10px',
                    border: '1px solid #e5e7eb',
                    background: '#fff',
                    color: '#111827',
                  }}
                />
              </label>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <label style={{ display: 'grid', gap: '0.35rem' }}>
                  <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Emoji</span>
                  <input
                    value={emoji}
                    onChange={(e) => setEmoji(e.target.value)}
                    placeholder="✨"
                    style={{
                      padding: '0.65rem 0.75rem',
                      borderRadius: '10px',
                      border: '1px solid #e5e7eb',
                      background: '#fff',
                      color: '#111827',
                    }}
                  />
                </label>

              </div>

              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Description (optional)</span>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What is this mode for?"
                  rows={3}
                  style={{
                    padding: '0.65rem 0.75rem',
                    borderRadius: '10px',
                    border: '1px solid #e5e7eb',
                    resize: 'vertical',
                    background: '#fff',
                    color: '#111827',
                  }}
                />
              </label>

              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Default tags (comma-separated)</span>
                <input
                  value={defaultTags}
                  onChange={(e) => setDefaultTags(e.target.value)}
                  placeholder="e.g., health, fitness, habits"
                  style={{
                    padding: '0.65rem 0.75rem',
                    borderRadius: '10px',
                    border: '1px solid #e5e7eb',
                    background: '#fff',
                    color: '#111827',
                  }}
                />
              </label>

              {error && <div style={{ color: '#b91c1c', fontSize: '0.9rem' }}>{error}</div>}

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '0.25rem' }}>
                <button
                  type="button"
                  onClick={close}
                  disabled={saving}
                  style={{
                    padding: '0.65rem 0.9rem',
                    borderRadius: '10px',
                    border: '1px solid #e5e7eb',
                    background: 'white',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleCreate}
                  disabled={saving}
                  style={{
                    padding: '0.65rem 0.9rem',
                    borderRadius: '10px',
                    border: 'none',
                    background: '#667eea',
                    color: 'white',
                    cursor: 'pointer',
                    fontWeight: 700,
                    opacity: saving ? 0.85 : 1,
                  }}
                >
                  {saving ? 'Creating…' : 'Create mode'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ModeSelector

