import { Snapshot } from '@/lib/types'
import { fmt } from '@/lib/utils'

interface Props {
  snap: Snapshot
}

function signalCN(signal: string | undefined): string {
  if (signal === 'bullish') return '看多 ↑'
  if (signal === 'bearish') return '看空 ↓'
  return '中性'
}

function signalTextColor(signal: string | undefined): string {
  if (signal === 'bullish') return 'text-green-400'
  if (signal === 'bearish') return 'text-red-400'
  return 'text-gray-500'
}

function Metric({ label, value, sub, subColor }: { label: string; value: string; sub?: string; subColor?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex-1 min-w-0">
      <div className="text-xs text-gray-500 uppercase tracking-wider">{label}</div>
      <div className="text-lg font-mono font-bold mt-0.5">{value}</div>
      {sub && <div className={`text-xs mt-0.5 ${subColor ?? 'text-gray-500'}`}>{sub}</div>}
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

  const vixSub = snap.vix != null
    ? snap.vix > 30 ? '恐慌 ↑' : snap.vix > 20 ? '偏高' : '正常 ↓'
    : undefined
  const vixSubColor = snap.vix != null
    ? snap.vix > 30 ? 'text-red-400' : snap.vix > 20 ? 'text-yellow-400' : 'text-green-400'
    : undefined

  return (
    <div className="flex flex-wrap gap-3 mx-6 mt-3">
      <Metric
        label="VIX(恐慌指數)"
        value={snap.vix != null ? fmt(snap.vix, 1) : '—'}
        sub={vixSub}
        subColor={vixSubColor}
      />
      <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex-1 min-w-0">
        <div className="text-xs text-gray-500 uppercase tracking-wider">VVIX/VIX(波動率比)</div>
        <div className={`text-lg font-mono font-bold mt-0.5 ${vvixColor}`}>
          {snap.vvix_ratio != null ? `${fmt(snap.vvix_ratio, 2)}x` : '—'}
        </div>
        {snap.vvix_ratio != null && (
          <div className={`text-xs mt-0.5 ${snap.vvix_ratio > 1.2 ? 'text-red-400' : 'text-gray-500'}`}>
            {snap.vvix_ratio > 1.2 ? '恐慌升溫 ↑' : '穩定'}
          </div>
        )}
      </div>
      <Metric
        label="OI PCR(持倉量比)"
        value={snap.oi_pcr != null ? fmt(snap.oi_pcr, 2) : '—'}
        sub={signalCN(snap.oi_pcr_signal)}
        subColor={signalTextColor(snap.oi_pcr_signal)}
      />
      <Metric
        label="Vol PCR(量能比)"
        value={snap.vol_pcr != null ? fmt(snap.vol_pcr, 2) : '—'}
        sub={signalCN(snap.vol_pcr_signal)}
        subColor={signalTextColor(snap.vol_pcr_signal)}
      />
      <Metric
        label="期權合約數"
        value={snap.options_count != null ? snap.options_count.toLocaleString() : '—'}
        sub="contracts"
      />
    </div>
  )
}
