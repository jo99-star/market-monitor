'use client'

import { GexLevel } from '@/lib/types'
import { fmt } from '@/lib/utils'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

interface Props {
  levels: GexLevel[]
  spot: number
}

function formatGex(v: number) {
  const abs = Math.abs(v)
  if (abs >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${(v / 1e6).toFixed(0)}M`
  return `${(v / 1e3).toFixed(0)}K`
}

export default function GexChart({ levels, spot }: Props) {
  // Show 30 strikes centered around spot price
  const sorted = [...levels].sort((a, b) => a.price - b.price)
  const spotIdx = sorted.findIndex((l) => l.price >= spot)
  const start = Math.max(0, spotIdx - 15)
  const data = sorted.slice(start, start + 30)

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-600 text-sm">
        No GEX data
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis
          dataKey="price"
          tick={{ fill: '#6b7280', fontSize: 10 }}
          tickFormatter={(v) => fmt(v, 0)}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: '#6b7280', fontSize: 10 }}
          tickFormatter={formatGex}
          width={44}
        />
        <Tooltip
          contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', fontSize: 12 }}
          formatter={(v: number) => [formatGex(v), 'GEX']}
          labelFormatter={(l) => `Strike $${l}`}
        />
        <ReferenceLine x={spot} stroke="#fbbf24" strokeDasharray="4 2" label={{ value: 'spot', fill: '#fbbf24', fontSize: 10 }} />
        <Bar dataKey="gex">
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.gex >= 0 ? '#4ade80' : '#f87171'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
