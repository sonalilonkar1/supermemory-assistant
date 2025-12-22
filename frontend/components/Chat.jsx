'use client'

import React, { useState, useEffect, useRef } from 'react'
import api from '@/lib/axios'
import styles from '@/styles/Chat.module.css'

function Chat({ mode, modeLabel, userId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [useSearch, setUseSearch] = useState(false)
  const [showDebugTools, setShowDebugTools] = useState(false)
  const [showProactive, setShowProactive] = useState(false)
  const [pendingMessages, setPendingMessages] = useState([])
  const [proactiveMessage, setProactiveMessage] = useState(null)
  const messagesEndRef = useRef(null)
  const timeoutRef = useRef(null)
  const pendingMessagesRef = useRef([])

  useEffect(() => {
    // Load per-mode chat history from localStorage (strict mode separation in UI)
    loadLocalChatHistory()
  }, [mode, userId])

  useEffect(() => {
    // Proactive is optional and hidden by default (user-facing UX)
    if (!showProactive) {
      setProactiveMessage(null)
      return
    }
    loadProactiveMessage()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showProactive, mode, userId])

  useEffect(() => {
    // Persist per-mode chat history so switching modes doesn't mix messages
    saveLocalChatHistory()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, mode, userId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // Lightweight markdown rendering (no extra deps):
  // - escapes HTML
  // - supports **bold**, *italic*, `inline code`
  // - supports simple bullet lists starting with "- " or "* "
  const renderMarkdownLite = (text) => {
    const raw = String(text ?? '')
    const escaped = raw
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')

    const renderInline = (s) => {
      let html = s
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
      html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      // Only treat *italic* when it's not a list marker (no space right after the opening asterisk)
      html = html.replace(/\*(?!\s)([^*]+)\*/g, '<em>$1</em>')
      return html
    }

    const lines = escaped.split('\n')
    let out = ''
    let inList = false
    let inOl = false

    const closeList = () => {
      if (inList) {
        out += '</ul>'
        inList = false
      }
      if (inOl) {
        out += '</ol>'
        inOl = false
      }
    }

    for (const line of lines) {
      // Headings: ###, ##, #
      const h = line.match(/^\s*(#{1,3})\s+(.*)$/)
      if (h) {
        closeList()
        const level = h[1].length
        const content = renderInline(h[2].trim())
        const size = level === 1 ? '1.15rem' : level === 2 ? '1.05rem' : '1rem'
        out += `<div style="font-weight:800;margin:0.4rem 0 0.25rem;font-size:${size};">${content}</div>`
        continue
      }

      // Numbered list: "1. item"
      const n = line.match(/^\s*(\d+)\.\s+(.*)$/)
      if (n) {
        if (!inOl) {
          closeList()
          out += '<ol style="margin: 0.25rem 0 0.25rem 1.25rem; padding: 0;">'
          inOl = true
        }
        out += `<li style="margin: 0.15rem 0;">${renderInline(n[2])}</li>`
        continue
      }

      const m = line.match(/^\s*([-*])\s+(.*)$/)
      if (m) {
        if (!inList) {
          closeList()
          out += '<ul style="margin: 0.25rem 0 0.25rem 1.25rem; padding: 0;">'
          inList = true
        }
        out += `<li style="margin: 0.15rem 0;">${renderInline(m[2])}</li>`
      } else {
        closeList()
        const trimmed = line.trimEnd()
        // Paragraphs: wrap non-empty lines, keep blank lines as spacing
        out += trimmed ? `<div style="margin:0.15rem 0;">${renderInline(trimmed)}</div>` : '<div style="height:0.4rem;"></div>'
      }
    }
    closeList()
    return out
  }

  const storageKey = () => `sm-chat:${userId || 'default'}:${mode}`

  const serializeMessages = (msgs) => {
    return (msgs || []).map(m => ({
      ...m,
      timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : m.timestamp
    }))
  }

  const deserializeMessages = (msgs) => {
    return (msgs || []).map(m => ({
      ...m,
      timestamp: m.timestamp ? new Date(m.timestamp) : new Date()
    }))
  }

  const loadLocalChatHistory = () => {
    try {
      const raw = localStorage.getItem(storageKey())
      if (!raw) {
        setMessages([])
        return
      }
      const parsed = JSON.parse(raw)
      setMessages(deserializeMessages(parsed))
    } catch (e) {
      console.error('Error loading local chat history:', e)
      setMessages([])
    }
  }

  const saveLocalChatHistory = () => {
    try {
      localStorage.setItem(storageKey(), JSON.stringify(serializeMessages(messages)))
    } catch (e) {
      // Ignore quota errors
    }
  }

  const loadProactiveMessage = async () => {
    try {
      const response = await api.get('/proactive', {
        params: { mode, userId }
      })
      if (response.data.message) {
        setProactiveMessage(response.data.message)
      }
    } catch (error) {
      console.error('Error loading proactive message:', error)
    }
  }

  const queueMessage = (text) => {
    // Add to queue (both state and ref)
    pendingMessagesRef.current = [...pendingMessagesRef.current, text]
    setPendingMessages(pendingMessagesRef.current)
    
    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    
    // Set new timeout to send after 1.5 seconds of inactivity
    timeoutRef.current = setTimeout(() => {
      sendPendingMessages()
    }, 1500)
  }

  const sendPendingMessages = async () => {
    // Get current pending messages from ref (always up to date)
    const messagesToSend = [...pendingMessagesRef.current]
    if (messagesToSend.length === 0) return
    
    // Clear both ref and state
    pendingMessagesRef.current = []
    setPendingMessages([])
    
    // Send messages
    sendMessage(messagesToSend)
  }

  const sendMessage = async (messageArray) => {
    const userMessages = Array.isArray(messageArray) ? messageArray : [messageArray]
    
    // Add user messages to chat
    const userMessageObjects = userMessages.map(msg => ({
      role: 'user',
      content: msg,
      timestamp: new Date()
    }))
    setMessages(prev => [...prev, ...userMessageObjects])
    setInput('')
    setIsLoading(true)

    try {
      const response = await api.post('/chat', {
        userId,
        mode,
        messages: userMessages,
        useSearch
      })

      // Add assistant replies as separate messages
      const assistantMessages = response.data.replies.map((reply, index) => ({
        role: 'assistant',
        content: reply,
        toolsUsed: index === 0 ? response.data.toolsUsed : [],
        timestamp: new Date()
      }))

      setMessages(prev => [...prev, ...assistantMessages])
      
      // Clear proactive message after first interaction
      if (proactiveMessage) {
        setProactiveMessage(null)
      }
    } catch (error) {
      console.error('Error sending message:', error)
      let errorMessage = 'Sorry, I encountered an error. Please try again.'
      
      // Provide more specific error messages
      if (error.response?.status === 500) {
        const errorData = error.response?.data
        if (errorData?.error) {
          errorMessage = errorData.error
          if (errorData.details) {
            errorMessage += `\n\n${errorData.details}`
          }
        } else if (errorData?.message) {
          errorMessage = errorData.message
        }
      } else if (error.response?.status === 429) {
        errorMessage = 'Rate limit exceeded. Please wait a moment and try again.'
      } else if (error.message) {
        errorMessage = `Error: ${error.message}`
      }
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: errorMessage,
        timestamp: new Date()
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    
    const messageText = input.trim()
    setInput('') // Clear input immediately
    
    // Clear any pending timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    
    // Get any pending messages from ref and combine with current message
    const allMessages = [...pendingMessagesRef.current, messageText]
    
    // Clear pending messages (both ref and state)
    pendingMessagesRef.current = []
    setPendingMessages([])
    
    // Send all messages immediately
    sendMessage(allMessages)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (input.trim() && !isLoading) {
        handleSubmit(e) // Use the same logic as form submit
      }
    }
  }

  return (
    <div className={styles['chat-container']}>
      <div className={styles['chat-header']}>
        <h2>Chat - {(modeLabel || mode).toString()} Mode</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <label className={styles['search-toggle']}>
            <input
              type="checkbox"
              checked={useSearch}
              onChange={(e) => setUseSearch(e.target.checked)}
            />
            <span>Use Web Search</span>
          </label>

          <label className={styles['search-toggle']} style={{ opacity: 0.85 }}>
            <input
              type="checkbox"
              checked={showProactive}
              onChange={(e) => setShowProactive(e.target.checked)}
            />
            <span>Show Proactive</span>
          </label>

          <label className={styles['search-toggle']} style={{ opacity: 0.85 }}>
            <input
              type="checkbox"
              checked={showDebugTools}
              onChange={(e) => setShowDebugTools(e.target.checked)}
            />
            <span>Show Debug Tools</span>
          </label>
        </div>
      </div>

      <div className={styles['chat-messages']}>
        {proactiveMessage && (
          <div className={`${styles.message} ${styles.proactive}`}>
            <div className={styles['message-content']}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem' }}>
                <span className={styles['proactive-label']}>Proactive</span>
                <button
                  type="button"
                  onClick={() => setProactiveMessage(null)}
                  style={{
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    color: '#856404',
                    fontWeight: 800,
                    fontSize: '1rem',
                    lineHeight: 1,
                  }}
                  aria-label="Dismiss proactive suggestion"
                  title="Dismiss"
                >
                  ×
                </button>
              </div>
              <div
                style={{ marginTop: '0.25rem' }}
                dangerouslySetInnerHTML={{ __html: renderMarkdownLite(proactiveMessage) }}
              />
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`${styles.message} ${styles[message.role]}`}>
            <div className={styles['message-content']}>
              <div
                style={{ whiteSpace: 'normal' }}
                dangerouslySetInnerHTML={{ __html: renderMarkdownLite(message.content) }}
              />
              {showDebugTools && message.toolsUsed && message.toolsUsed.length > 0 && (
                <div className={styles['tools-used']}>
                  <span className={styles['tools-label']}>🔧 Tools:</span>
                  {message.toolsUsed.map((tool, i) => (
                    <span key={i} className={styles['tool-badge']}>
                      {tool.name.replace('.', ' ')}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <span className={styles['message-time']}>
              {message.timestamp.toLocaleTimeString()}
            </span>
          </div>
        ))}

        {isLoading && (
          <div className={`${styles.message} ${styles.assistant}`}>
            <div className={styles['message-content']}>
              <div className={styles['typing-indicator']}>
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className={styles['chat-input-form']} onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message..."
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}

export default Chat

