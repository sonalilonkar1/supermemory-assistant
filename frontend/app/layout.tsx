import type { Metadata } from 'next'
import '../styles/globals.css'
// Required for @supermemory/memory-graph (it relies on its generated CSS classes for layout)
import '@supermemory/memory-graph/styles.css'

export const metadata: Metadata = {
  title: 'Supermemory Assistant',
  description: 'A personal assistant with long-term memory powered by Supermemory',
  icons: {
    icon: [
      { url: '/favicon.svg', type: 'image/svg+xml' },
      { url: '/favicon.ico', sizes: 'any' },
    ],
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}

