import { Snapshot } from '@/lib/types'
import { biasColor, fmt, fmtM, pcrColor, signalColor, signalLabel } from '@/lib/utils'

interface Props {
  symbol: string
  snap: Snapshot
}

function Card({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">{label}</div>
      {children}
    </div>
  )
}

export default function StatGrid({ symbol, snap }: Props) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mx-6 mt-4">
      <Card label={`${symbol} Spot`}>
        <div className="text-3xl font-mono font-bold">${fmt(snap.spot)}</div>
        <div className={`text-sm mt-1 ${biasColor(snap.vpoc_bias)}`}>
          {snap.vpoc_bias} vs VPOC
        </div>
      </Card>

      <Card label="Value Area">
        <div className="space-y-1 font-mono text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">VAH</span>
            <span className="text-red-300">{fmt(snap.vah)}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-500">VPOC</span>
            <span className="text-yellow-300 font-bold">{fmt(snap.vpoc)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">VAL</span>
            <span className="text-green-300">{fmt(snap.val)}</span>
          </div>
          <div className="flex justify-between pt-1 border-t border-gray-700">
            <span className="text-gray-500">Max Pain</span>
            <span className="text-gray-300">{fmt(snap.max_pain)}</span>
          </div>
        </div>
      </Card>

      <Card label="GEX">
        <div className={`text-lg font-bold ${signalColor(snap.gex_signal)}`}>
          {signalLabel(snap.gex_signal)}
        </div>
        <div className="font-mono text-sm text-gray-400 mt-1">
          Net: {fmtM(snap.gex_net)}
        </div>
      </Card>

      <Card label="Put/Call Ratio">
        <div className="space-y-1 text-sm font-mono">
          <div className="flex justify-between">
            <span className="text-gray-500">OI PCR</span>
            <span className={pcrColor(snap.oi_pcr_signal)}>
              {fmt(snap.oi_pcr, 2)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Vol PCR</span>
            <span className={pcrColor(snap.vol_pcr_signal)}>
              {fmt(snap.vol_pcr, 2)}
            </span>
          </div>
        </div>
      </Card>
    </div>
  )
}
