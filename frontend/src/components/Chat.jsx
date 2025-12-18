import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import './Chat.css'

function Chat({ mode, userId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [useSearch, setUseSearch] = useState(false)
  const [pendingMessages, setPendingMessages] = useState([])
  const [proactiveMessage, setProactiveMessage] = useState(null)
  const messagesEndRef = useRef(null)
  const timeoutRef = useRef(null)

  useEffect(() => {
    // Load proactive message on mount
    loadProactiveMessage()
  }, [mode, userId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const loadProactiveMessage = async () => {
    try {
      const response = await axios.get('/api/proactive', {
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
    setPendingMessages(prev => [...prev, text])
    
    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    
    // Set new timeout to send after 1.5 seconds of inactivity
    timeoutRef.current = setTimeout(() => {
      sendPendingMessages()
    }, 1500)
  }

  const sendPendingMessages = async () => {
    if (pendingMessages.length === 0) return
    
    const messagesToSend = [...pendingMessages]
    setPendingMessages([])
    await sendMessage(messagesToSend)
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
      const response = await axios.post('/api/chat', {
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

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim()) return
    
    queueMessage(input.trim())
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>Chat - {mode.charAt(0).toUpperCase() + mode.slice(1)} Mode</h2>
        <label className="search-toggle">
          <input
            type="checkbox"
            checked={useSearch}
            onChange={(e) => setUseSearch(e.target.checked)}
          />
          <span>Use Web Search</span>
        </label>
      </div>

      <div className="chat-messages">
        {proactiveMessage && (
          <div className="message proactive">
            <div className="message-content">
              <span className="proactive-label">⚡ Proactive</span>
              <p>{proactiveMessage}</p>
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            <div className="message-content">
              <p>{message.content}</p>
              {message.toolsUsed && message.toolsUsed.length > 0 && (
                <div className="tools-used">
                  <span className="tools-label">🔧 Tools:</span>
                  {message.toolsUsed.map((tool, i) => (
                    <span key={i} className="tool-badge">
                      {tool.name.replace('.', ' ')}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <span className="message-time">
              {message.timestamp.toLocaleTimeString()}
            </span>
          </div>
        ))}

        {isLoading && (
          <div className="message assistant">
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
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

