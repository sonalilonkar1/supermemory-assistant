'use client'

import React, { useState, useEffect } from 'react'
import api from '@/lib/axios'
import styles from '@/styles/MemoryGraph.module.css'

function MemoryGraph({ mode, userId }) {
  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadMemories()
  }, [mode, userId])

  const loadMemories = async () => {
    try {
      setLoading(true)
      const response = await api.get('/memories', {
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

  // Transform memories into graph nodes
  const getGraphData = () => {
    const nodes = memories.map((memory, index) => ({
      id: memory.id || `memory-${index}`,
      label: memory.text?.substring(0, 50) + (memory.text?.length > 50 ? '...' : '') || 'Memory',
      group: memory.metadata?.mode || mode,
      timestamp: memory.metadata?.createdAt || new Date().toISOString()
    }))

    // Create relationships based on mode and time proximity
    const links = []
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        if (nodes[i].group === nodes[j].group) {
          const timeDiff = Math.abs(
            new Date(nodes[i].timestamp) - new Date(nodes[j].timestamp)
          )
          // Link memories within 7 days
          if (timeDiff < 7 * 24 * 60 * 60 * 1000) {
            links.push({
              source: nodes[i].id,
              target: nodes[j].id,
              value: 1
            })
          }
        }
      }
    }

    return { nodes, links }
  }

  if (loading) {
    return (
      <div className={styles['memory-graph-container']}>
        <div className={styles.loading}>Loading memory graph...</div>
      </div>
    )
  }

  const graphData = getGraphData()

  // Simple visualization using CSS (for a more advanced version, integrate @supermemory/memory-graph)
  return (
    <div className={styles['memory-graph-container']}>
      <div className={styles['graph-header']}>
        <h2>Memory Graph - {mode.charAt(0).toUpperCase() + mode.slice(1)} Mode</h2>
        <button onClick={loadMemories} className={styles['refresh-btn']}>
          🔄 Refresh
        </button>
      </div>

      {graphData.nodes.length === 0 ? (
        <div className={styles['empty-state']}>
          <p>No memories to visualize.</p>
          <p className={styles['empty-hint']}>Start chatting to create memories!</p>
        </div>
      ) : (
        <div className={styles['graph-content']}>
          <div className={styles['graph-stats']}>
            <div className={styles.stat}>
              <span className={styles['stat-value']}>{graphData.nodes.length}</span>
              <span className={styles['stat-label']}>Memories</span>
            </div>
            <div className={styles.stat}>
              <span className={styles['stat-value']}>{graphData.links.length}</span>
              <span className={styles['stat-label']}>Connections</span>
            </div>
          </div>

          <div className={styles['graph-visualization']}>
            <div className={styles['graph-nodes']}>
              {graphData.nodes.map((node, index) => (
                <div
                  key={node.id}
                  className={styles['graph-node']}
                  style={{
                    '--delay': `${index * 0.1}s`
                  }}
                >
                  <div className={styles['node-content']}>
                    <div className={styles['node-label']}>{node.label}</div>
                    <div className={styles['node-group']}>{node.group}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className={styles['graph-legend']}>
              <div className={styles['legend-item']}>
                <div className={`${styles['legend-color']} ${styles.student}`}></div>
                <span>Student</span>
              </div>
              <div className={styles['legend-item']}>
                <div className={`${styles['legend-color']} ${styles.parent}`}></div>
                <span>Parent</span>
              </div>
              <div className={styles['legend-item']}>
                <div className={`${styles['legend-color']} ${styles.job}`}></div>
                <span>Job</span>
              </div>
            </div>
          </div>

          <div className={styles['graph-note']}>
            <p>
              💡 <strong>Note:</strong> This is a simplified visualization. 
              For a more advanced graph with interactive features, integrate the{' '}
              <code>@supermemory/memory-graph</code> package.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default MemoryGraph

