'use client'

import React from 'react'
import styles from '@/styles/ModeSelector.module.css'

function ModeSelector({ modes, currentMode, onModeChange }) {
  if (!modes || modes.length === 0) {
    return <div style={{ color: 'white', padding: '1rem' }}>No modes available</div>
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
    </div>
  )
}

export default ModeSelector

