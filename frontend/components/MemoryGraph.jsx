'use client'

import React, { useState, useEffect, Suspense, useRef } from 'react'
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


// Lightweight custom SVG view (no hexagons) for visual refresh
function CustomGraph({ graphData, onSelect }) {
  const containerRef = useRef(null)
  const [size, setSize] = useState({ width: 900, height: 520 })

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setSize({
          width: containerRef.current.clientWidth,
          height: Math.max(containerRef.current.clientHeight, 420),
        })
      }
    }
    updateSize()
    window.addEventListener('resize', updateSize)
    return () => window.removeEventListener('resize', updateSize)
  }, [])

  const { width, height } = size
  const nodes = graphData?.nodes || []
  const edges = graphData?.edges || graphData?.links || []

  const radius = Math.max(Math.min(width, height) / 2 - 80, 120)
  const cx = width / 2
  const cy = height / 2

  const laidOutNodes = nodes.map((n, idx) => {
    const angle = (idx / Math.max(nodes.length, 1)) * Math.PI * 2
    return {
      ...n,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    }
  })

  const nodeMap = new Map(laidOutNodes.map(n => [n.id, n]))

  const renderNodeShape = (node) => {
    const type = node.type || node.group || 'memory'
    const common = {
      key: node.id,
      stroke: '#0f172a',
      strokeWidth: 2,
      style: { filter: 'drop-shadow(0 2px 6px rgba(0,0,0,0.25))', cursor: 'pointer' },
      onClick: () => onSelect && onSelect(node),
    }
    if (type === 'document') {
      return (
        <rect
          {...common}
          x={node.x - 10}
          y={node.y - 10}
          width={20}
          height={20}
          rx={4}
          fill="#10b981"
        />
      )
    }
    if (type === 'user') {
      return (
        <polygon
          {...common}
          points={`${node.x},${node.y - 12} ${node.x + 12},${node.y} ${node.x},${node.y + 12} ${node.x - 12},${node.y}`}
          fill="#f59e0b"
        />
      )
    }
    return (
      <circle
        {...common}
        cx={node.x}
        cy={node.y}
        r={9}
        fill="#6366f1"
      />
    )
  }

  return (
    <div ref={containerRef} className={styles.customGraphContainer}>
      <svg width={width} height={height} className={styles.customGraphSvg}>
        {edges.map((e, idx) => {
          const s = nodeMap.get(e.source)
          const t = nodeMap.get(e.target)
          if (!s || !t) return null
          return (
            <line
              key={`edge-${idx}`}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke="#94a3b8"
              strokeWidth={2}
              strokeLinecap="round"
              opacity={0.6}
            />
          )
        })}
        {laidOutNodes.map(renderNodeShape)}
        {laidOutNodes.map((n, idx) => (
          <text
            key={`label-${idx}`}
            x={n.x}
            y={n.y - 16}
            textAnchor="middle"
            fill="#e2e8f0"
            fontSize="11"
            fontWeight="600"
          >
            {(n.label || '').slice(0, 18)}
          </text>
        ))}
      </svg>
    </div>
  )
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
  const [useCustomView, setUseCustomView] = useState(true)
  const [selectedNode, setSelectedNode] = useState(null)
  const [combinedView, setCombinedView] = useState(false) // Toggle for combined/separate view

  useEffect(() => {
    loadGraphData()
  }, [mode, userId, combinedView])

  const loadGraphData = async () => {
    try {
      setLoading(true)
      // Use the memory-graph endpoint which provides nodes and edges
      // If combinedView is true, don't pass role (or pass null) to get all modes
      const params = { userId }
      if (!combinedView) {
        params.role = mode
      }
      const response = await api.get('/memory-graph', { params })
      
      if (response.data.nodes && response.data.edges) {
        setGraphData({
          nodes: response.data.nodes,
          edges: response.data.edges
        })
      } else {
        // Fallback to simple memories endpoint
        const memoriesParams = { userId }
        if (!combinedView) {
          memoriesParams.mode = mode
        }
        const memoriesResponse = await api.get('/memories', { params: memoriesParams })
        const fetched = memoriesResponse.data.memories || []
        const strict = combinedView ? fetched : fetched.filter(m => (m.metadata?.mode || null) === mode)
        setMemories(strict)
      }
    } catch (error) {
      console.error('Error loading memory graph:', error)
      // Fallback to simple memories
      try {
        const memoriesParams = { userId }
        if (!combinedView) {
          memoriesParams.mode = mode
        }
        const memoriesResponse = await api.get('/memories', { params: memoriesParams })
        const fetched = memoriesResponse.data.memories || []
        const strict = combinedView ? fetched : fetched.filter(m => (m.metadata?.mode || null) === mode)
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
    // In combined view, link memories across modes; in separate view, only within same mode
    const links = []
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const sameMode = nodes[i].group === nodes[j].group
        if (combinedView || sameMode) {
          const timeDiff = Math.abs(
            new Date(nodes[i].timestamp) - new Date(nodes[j].timestamp)
          )
          // Link memories within 7 days (across modes in combined view, same mode in separate view)
          if (timeDiff < 7 * 24 * 60 * 60 * 1000) {
            links.push({
              source: nodes[i].id,
              target: nodes[j].id,
              value: sameMode ? 2 : 1, // Stronger links within same mode
              type: sameMode ? 'same-mode' : 'cross-mode'
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

  const handleGraphToggle = () => {
    if (!useAdvancedGraph) {
      setUseAdvancedGraph(true)
      return
    }
    setUseCustomView(!useCustomView)
  }

  const handleSimpleView = () => {
    setUseAdvancedGraph(false)
    setSelectedNode(null)
  }

  const handleRefresh = () => {
    loadGraphData()
  }

  const handleNodeSelect = (node) => {
    setSelectedNode(node)
  }

  return (
    <div className={styles['memory-graph-container']}>
      <div className={styles['graph-header']}>
        <h2>Memory Graph - {combinedView ? 'All Modes' : `${(modeLabel || mode).toString()} Mode`}</h2>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button 
            onClick={() => setCombinedView(!combinedView)}
            className={styles['toggle-btn']}
            style={{
              background: combinedView ? '#10b981' : '#e5e7eb',
              color: combinedView ? 'white' : '#111827',
              border: `1px solid ${combinedView ? '#10b981' : '#e5e7eb'}`,
              padding: '0.5rem 1rem',
              borderRadius: '8px',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.875rem'
            }}
            title={combinedView ? 'Show only current mode' : 'Show all modes'}
          >
            {combinedView ? '🔗 Combined View' : '📊 Separate View'}
          </button>
          <button 
            onClick={handleGraphToggle} 
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
            {useAdvancedGraph ? (useCustomView ? '🔄 Custom View' : '🔄 Advanced View') : '✨ Graph View'}
          </button>
          <button onClick={handleSimpleView} className={styles['refresh-btn']} style={{ background: '#e5e7eb', color: '#111827' }}>
          Simple View
        </button>
          <button 
            onClick={handleRefresh} 
            className={styles['refresh-btn']} 
            style={{ background: '#f3f4f6', color: '#111827' }}
          >
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
            useCustomView ? (
              <div className={styles['advanced-graph-container']} style={{ width: '100%', height: '70vh', minHeight: '560px', border: '1px solid #dfe3eb', borderRadius: '14px', background: "radial-gradient(circle at 20% 20%, #111827 0%, #0b1220 45%, #0a0f1a 100%)", position: 'relative', overflow: 'hidden', boxShadow: '0 10px 30px rgba(0,0,0,0.2)', padding: '0.5rem' }}>
                <CustomGraph graphData={displayData} onSelect={handleNodeSelect} />
                <div className={styles.legendRow}>
                  <span className={`${styles.legendChip}`}><span className={`${styles.legendDot} ${styles.memory}`}></span>Memory</span>
                  <span className={`${styles.legendChip}`}><span className={`${styles.legendDot} ${styles.document}`}></span>Document</span>
                  <span className={`${styles.legendChip}`}><span className={`${styles.legendDot} ${styles.user}`}></span>User</span>
                  <span className={`${styles.legendChip}`}><span className={`${styles.legendDot} ${styles.edge}`}></span>Edge</span>
                </div>
              </div>
            ) : (
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
            )
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
            </div>
          )}
        </div>
      )}

      {/* Detail Drawer for Custom View */}
      {useAdvancedGraph && useCustomView && selectedNode && (
        <div className={styles.drawerOverlay} onClick={() => setSelectedNode(null)}>
          <div className={styles.drawer} onClick={(e) => e.stopPropagation()}>
            <div className={styles.drawerHeader}>
              <h3>Memory Detail</h3>
              <button className={styles.drawerClose} onClick={() => setSelectedNode(null)}>×</button>
            </div>
            <div className={styles.drawerContent}>
              <div className={styles.detailSection}>
                <label>Label</label>
                <div className={styles.detailValue}>{selectedNode.label || 'Untitled'}</div>
              </div>
              <div className={styles.detailSection}>
                <label>Type</label>
                <div className={styles.detailValue}>{selectedNode.type || selectedNode.group || 'memory'}</div>
              </div>
              <div className={styles.detailSection}>
                <label>ID</label>
                <div className={styles.detailValue}>{selectedNode.id}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default MemoryGraph
