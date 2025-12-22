'use client'

import React, { useState } from 'react'
import api from '@/lib/axios'
import styles from '@/styles/ModeSelector.module.css'

function ModeSelector({ modes, currentMode, onModeChange, onModeCreated }) {
  const [isOpen, setIsOpen] = useState(false)
  const [name, setName] = useState('')
  const [emoji, setEmoji] = useState('✨')
  const [baseRole, setBaseRole] = useState('student')
  const [description, setDescription] = useState('')
  const [defaultTags, setDefaultTags] = useState('') // comma-separated
  const [crossModeSources, setCrossModeSources] = useState([]) // array of mode keys
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  if (!modes || modes.length === 0) {
    return <div style={{ color: 'white', padding: '1rem' }}>No modes available</div>
  }

  const resetForm = () => {
    setName('')
    setEmoji('✨')
    setBaseRole('student')
    setDescription('')
    setDefaultTags('')
    setCrossModeSources([])
    setError('')
  }

  const close = () => {
    setIsOpen(false)
    resetForm()
  }

  const handleCreate = async () => {
    setError('')
    if (!name.trim()) {
      setError('Mode name is required')
      return
    }
    try {
      setSaving(true)
      const res = await api.post('/modes', {
        name: name.trim(),
        emoji: emoji.trim() || '✨',
        baseRole,
        description: description.trim(),
        defaultTags: defaultTags
          .split(',')
          .map(s => s.trim())
          .filter(Boolean),
        crossModeSources,
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
  
  return (
    <div className={styles['mode-selector']} style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
      {modes.map(mode => (
        <button
          key={mode.id}
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
              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Mode name</span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Fitness Coach"
                  style={{ padding: '0.65rem 0.75rem', borderRadius: '10px', border: '1px solid #e5e7eb' }}
                />
              </label>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <label style={{ display: 'grid', gap: '0.35rem' }}>
                  <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Emoji</span>
                  <input
                    value={emoji}
                    onChange={(e) => setEmoji(e.target.value)}
                    placeholder="✨"
                    style={{ padding: '0.65rem 0.75rem', borderRadius: '10px', border: '1px solid #e5e7eb' }}
                  />
                </label>

                <label style={{ display: 'grid', gap: '0.35rem' }}>
                  <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Base role (behavior)</span>
                  <select
                    value={baseRole}
                    onChange={(e) => setBaseRole(e.target.value)}
                    style={{ padding: '0.65rem 0.75rem', borderRadius: '10px', border: '1px solid #e5e7eb' }}
                  >
                    <option value="student">Student</option>
                    <option value="parent">Parent</option>
                    <option value="job">Job</option>
                  </select>
                </label>
              </div>

              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Description (optional)</span>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What is this mode for?"
                  rows={3}
                  style={{ padding: '0.65rem 0.75rem', borderRadius: '10px', border: '1px solid #e5e7eb', resize: 'vertical' }}
                />
              </label>

              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Default tags (comma-separated)</span>
                <input
                  value={defaultTags}
                  onChange={(e) => setDefaultTags(e.target.value)}
                  placeholder="e.g., health, fitness, habits"
                  style={{ padding: '0.65rem 0.75rem', borderRadius: '10px', border: '1px solid #e5e7eb' }}
                />
              </label>

              <div style={{ display: 'grid', gap: '0.35rem' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Cross-mode sources (borrow from)</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {modes.map((m) => (
                    <label key={m.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.9rem' }}>
                      <input
                        type="checkbox"
                        checked={crossModeSources.includes(m.id)}
                        onChange={(e) => {
                          const checked = e.target.checked
                          setCrossModeSources((prev) => {
                            if (checked) return Array.from(new Set([...prev, m.id]))
                            return prev.filter((x) => x !== m.id)
                          })
                        }}
                      />
                      <span>{m.emoji} {m.name}</span>
                    </label>
                  ))}
                </div>
                <span style={{ fontSize: '0.8rem', color: '#6b7280' }}>
                  The assistant can pull a tiny, relevant slice from these modes during chat only (UI stays separated).
                </span>
              </div>

              <p style={{ margin: 0, fontSize: '0.85rem', color: '#6b7280' }}>
                Base role controls assistant behavior + profile slicing. Memories remain isolated to the new mode.
              </p>

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

