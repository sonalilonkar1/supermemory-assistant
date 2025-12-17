import React, { useState } from 'react'
import Chat from './components/Chat'
import Memories from './components/Memories'
import MemoryGraph from './components/MemoryGraph'
import ModeSelector from './components/ModeSelector'
import './App.css'

const MODES = [
  { id: 'student', name: 'Student Assistant', emoji: '🎓' },
  { id: 'parent', name: 'Parent / Family Planner', emoji: '👨‍👩‍👧' },
  { id: 'job', name: 'Job-Hunt Assistant', emoji: '💼' }
]

function App() {
  const [currentMode, setCurrentMode] = useState('student')
  const [activeTab, setActiveTab] = useState('chat')
  const [userId] = useState('default') // In production, get from auth

  return (
    <div className="app">
      <header className="app-header">
        <h1>Supermemory Assistant</h1>
        <ModeSelector
          modes={MODES}
          currentMode={currentMode}
          onModeChange={setCurrentMode}
        />
      </header>

      <nav className="app-nav">
        <button
          className={activeTab === 'chat' ? 'active' : ''}
          onClick={() => setActiveTab('chat')}
        >
          💬 Chat
        </button>
        <button
          className={activeTab === 'memories' ? 'active' : ''}
          onClick={() => setActiveTab('memories')}
        >
          🧠 Memories
        </button>
        <button
          className={activeTab === 'graph' ? 'active' : ''}
          onClick={() => setActiveTab('graph')}
        >
          📊 Memory Graph
        </button>
      </nav>

      <main className="app-main">
        {activeTab === 'chat' && (
          <Chat mode={currentMode} userId={userId} />
        )}
        {activeTab === 'memories' && (
          <Memories mode={currentMode} userId={userId} />
        )}
        {activeTab === 'graph' && (
          <MemoryGraph mode={currentMode} userId={userId} />
        )}
      </main>
    </div>
  )
}

export default App

