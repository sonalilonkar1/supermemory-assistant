'use client'

import React, { useState, useEffect, useRef } from 'react'
import api from '@/lib/axios'
import styles from '@/styles/Chat.module.css'

function Chat({ mode, userId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [useSearch, setUseSearch] = useState(false)
  const [pendingMessages, setPendingMessages] = useState([])
  const [proactiveMessage, setProactiveMessage] = useState(null)
  const messagesEndRef = useRef(null)
  const timeoutRef = useRef(null)
  const pendingMessagesRef = useRef([])

  useEffect(() => {
    // Load proactive message on mount
    loadProactiveMessage()
    // Load per-mode chat history from localStorage (strict mode separation in UI)
    loadLocalChatHistory()
  }, [mode, userId])

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
        <h2>Chat - {mode.charAt(0).toUpperCase() + mode.slice(1)} Mode</h2>
        <label className={styles['search-toggle']}>
          <input
            type="checkbox"
            checked={useSearch}
            onChange={(e) => setUseSearch(e.target.checked)}
          />
          <span>Use Web Search</span>
        </label>
      </div>

      <div className={styles['chat-messages']}>
        {proactiveMessage && (
          <div className={`${styles.message} ${styles.proactive}`}>
            <div className={styles['message-content']}>
              <span className={styles['proactive-label']}>⚡ Proactive</span>
              <p>{proactiveMessage}</p>
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`${styles.message} ${styles[message.role]}`}>
            <div className={styles['message-content']}>
              <p>{message.content}</p>
              {message.toolsUsed && message.toolsUsed.length > 0 && (
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

