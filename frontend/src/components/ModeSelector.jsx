import React from 'react'
import './ModeSelector.css'

function ModeSelector({ modes, currentMode, onModeChange }) {
  return (
    <div className="mode-selector">
      {modes.map(mode => (
        <button
          key={mode.id}
          className={`mode-button ${currentMode === mode.id ? 'active' : ''}`}
          onClick={() => onModeChange(mode.id)}
        >
          <span className="mode-emoji">{mode.emoji}</span>
          <span className="mode-name">{mode.name}</span>
        </button>
      ))}
    </div>
  )
}

export default ModeSelector

