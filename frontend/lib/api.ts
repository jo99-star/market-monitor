import { Snapshot } from './types'

const API_URL = process.env.NEXT_PUBLIC_API_URL
if (!API_URL && typeof window !== 'undefined') {
  console.error('NEXT_PUBLIC_API_URL is not set')
}

export async function fetchSnapshot(symbol: string): Promise<Snapshot | null> {
  if (!API_URL) return null
  try {
    const res = await fetch(`${API_URL}/api/snapshot?symbol=${encodeURIComponent(symbol)}`)
    if (!res.ok) return null
    return res.json() as Promise<Snapshot>
  } catch {
    return null
  }
}
