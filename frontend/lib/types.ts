export interface GexLevel {
  price: number
  gex: number
}

export interface OptionsAlert {
  symbol: string
  expiry?: string
  strike: number
  type: 'call' | 'put'
  premium: number
  flow_type?: string
  iv?: number
  otm_pct?: number
  level: 'alert' | 'whale'
  timestamp?: string
}

export interface AIInterpretation {
  support?: number
  resistance?: number
  bias: 'bullish' | 'bearish' | 'neutral' | 'unknown'
  key_level?: number
  trigger_long?: string
  trigger_short?: string
  confidence?: 'high' | 'medium' | 'low'
  summary?: string
  error?: string
}

export interface Snapshot {
  vpoc: number
  vah: number
  val: number
  vpoc_bias: 'bullish' | 'bearish' | 'neutral'
  gex_net: number
  gex_signal: 'mean_revert' | 'trend_amplify' | 'neutral'
  max_pain: number
  gex_levels: GexLevel[]
  oi_pcr: number
  vol_pcr: number
  oi_pcr_signal: string
  vol_pcr_signal: string
  spot: number
  vix?: number
  vvix_ratio?: number
  options_count?: number
  options_alerts?: OptionsAlert[]
  top_headlines?: string[]
  interpretation?: AIInterpretation
  written_at: string
}
