'use client'

import React, { useState, useEffect, Suspense } from 'react'
import api from '@/lib/axios'
import styles from '@/styles/MemoryGraph.module.css'

// Lazy load the MemoryGraph component from the package
const AdvancedMemoryGraph = React.lazy(() => 
  import('@supermemory/memory-graph').then(module => {
    // Try different export formats
    const Component = module.default || module.MemoryGraph || module
    return { default: Component }
  }).catch(err => {
    console.error('Failed to load @supermemory/memory-graph:', err)
    // Return a fallback component
    return { 
      default: () => (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
          <p>Failed to load advanced graph component.</p>
          <p style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>
            Error: {err.message}
          </p>
        </div>
      )
    }
  })
)

// Error Boundary component
class GraphErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('GraphErrorBoundary caught an error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#d32f2f' }}>
          <p><strong>Error rendering advanced graph:</strong></p>
          <p style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>
            {this.state.error?.message || 'Unknown error occurred'}
          </p>
          <p style={{ fontSize: '0.8rem', marginTop: '1rem', color: '#666' }}>
            The graph component encountered an error. Please use the simple view or check the console for details.
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              background: '#667eea',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Try Again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

// Wrapper component to handle prop validation
function AdvancedMemoryGraphWrapper({ nodes, edges, userId }) {
  // Ensure nodes and edges are arrays with proper structure
  const safeNodes = Array.isArray(nodes) ? nodes : []
  const safeEdges = Array.isArray(edges) ? edges : []
  
  // Validate node structure - ensure each node has required properties
  // Graph libraries often expect: id, label, and sometimes position/coordinates
  const validatedNodes = safeNodes.map((node, index) => ({
    id: String(node.id || `node-${index}`),
    label: String(node.label || node.name || 'Node'),
    // Add common graph library properties
    type: node.type || 'default',
    role: node.role || 'all',
    // Ensure all properties are defined (not undefined)
    ...Object.fromEntries(
      Object.entries(node).filter(([_, v]) => v !== undefined)
    )
  }))
  
  // Validate edge structure - ensure each edge has source and target
  // Graph libraries expect: id (optional), source, target
  const validatedEdges = safeEdges
    .map((edge, index) => ({
      id: String(edge.id || `edge-${index}`),
      source: String(edge.source || edge.from || edge.sourceId || ''),
      target: String(edge.target || edge.to || edge.targetId || ''),
      // Add relation if present
      relation: edge.relation || edge.type || 'connected',
      // Ensure all properties are defined
      ...Object.fromEntries(
        Object.entries(edge).filter(([_, v]) => v !== undefined)
      )
    }))
    .filter(edge => edge.source && edge.target && edge.source !== edge.target) // Remove invalid edges
  
  console.log('AdvancedMemoryGraph props:', {
    nodesCount: validatedNodes.length,
    edgesCount: validatedEdges.length,
    sampleNode: validatedNodes[0],
    sampleEdge: validatedEdges[0]
  })
  
  // Try different prop formats - the component might expect:
  // 1. nodes/edges as separate props
  // 2. data prop with nested structure
  // 3. graphData prop
  // The Error Boundary will catch any errors
  
  // First, ensure we have at least one node (some components require this)
  if (validatedNodes.length === 0) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
        <p>No nodes to display in the graph.</p>
        <p style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>
          Create some memories first to see the graph visualization.
        </p>
      </div>
    )
  }
  
  // The component is trying to read .length on something undefined
  // This suggests it expects a specific prop structure
  // Based on common graph libraries, let's try different formats
  
  // Ensure we always have valid arrays (not undefined)
  const graphData = {
    nodes: validatedNodes || [],
    edges: validatedEdges || []
  }
  
  console.log('🔍 AdvancedMemoryGraph Debug Info:', {
    nodesCount: validatedNodes.length,
    edgesCount: validatedEdges.length,
    nodesType: Array.isArray(validatedNodes) ? 'array' : typeof validatedNodes,
    edgesType: Array.isArray(validatedEdges) ? 'array' : typeof validatedEdges,
    sampleNode: validatedNodes[0],
    sampleEdge: validatedEdges[0],
    graphDataStructure: Object.keys(graphData)
  })
  
  // IMPORTANT: MemoryGraph expects 'documents' prop, not 'nodes' and 'edges'!
  // Transform our nodes/edges into DocumentWithMemories format
  // Convert nodes/edges -> documents. Prefer non-user nodes (memory/entity), but if we
  // only have the user node, include it so the advanced graph can still render.
  let documents = validatedNodes
    .filter(node => node.type !== 'user') // Prefer excluding user node
    .map((node) => {
      // Find edges connected to this node
      const connectedEdges = validatedEdges.filter(
        edge => edge.target === node.id || edge.source === node.id
      )
      
      // Create memory entries from connected edges or the node itself
      const memoryEntries = connectedEdges.length > 0
        ? connectedEdges.map((edge, edgeIndex) => ({
            id: edge.id || `memory-${node.id}-${edgeIndex}`,
            documentId: node.id,
            content: node.label || '',
            summary: node.label || '',
            title: node.label || '',
            type: node.type || null,
            metadata: {
              role: node.role || 'all',
              relation: edge.relation || 'connected',
              ...node
            },
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            spaceContainerTag: userId || null
          }))
        : [{
            id: `memory-${node.id}`,
            documentId: node.id,
            content: node.label || '',
            summary: node.label || '',
            title: node.label || '',
            type: node.type || null,
            metadata: {
              role: node.role || 'all',
              ...node
            },
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            spaceContainerTag: userId || null
          }]
      
      // Create DocumentWithMemories object
      return {
        id: node.id,
        userId: userId || 'default',
        orgId: userId || 'default',
        contentHash: null,
        title: node.label || 'Untitled',
        content: node.label || '',
        summary: node.label || '',
        type: node.type || 'default',
        status: 'done',
        metadata: {
          role: node.role || 'all',
          ...node
        },
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        memoryEntries: memoryEntries
      }
    })

  // If we have no non-user nodes, fall back to including the user node as a single document.
  if (documents.length === 0) {
    const userNode = validatedNodes.find(n => n.type === 'user')
    if (userNode) {
      documents = [{
        id: userNode.id,
        userId: userId || 'default',
        orgId: userId || 'default',
        contentHash: null,
        title: userNode.label || 'User',
        content: userNode.label || 'User',
        summary: userNode.label || 'User',
        url: null,
        source: null,
        type: 'user',
        status: 'done',
        metadata: {
          role: userNode.role || 'all',
          ...userNode
        },
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        memoryEntries: [{
          id: `memory-${userNode.id}`,
          documentId: userNode.id,
          content: userNode.label || 'User',
          summary: userNode.label || 'User',
          title: userNode.label || 'User',
          url: null,
          type: 'user',
          metadata: {
            role: userNode.role || 'all',
            ...userNode
          },
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        }]
      }]
    }
  }
  
  console.log('🔍 Transformed data for MemoryGraph:', {
    documentsCount: documents.length,
    sampleDocument: documents[0],
    totalMemoryEntries: documents.reduce((sum, doc) => sum + doc.memoryEntries.length, 0)
  })
  
  if (documents.length === 0) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
        <p>No documents to display in the graph.</p>
        <p style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>
          Create some memories first to see the graph visualization.
        </p>
      </div>
    )
  }
  
  return (
    <GraphErrorBoundary>
      <AdvancedMemoryGraph
        documents={documents}
        isLoading={false}
        variant="consumer"
      />
    </GraphErrorBoundary>
  )
}

function MemoryGraph({ mode, modeLabel, userId }) {
  const [memories, setMemories] = useState([])
  const [graphData, setGraphData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [useAdvancedGraph, setUseAdvancedGraph] = useState(false)

  useEffect(() => {
    loadGraphData()
  }, [mode, userId])

  const loadGraphData = async () => {
    try {
      setLoading(true)
      // Use the memory-graph endpoint which provides nodes and edges
      const response = await api.get('/memory-graph', {
        params: { role: mode, userId }
      })
      
      if (response.data.nodes && response.data.edges) {
        setGraphData({
          nodes: response.data.nodes,
          edges: response.data.edges
        })
      } else {
        // Fallback to simple memories endpoint
        const memoriesResponse = await api.get('/memories', {
        params: { mode, userId }
      })
        const fetched = memoriesResponse.data.memories || []
        const strict = fetched.filter(m => (m.metadata?.mode || null) === mode)
        setMemories(strict)
      }
    } catch (error) {
      console.error('Error loading memory graph:', error)
      // Fallback to simple memories
      try {
        const memoriesResponse = await api.get('/memories', {
          params: { mode, userId }
        })
        const fetched = memoriesResponse.data.memories || []
        const strict = fetched.filter(m => (m.metadata?.mode || null) === mode)
        setMemories(strict)
      } catch (err) {
        console.error('Error loading memories:', err)
      setMemories([])
      }
    } finally {
      setLoading(false)
    }
  }


  // Fallback: Transform memories into graph nodes if graphData not available
  const getSimpleGraphData = () => {
    const nodes = memories.map((memory, index) => ({
      id: memory.id || `memory-${index}`,
      label: (memory.text || memory.content || '').substring(0, 50) + ((memory.text || memory.content || '').length > 50 ? '...' : '') || 'Memory',
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

  const displayData = graphData || getSimpleGraphData()

  return (
    <div className={styles['memory-graph-container']}>
      <div className={styles['graph-header']}>
        <h2>Memory Graph - {(modeLabel || mode).toString()} Mode</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button 
            onClick={() => setUseAdvancedGraph(!useAdvancedGraph)} 
            className={styles['toggle-btn']}
            style={{
              background: useAdvancedGraph ? '#667eea' : 'transparent',
              color: useAdvancedGraph ? 'white' : '#667eea',
              border: '1px solid #667eea',
              padding: '0.5rem 1rem',
              borderRadius: '8px',
              cursor: 'pointer'
            }}
          >
            {useAdvancedGraph ? '🔄 Advanced View' : '✨ Use Advanced Graph'}
          </button>
          <button onClick={loadGraphData} className={styles['refresh-btn']}>
          🔄 Refresh
        </button>
        </div>
      </div>

      {displayData.nodes.length === 0 ? (
        <div className={styles['empty-state']}>
          <p>No memories to visualize.</p>
          <p className={styles['empty-hint']}>Start chatting to create memories!</p>
        </div>
      ) : (
        <div className={styles['graph-content']}>
          <div className={styles['graph-stats']}>
            <div className={styles.stat}>
              <span className={styles['stat-value']}>{displayData.nodes.length}</span>
              <span className={styles['stat-label']}>Nodes</span>
            </div>
            <div className={styles.stat}>
              <span className={styles['stat-value']}>{displayData.edges?.length || displayData.links?.length || 0}</span>
              <span className={styles['stat-label']}>Connections</span>
            </div>
          </div>

          {useAdvancedGraph ? (
            <div 
              className={styles['advanced-graph-container']}
              style={{
                width: '100%',
                height: '70vh',
                minHeight: '560px',
                border: '1px solid #e9ecef',
                borderRadius: '12px',
                background: '#fff',
                position: 'relative',
                overflow: 'hidden'
              }}
            >
              <Suspense fallback={
                <div className={styles.loading} style={{ padding: '2rem' }}>
                  Loading advanced graph...
                </div>
              }>
                <AdvancedMemoryGraphWrapper
                  nodes={displayData.nodes || []}
                  edges={displayData.edges || []}
                  userId={userId}
                />
              </Suspense>
            </div>
          ) : (
            <div className={styles['graph-visualization']}>
              <div className={styles['graph-nodes']}>
                {displayData.nodes.map((node, index) => (
                <div
                  key={node.id}
                    className={styles['graph-node']}
                  style={{
                    '--delay': `${index * 0.1}s`
                  }}
                >
                    <div className={styles['node-content']}>
                      <div className={styles['node-label']}>{node.label}</div>
                      <div className={styles['node-group']}>{node.type || node.group || mode}</div>
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
          )}

          {!useAdvancedGraph && (
            <div className={styles['graph-note']}>
            <p>
                💡 <strong>Tip:</strong> Click "✨ Use Advanced Graph" to enable interactive visualization with{' '}
              <code>@supermemory/memory-graph</code> package.
            </p>
          </div>
          )}
        </div>
      )}
    </div>
  )
}

export default MemoryGraph

