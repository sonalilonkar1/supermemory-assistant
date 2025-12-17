import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './Memories.css'

function Memories({ mode, userId }) {
  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null)
  const [editText, setEditText] = useState('')

  useEffect(() => {
    loadMemories()
  }, [mode, userId])

  const loadMemories = async () => {
    try {
      setLoading(true)
      const response = await axios.get('/api/memories', {
        params: { mode, userId }
      })
      setMemories(response.data.memories || [])
    } catch (error) {
      console.error('Error loading memories:', error)
      setMemories([])
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (memoryId) => {
    if (!window.confirm('Are you sure you want to delete this memory?')) {
      return
    }

    try {
      await axios.delete(`/api/memories/${memoryId}`)
      setMemories(memories.filter(m => m.id !== memoryId))
    } catch (error) {
      console.error('Error deleting memory:', error)
      alert('Failed to delete memory')
    }
  }

  const handleEdit = (memory) => {
    setEditingId(memory.id)
    setEditText(memory.text || '')
  }

  const handleSaveEdit = async (memoryId) => {
    try {
      await axios.put(`/api/memories/${memoryId}`, {
        text: editText
      })
      setMemories(memories.map(m => 
        m.id === memoryId ? { ...m, text: editText } : m
      ))
      setEditingId(null)
      setEditText('')
    } catch (error) {
      console.error('Error updating memory:', error)
      alert('Failed to update memory')
    }
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditText('')
  }

  if (loading) {
    return (
      <div className="memories-container">
        <div className="loading">Loading memories...</div>
      </div>
    )
  }

  return (
    <div className="memories-container">
      <div className="memories-header">
        <h2>Memories - {mode.charAt(0).toUpperCase() + mode.slice(1)} Mode</h2>
        <button onClick={loadMemories} className="refresh-btn">
          🔄 Refresh
        </button>
      </div>

      {memories.length === 0 ? (
        <div className="empty-state">
          <p>No memories found for this mode.</p>
          <p className="empty-hint">Start chatting to create memories!</p>
        </div>
      ) : (
        <div className="memories-list">
          {memories.map(memory => (
            <div key={memory.id} className="memory-card">
              {editingId === memory.id ? (
                <div className="memory-edit">
                  <textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    className="edit-textarea"
                    rows="4"
                  />
                  <div className="edit-actions">
                    <button
                      onClick={() => handleSaveEdit(memory.id)}
                      className="save-btn"
                    >
                      Save
                    </button>
                    <button
                      onClick={handleCancelEdit}
                      className="cancel-btn"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="memory-content">
                    <p>{memory.text}</p>
                    {memory.metadata && (
                      <div className="memory-metadata">
                        {memory.metadata.mode && (
                          <span className="metadata-tag">{memory.metadata.mode}</span>
                        )}
                        {memory.metadata.createdAt && (
                          <span className="metadata-date">
                            {new Date(memory.metadata.createdAt).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="memory-actions">
                    <button
                      onClick={() => handleEdit(memory)}
                      className="edit-btn"
                    >
                      ✏️ Edit
                    </button>
                    <button
                      onClick={() => handleDelete(memory.id)}
                      className="delete-btn"
                    >
                      🗑️ Delete
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Memories

