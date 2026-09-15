'use client'

import { Snapshot } from '@/lib/types'
import { timeAgo } from '@/lib/utils'

interface Props {
  activeSymbol: string
  symbols: string[]
  snapshot: Snapshot | null
  loading: boolean
  onSymbolChange: (s: string) => void
}

export default function Header({ activeSymbol, symbols, snapshot, loading, onSymbolChange }: Props) {
  const age = snapshot ? timeAgo(snapshot.written_at) : null

  return (
    <header className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-900">
      <div className="flex items-center gap-4">
        <span className="text-sm font-bold tracking-widest text-gray-400 uppercase">
          Market Monitor
        </span>
        <div className="flex gap-1">
          {symbols.map((sym) => (
            <button
              key={sym}
              onClick={() => onSymbolChange(sym)}
              className={`px-3 py-1 rounded text-sm font-semibold transition-colors ${
                activeSymbol === sym
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {sym}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-4 text-sm">
        {age && (
          <span className={age.stale ? 'text-yellow-400' : 'text-gray-500'}>
            {age.stale ? '⚠ ' : ''}updated {age.text}
          </span>
        )}
        <span className={`flex items-center gap-1 ${loading ? 'text-gray-500' : age?.stale ? 'text-yellow-400' : 'text-green-400'}`}>
          <span className={`w-2 h-2 rounded-full ${loading ? 'bg-gray-500' : age?.stale ? 'bg-yellow-400' : 'bg-green-400 animate-pulse'}`} />
          {age?.stale ? 'STALE' : 'LIVE'}
        </span>
      </div>
    </header>
  )
}
