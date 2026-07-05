import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ExportGuard — Real-Time Export Risk Intelligence',
  description:
    'Decide in real-time whether a new export deal is safe to take and on what payment terms.',
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
