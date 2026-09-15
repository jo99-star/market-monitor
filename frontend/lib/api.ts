import { Snapshot } from './types'

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  'https://market-monitor-production-dbf8.up.railway.app'

export async function fetchSnapshot(symbol: string): Promise<Snapshot | null> {
  try {
    const res = await fetch(`${API_URL}/api/snapshot?symbol=${symbol}`)
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}
