'use client'

import { useEffect, useState } from 'react'
import useSWR from 'swr'
import { fetchSnapshot } from '@/lib/api'
import { Snapshot } from '@/lib/types'
import AIBanner from '@/components/AIBanner'
import AlertsFeed from '@/components/AlertsFeed'
import GexChart from '@/components/GexChart'
import Header from '@/components/Header'
import HeadlinesFeed from '@/components/HeadlinesFeed'
import MetricsRow from '@/components/MetricsRow'
import StatGrid from '@/components/StatGrid'

const SYMBOLS = ['SPY', 'QQQ']
const REFRESH_MS = 60_000

function useSnapshot(symbol: string) {
  return useSWR<Snapshot | null>(
    symbol,
    () => fetchSnapshot(symbol),
    { refreshInterval: REFRESH_MS, revalidateOnFocus: true }
  )
}

export default function Dashboard() {
  const [active, setActive] = useState('SPY')
  const { data: snap, isLoading } = useSnapshot(active)

  // Prefetch the other symbol
  useSnapshot(active === 'SPY' ? 'QQQ' : 'SPY')

  return (
    <div className="min-h-screen bg-gray-950">
      <Header
        activeSymbol={active}
        symbols={SYMBOLS}
        snapshot={snap ?? null}
        loading={isLoading}
        onSymbolChange={setActive}
      />

      {snap ? (
        <>
          {snap.interpretation && <AIBanner interp={snap.interpretation} />}

          <StatGrid symbol={active} snap={snap} />

          <MetricsRow snap={snap} />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mx-6 mt-3">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">
                GEX Levels by Strike
              </div>
              <GexChart levels={snap.gex_levels ?? []} spot={snap.spot} />
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">
                Options Flow Alerts
              </div>
              <AlertsFeed alerts={snap.options_alerts ?? []} />
            </div>
          </div>

          <div className="mx-6 mt-3 mb-8 bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">
              Top Headlines
            </div>
            <HeadlinesFeed headlines={snap.top_headlines ?? []} />
          </div>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center h-64 gap-3">
          {isLoading ? (
            <>
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-gray-500 text-sm">Loading {active} snapshot…</p>
            </>
          ) : (
            <p className="text-gray-500 text-sm">
              No data available — backend may be starting up
            </p>
          )}
        </div>
      )}
    </div>
  )
}
