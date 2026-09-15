import { OptionsAlert } from '@/lib/types'
import { fmtPremium } from '@/lib/utils'

interface Props {
  alerts: OptionsAlert[]
}

export default function AlertsFeed({ alerts }: Props) {
  if (alerts.length === 0) {
    return <div className="text-gray-600 text-sm py-4 text-center">No alerts yet</div>
  }

  return (
    <div className="space-y-2">
      {alerts.map((a, i) => (
        <div
          key={i}
          className={`flex items-start gap-2 px-3 py-2 rounded text-sm border ${
            a.level === 'whale'
              ? 'border-yellow-800 bg-yellow-950/40'
              : 'border-gray-800 bg-gray-900'
          }`}
        >
          <span
            className={`mt-0.5 px-1.5 py-0.5 rounded text-xs font-bold uppercase shrink-0 ${
              a.contract_type === 'call'
                ? 'bg-green-900 text-green-300'
                : 'bg-red-900 text-red-300'
            }`}
          >
            {a.contract_type}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono font-semibold">
                ${a.strike} {a.expiry ?? ''}
              </span>
              <span className="font-mono text-yellow-300 font-bold shrink-0">
                {fmtPremium(a.premium)}
              </span>
            </div>
            <div className="text-gray-500 text-xs mt-0.5 flex gap-2">
              {a.flow_type && <span className="uppercase">{a.flow_type}</span>}
              {a.iv != null && <span>IV {(a.iv * 100).toFixed(0)}%</span>}
              {a.otm_pct != null && a.otm_pct > 0 && (
                <span>{a.otm_pct.toFixed(1)}% OTM</span>
              )}
              {a.level === 'whale' && (
                <span className="text-yellow-500">🐋 WHALE</span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
