export function fmt(n: number | undefined | null, decimals = 2): string {
  if (n == null || isNaN(n)) return '—'
  return n.toFixed(decimals)
}

export function fmtM(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '—'
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(0)}M`
  return `${sign}${(abs / 1e3).toFixed(0)}K`
}

export function fmtPremium(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '—'
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`
  return `$${n.toFixed(0)}`
}

export function timeAgo(iso: string): { text: string; stale: boolean } {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  const stale = diff > 65
  if (diff < 60) return { text: `${Math.floor(diff)}s ago`, stale }
  if (diff < 3600) return { text: `${Math.floor(diff / 60)}m ago`, stale }
  return { text: `${Math.floor(diff / 3600)}h ago`, stale }
}

export function biasColor(bias: string): string {
  if (bias === 'bullish') return 'text-green-400'
  if (bias === 'bearish') return 'text-red-400'
  return 'text-gray-400'
}

export function signalLabel(signal: string): string {
  if (signal === 'mean_revert') return 'Mean Revert ↔'
  if (signal === 'trend_amplify') return 'Trend Amplify →'
  return 'Neutral'
}

export function signalColor(signal: string): string {
  if (signal === 'mean_revert') return 'text-blue-400'
  if (signal === 'trend_amplify') return 'text-yellow-400'
  return 'text-gray-400'
}

export function pcrColor(signal: string): string {
  if (signal === 'bullish') return 'text-green-400'
  if (signal === 'bearish') return 'text-red-400'
  return 'text-gray-400'
}

export function confidenceBadge(c?: string): string {
  if (c === 'high') return 'bg-green-900 text-green-300'
  if (c === 'low') return 'bg-gray-800 text-gray-400'
  return 'bg-yellow-900 text-yellow-300'
}
