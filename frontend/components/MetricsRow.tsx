import { Snapshot } from '@/lib/types'
import { fmt } from '@/lib/utils'

interface Props {
  snap: Snapshot
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex-1 min-w-0">
      <div className="text-xs text-gray-500 uppercase tracking-wider">{label}</div>
      <div className="text-lg font-mono font-bold mt-0.5">{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
    </div>
  )
}

export default function MetricsRow({ snap }: Props) {
  const vvixColor =
    snap.vvix_ratio != null && snap.vvix_ratio > 1.2
      ? 'text-red-400'
      : snap.vvix_ratio != null && snap.vvix_ratio < 0.9
      ? 'text-green-400'
      : ''

  return (
    <div className="flex flex-wrap gap-3 mx-6 mt-3">
      <Metric
        label="VIX"
        value={snap.vix != null ? fmt(snap.vix, 1) : '—'}
        sub={snap.vix != null && snap.vix > 25 ? 'elevated' : 'calm'}
      />
      <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex-1 min-w-0">
        <div className="text-xs text-gray-500 uppercase tracking-wider">VVIX/VIX</div>
        <div className={`text-lg font-mono font-bold mt-0.5 ${vvixColor}`}>
          {snap.vvix_ratio != null ? `${fmt(snap.vvix_ratio, 2)}x` : '—'}
        </div>
        <div className="text-xs text-gray-500 mt-0.5">
          {snap.vvix_ratio != null && snap.vvix_ratio > 1.2 ? 'fear spike' : 'stable'}
        </div>
      </div>
      <Metric
        label="OI PCR"
        value={snap.oi_pcr != null ? fmt(snap.oi_pcr, 2) : '—'}
        sub={snap.oi_pcr_signal}
      />
      <Metric
        label="Vol PCR"
        value={snap.vol_pcr != null ? fmt(snap.vol_pcr, 2) : '—'}
        sub={snap.vol_pcr_signal}
      />
      <Metric
        label="Options"
        value={snap.options_count != null ? snap.options_count.toLocaleString() : '—'}
        sub="contracts"
      />
    </div>
  )
}
