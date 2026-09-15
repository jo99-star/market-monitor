import { AIInterpretation } from '@/lib/types'
import { biasColor, confidenceBadge, fmt } from '@/lib/utils'

interface Props {
  interp: AIInterpretation
}

export default function AIBanner({ interp }: Props) {
  if (interp.bias === 'unknown' || interp.error) return null

  return (
    <div className="mx-6 mt-4 rounded-lg border border-gray-700 bg-gray-900 p-4">
      <div className="flex flex-wrap items-start gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 uppercase tracking-wider">AI Bias</span>
          <span className={`text-lg font-bold capitalize ${biasColor(interp.bias)}`}>
            {interp.bias}
          </span>
          {interp.confidence && (
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${confidenceBadge(interp.confidence)}`}>
              {interp.confidence}
            </span>
          )}
        </div>

        {interp.support != null && interp.resistance != null && (
          <div className="flex gap-4 text-sm">
            <span className="text-gray-500">
              Support <span className="text-green-400 font-mono font-bold">{fmt(interp.support)}</span>
            </span>
            <span className="text-gray-500">
              Resistance <span className="text-red-400 font-mono font-bold">{fmt(interp.resistance)}</span>
            </span>
            {interp.key_level != null && (
              <span className="text-gray-500">
                Key Level <span className="text-yellow-400 font-mono font-bold">{fmt(interp.key_level)}</span>
              </span>
            )}
          </div>
        )}
      </div>

      {interp.summary && (
        <p className="mt-2 text-sm text-gray-300">{interp.summary}</p>
      )}

      {(interp.trigger_long || interp.trigger_short) && (
        <div className="mt-2 flex flex-wrap gap-4 text-xs">
          {interp.trigger_long && (
            <span className="text-gray-500">
              Long: <span className="text-green-300">{interp.trigger_long}</span>
            </span>
          )}
          {interp.trigger_short && (
            <span className="text-gray-500">
              Short: <span className="text-red-300">{interp.trigger_short}</span>
            </span>
          )}
        </div>
      )}
    </div>
  )
}
