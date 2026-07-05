'use client'

import { useState, FormEvent, useCallback } from 'react'

interface ScoreResult {
  risk_score: number
  risk_category: string
  recommended_payment_terms: string
  supporting_reasons: string[]
  country_stability: number
  currency_volatility: number
  trade_sanctions: boolean
  avg_payment_delay: number
  dispute_rate: number
  buyer_reliability_score: number
  suggested_credit_limit: number
}

interface BuyerHistory {
  buyer_id: string
  total_orders: number
  total_value_usd: number
  avg_payment_delay_days: number
  dispute_rate: number
  paid_in_full_rate: number
  primary_country: string
}

interface CountryRisk {
  country: string
  records: Array<{
    month: string
    political_stability_score: number
    currency_volatility_index: number
    trade_sanctions_flag: number
  }>
}

interface RecentDeal {
  id: number
  country: string
  hs_code: number
  value: number
  score: number
  category: string
  terms: string
  timestamp: string
}

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const SAMPLES = [
  { label: 'India Textiles', b: 'buyer_00001', c: 'India', h: '61', v: '50000' },
  { label: 'UAE Machinery', b: 'buyer_02470', c: 'UAE', h: '84', v: '120000' },
  { label: 'Nigeria Steel', b: '', c: 'Nigeria', h: '72', v: '250000' },
  { label: 'Swiss Pharma', b: 'buyer_05258', c: 'Switzerland', h: '11', v: '75000' },
  { label: 'USA Electronics', b: 'buyer_03551', c: 'USA', h: '84', v: '200000' },
]

export default function Home() {
  const [bId, setBId] = useState('')
  const [ctry, setCtry] = useState('')
  const [hs, setHs] = useState('')
  const [val, setVal] = useState('')
  const [res, setRes] = useState<ScoreResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [hist, setHist] = useState<BuyerHistory | null>(null)
  const [deals, setDeals] = useState<RecentDeal[]>([])
  const [tab, setTab] = useState<'score' | 'explore'>('score')
  const [lCtry, setLCtry] = useState('')
  const [lRes, setLRes] = useState<CountryRisk | null>(null)
  const [lBusy, setLBusy] = useState(false)
  const [showHS, setShowHS] = useState(false)

  const submit = useCallback(async (e: FormEvent) => {
    e.preventDefault()
    if (!ctry || !hs || !val) return
    setLoading(true); setErr(''); setRes(null); setHist(null)
    try {
      const r = await fetch(`${API}/score-deal`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ buyer_id: bId || null, buyer_country: ctry, hs_code: parseInt(hs), invoice_value_usd: parseFloat(val) }),
      })
      if (!r.ok) throw new Error((await r.json()).detail || 'Error')
      const d: ScoreResult = await r.json()
      setRes(d)
      setDeals(p => [{ id: Date.now(), country: ctry, hs_code: parseInt(hs), value: parseFloat(val), score: d.risk_score, category: d.risk_category, terms: d.recommended_payment_terms, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }, ...p].slice(0, 30))
      if (bId) fetch(`${API}/buyer/${bId}/history`).then(r => { if (r.ok) r.json().then(setHist) }).catch(() => {})
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : 'Error') }
    finally { setLoading(false) }
  }, [bId, ctry, hs, val])

  const searchCtry = useCallback(async () => {
    if (!lCtry.trim()) return
    setLBusy(true); setLRes(null)
    try { const r = await fetch(`${API}/country/${lCtry.trim()}/risk-trend`); if (r.ok) setLRes(await r.json()) } catch {}
    setLBusy(false)
  }, [lCtry])

  const fill = (s: typeof SAMPLES[0]) => { setBId(s.b); setCtry(s.c); setHs(s.h); setVal(s.v); setRes(null); setHist(null); setErr('') }

  const sc = (s: number) => s < 30 ? 'emerald' : s < 60 ? 'amber' : 'rose'
  const scBg = (s: number) => s < 30 ? 'bg-emerald-600' : s < 60 ? 'bg-amber-500' : 'bg-rose-600'
  const scBorder = (s: number) => s < 30 ? 'border-emerald-600' : s < 60 ? 'border-amber-500' : 'border-rose-600'
  const scText = (s: number) => s < 30 ? 'text-emerald-700' : s < 60 ? 'text-amber-700' : 'text-rose-700'

  return (
    <div className="min-h-screen bg-[#fef3c7]">
      {/* ── HEADER ── */}
      <header className="bg-stone-900 text-white border-b-[6px] border-amber-500">
        <div className="max-w-6xl mx-auto px-5 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-bold tracking-tight" style={{ fontFamily: "'Space Mono', monospace" }}>EXPORTGUARD</h1>
            <span className="text-[10px] bg-amber-500 text-stone-900 font-bold px-2 py-1">v1.0</span>
          </div>
          <nav className="flex items-center gap-1">
            {(['score', 'explore'] as const).map(t => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-4 py-1.5 text-xs font-bold uppercase tracking-wider border-2 transition-colors ${
                  tab === t ? 'bg-amber-500 text-stone-900 border-amber-500' : 'bg-transparent text-white border-transparent hover:border-white/30'
                }`}>
                {t === 'score' ? '[ Score Deal ]' : '[ Explore ]'}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-5 py-6">

        {/* ══════════════════════════════════════════
           TAB: SCORE
           ══════════════════════════════════════════ */}
        {tab === 'score' && (
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

            {/* ── LEFT COL ── */}
            <div className="lg:col-span-2 space-y-5">
              {/* FORM */}
              <div className="card-retro p-5">
                <h2 className="text-sm font-bold uppercase tracking-wider mb-0.5" style={{ fontFamily: "'Space Mono', monospace" }}>NEW DEAL</h2>
                <p className="text-xs text-stone-500 mb-4 font-mono">Fill in the details or try a sample.</p>

                <div className="flex flex-wrap gap-1.5 mb-5">
                  {SAMPLES.map((s, i) => (
                    <button key={i} onClick={() => fill(s)}
                      className="tag-retro border-stone-300 text-stone-600 hover:bg-stone-900 hover:text-white hover:border-stone-900 transition-colors cursor-pointer">
                      {s.label}
                    </button>
                  ))}
                </div>

                <form onSubmit={submit} className="space-y-3.5">
                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider block mb-1">Buyer ID <span className="font-normal text-stone-400">(optional)</span></label>
                    <input value={bId} onChange={e => setBId(e.target.value)} className="input-retro" placeholder="buyer_00001" />
                  </div>
                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider block mb-1">Buyer Country *</label>
                    <input value={ctry} onChange={e => setCtry(e.target.value)} className="input-retro" placeholder="India, USA, Nigeria..." required />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-bold uppercase tracking-wider block mb-1">HS Code *</label>
                      <div className="relative">
                        <input value={hs} onChange={e => setHs(e.target.value)} className="input-retro" placeholder="61" required type="number" min={1} max={99} />
                        <button type="button" onClick={() => setShowHS(!showHS)} className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-bold bg-stone-200 px-1.5 py-0.5 border-2 border-stone-900">?</button>
                      </div>
                      {showHS && (
                        <div className="mt-1 border-[3px] border-stone-900 bg-white p-2 text-xs max-h-48 overflow-y-auto space-y-0.5">
                          {[[1,'Textiles'],[2,'Chemicals'],[3,'Machinery'],[4,'Electronics'],[5,'Automotive'],[6,'Pharma'],[7,'Plastics'],[8,'Agricultural'],[9,'Steel'],[10,'Ceramics'],[11,'Leather'],[12,'Paper'],[13,'Wood'],[14,'Minerals'],[15,'Food'],[16,'Rubber'],[17,'Glass'],[18,'Precious Metals'],[19,'Base Metals'],[20,'Footwear'],[21,'Optical']].map(([k,v]) => (
                            <div key={k} className="flex justify-between px-1 py-0.5 hover:bg-amber-50 cursor-pointer font-mono" onClick={() => { setHs(String(k)); setShowHS(false) }}>
                              <span className="font-bold">HS {String(k).padStart(2,'0')}</span><span className="text-stone-500">{v as string}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    <div>
                      <label className="text-xs font-bold uppercase tracking-wider block mb-1">Invoice (USD) *</label>
                      <input value={val} onChange={e => setVal(e.target.value)} className="input-retro" placeholder="50000" required type="number" min={1} />
                    </div>
                  </div>
                  <button type="submit" disabled={loading || !ctry || !hs || !val}
                    className="w-full btn-retro text-sm tracking-wider">
                    {loading ? 'SCORING...' : '[ SCORE DEAL ]'}
                  </button>
                </form>
              </div>

              {/* BUYER PROFILE */}
              {hist && (
                <div className="card-retro p-5 animate-fadeIn">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="w-3 h-3 bg-amber-500 border-2 border-stone-900" />
                    <span className="text-sm font-bold font-mono uppercase tracking-wider">{hist.buyer_id}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="border-2 border-stone-900 bg-stone-50 p-2.5">
                      <p className="text-xl font-bold font-mono">{hist.total_orders}</p>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Orders</p>
                    </div>
                    <div className="border-2 border-stone-900 bg-stone-50 p-2.5">
                      <p className="text-xl font-bold font-mono">{hist.avg_payment_delay_days.toFixed(0)}d</p>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Delay</p>
                    </div>
                    <div className="border-2 border-stone-900 bg-stone-50 p-2.5">
                      <p className="text-xl font-bold font-mono">{(hist.dispute_rate * 100).toFixed(0)}%</p>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Disputes</p>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5 text-[10px] font-bold font-mono uppercase tracking-wider">
                    <span className="tag-retro text-[10px]">{hist.primary_country}</span>
                    <span className="tag-retro text-[10px]">${(hist.total_value_usd / 1_000_000).toFixed(1)}M</span>
                    <span className="tag-retro text-[10px]">{(hist.paid_in_full_rate * 100).toFixed(0)}% Paid</span>
                  </div>
                </div>
              )}
            </div>

            {/* ── RIGHT COL ── */}
            <div className="lg:col-span-3 space-y-5">

              {err && <div className="border-[3px] border-rose-600 bg-rose-50 p-4 text-sm font-bold text-rose-700">{err}</div>}

              {/* RESULT CARD */}
              {res && (
                <div className="card-retro p-6 animate-fadeIn">
                  {/* BIG — ACTION FIRST */}
                  <div className={`border-[4px] ${scBorder(res.risk_score)} p-4 mb-5 text-center`}>
                    <p className="text-[11px] font-bold uppercase tracking-widest text-stone-500 font-mono">Recommended Action</p>
                    <p className={`text-3xl font-black mt-1 uppercase tracking-tight ${scText(res.risk_score)}`} style={{ fontFamily: "'Space Mono', monospace" }}>
                      {res.risk_score < 30 ? 'CREDIT OK' : res.risk_score < 60 ? 'LC REQUIRED' : 'ADVANCE PAYMENT'}
                    </p>
                  </div>

                  <div className="flex flex-row items-start gap-5">
                    {/* Big score block */}
                    <div className={`w-20 h-20 border-[4px] ${scBorder(res.risk_score)} flex flex-col items-center justify-center shrink-0
                      ${res.risk_category === 'Low Risk' ? 'bg-emerald-50' : res.risk_category === 'Medium Risk' ? 'bg-amber-50' : 'bg-rose-50'}`}>
                      <span className={`text-3xl font-black font-mono leading-none ${scText(res.risk_score)}`}>{Math.round(res.risk_score)}</span>
                      <span className="text-[8px] font-bold font-mono text-stone-500 mt-0.5">/ 100</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-3">
                        <p className={`text-lg font-black uppercase tracking-tight ${scText(res.risk_score)}`}>{res.risk_category}</p>
                        <span className="text-[10px] font-bold font-mono text-stone-500">Credit: ${res.suggested_credit_limit >= 1000 ? `${(res.suggested_credit_limit / 1000).toFixed(0)}K` : res.suggested_credit_limit.toFixed(0)}</span>
                      </div>
                      <div className="w-full h-3 border-[3px] border-stone-900 mt-2 bg-stone-100">
                        <div className={`h-full transition-all duration-500 ${scBg(res.risk_score)}`} style={{ width: `${res.risk_score}%` }} />
                      </div>
                      <p className="text-[10px] font-mono font-bold text-stone-500 mt-1">{res.recommended_payment_terms}</p>
                    </div>
                  </div>

                  <div className="mt-5 pt-4 border-t-[3px] border-stone-900">
                    <p className="text-[11px] font-bold uppercase tracking-widest text-stone-500 font-mono mb-3">Why?</p>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      {res.supporting_reasons.map((r, i) => (
                        <div key={i} className="border-[3px] border-stone-900 bg-stone-50 p-3 text-sm">
                          <span className={`inline-block w-5 h-5 ${scBg(res.risk_score)} text-white text-xs font-bold font-mono flex items-center justify-center mb-1`}>{i + 1}</span>
                          {r}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-5 pt-4 border-t-[3px] border-stone-900">
                    <p className="text-[11px] font-bold uppercase tracking-widest text-stone-500 font-mono mb-3">Deal Insights</p>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div className="border-[3px] border-stone-900 bg-white p-3">
                        <p className="text-[9px] font-black font-mono uppercase text-stone-500">Country Stability</p>
                        <p className="text-xl font-black font-mono mt-1 text-emerald-700">{res.country_stability.toFixed(2)}</p>
                        <div className="w-full h-2 border-[2px] border-stone-900 mt-1.5 bg-stone-100">
                          <div className="h-full bg-emerald-600" style={{ width: `${res.country_stability * 100}%` }} />
                        </div>
                      </div>
                      <div className="border-[3px] border-stone-900 bg-white p-3">
                        <p className="text-[9px] font-black font-mono uppercase text-stone-500">Currency Volatility</p>
                        <p className="text-xl font-black font-mono mt-1 text-amber-700">{res.currency_volatility.toFixed(2)}</p>
                        <div className="w-full h-2 border-[2px] border-stone-900 mt-1.5 bg-stone-100">
                          <div className={`h-full ${res.currency_volatility > 0.5 ? 'bg-rose-600' : 'bg-amber-500'}`} style={{ width: `${res.currency_volatility * 100}%` }} />
                        </div>
                      </div>
                      <div className="border-[3px] border-stone-900 bg-white p-3">
                        <p className="text-[9px] font-black font-mono uppercase text-stone-500">Buyer Reliability</p>
                        <p className={`text-xl font-black font-mono mt-1 ${res.buyer_reliability_score >= 70 ? 'text-emerald-700' : res.buyer_reliability_score >= 40 ? 'text-amber-700' : 'text-rose-700'}`}>
                          {res.buyer_reliability_score.toFixed(0)}%
                        </p>
                        {res.avg_payment_delay > 0 && (
                          <p className="text-[10px] font-mono text-stone-500 mt-0.5">{res.avg_payment_delay.toFixed(0)}d avg delay</p>
                        )}
                      </div>
                      <div className="border-[3px] border-stone-900 bg-white p-3 relative">
                        {res.trade_sanctions && (
                          <span className="absolute -top-2 -right-2 bg-rose-600 text-white text-[9px] font-black font-mono px-1.5 py-0.5 border-[2px] border-stone-900 z-10">SANCTIONS</span>
                        )}
                        <p className="text-[9px] font-black font-mono uppercase text-stone-500">Credit Limit</p>
                        <p className="text-xl font-black font-mono mt-1 text-stone-900">${res.suggested_credit_limit >= 1000 ? `${(res.suggested_credit_limit / 1000).toFixed(0)}K` : res.suggested_credit_limit.toFixed(0)}</p>
                        <p className="text-[9px] font-mono text-stone-500">suggested max</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* RECENT DEALS */}
              {deals.length > 0 && (
                <div className="card-retro animate-fadeIn">
                  <div className="border-b-[3px] border-stone-900 px-5 py-3 flex items-center justify-between">
                    <h3 className="text-sm font-bold font-mono uppercase tracking-wider">Recent Scores</h3>
                    <div className="flex items-center gap-3 text-[10px] font-bold font-mono uppercase">
                      <span className="w-2.5 h-2.5 bg-emerald-600 border border-stone-900 inline-block" />{deals.filter(d => d.score < 30).length}
                      <span className="w-2.5 h-2.5 bg-amber-500 border border-stone-900 inline-block" />{deals.filter(d => d.score >= 30 && d.score < 60).length}
                      <span className="w-2.5 h-2.5 bg-rose-600 border border-stone-900 inline-block" />{deals.filter(d => d.score >= 60).length}
                    </div>
                  </div>
                  {/* Score distribution summary */}
                  {deals.length >= 2 && (
                    <div className="px-5 py-2.5 border-b-[3px] border-stone-900 bg-stone-50 flex items-center gap-4 text-[10px] font-bold font-mono">
                      <span className="text-stone-500 uppercase tracking-wider">Range:</span>
                      <span className="text-emerald-700">Low {deals.filter(d => d.score < 30).length}</span>
                      <span className="text-amber-700">Med {deals.filter(d => d.score >= 30 && d.score < 60).length}</span>
                      <span className="text-rose-700">High {deals.filter(d => d.score >= 60).length}</span>
                      <span className="ml-auto text-stone-500">Avg: {(deals.reduce((s, d) => s + d.score, 0) / deals.length).toFixed(0)}</span>
                    </div>
                  )}
                  <div className="divide-y-[3px] divide-stone-900 max-h-[350px] overflow-y-auto">
                    {deals.map(d => (
                      <div key={d.id} className="px-5 py-2.5 flex items-center gap-3 text-sm hover:bg-amber-50 transition-colors">
                        <span className={`w-10 h-10 border-[3px] border-stone-900 flex items-center justify-center text-sm font-black font-mono text-white ${scBg(d.score)}`}>
                          {Math.round(d.score)}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="font-bold font-mono">{d.country} <span className="font-normal text-stone-500">HS {d.hs_code}</span></p>
                          <p className="text-xs font-mono text-stone-500">${d.value.toLocaleString()} &middot; {d.timestamp}</p>
                        </div>
                        <span className="text-[11px] font-bold font-mono text-right shrink-0 max-w-[140px] uppercase">{d.terms}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* EMPTY */}
              {!res && deals.length === 0 && !err && (
                <div className="card-retro p-10 text-center">
                  <div className="w-16 h-16 border-[4px] border-stone-900 bg-amber-100 flex items-center justify-center mx-auto mb-4">
                    <span className="text-2xl font-bold font-mono text-stone-600">?</span>
                  </div>
                  <p className="text-lg font-black font-mono uppercase tracking-wider text-stone-500">Score a Deal</p>
                  <p className="text-sm font-mono text-stone-400 mt-1">Fill in the form or click a sample above</p>
                  <div className="flex justify-center gap-2 mt-5">
                    {SAMPLES.slice(0, 3).map((s, i) => (
                      <button key={i} onClick={() => fill(s)}
                        className="tag-retro border-stone-400 text-stone-600 hover:bg-stone-900 hover:text-white hover:border-stone-900 cursor-pointer">
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════
           TAB: EXPLORE
           ══════════════════════════════════════════ */}
        {tab === 'explore' && (
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

            <div className="lg:col-span-3">
              <div className="card-retro p-5">
                <h2 className="text-sm font-bold font-mono uppercase tracking-wider mb-0.5">Country Risk</h2>
                <p className="text-xs text-stone-500 mb-4 font-mono">Look up political stability, currency volatility, and sanctions.</p>
                <div className="flex gap-2 mb-5">
                  <input value={lCtry} onChange={e => setLCtry(e.target.value)} onKeyDown={e => e.key === 'Enter' && searchCtry()}
                    className="input-retro flex-1" placeholder="Type a country name..." />
                  <button onClick={searchCtry} disabled={lBusy} className="btn-retro text-sm">
                    {lBusy ? '...' : '[ SEARCH ]'}
                  </button>
                </div>

                {lRes && lRes.records?.length > 0 && (
                  <div className="animate-fadeIn">
                    <div className="border-[3px] border-stone-900 bg-amber-50 p-5">
                      <h3 className="text-xl font-black font-mono uppercase tracking-tight mb-5">{lRes.country}</h3>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="border-[3px] border-stone-900 bg-white p-4">
                          <p className="text-[10px] font-bold font-mono uppercase tracking-wider text-stone-500 mb-1">Stability</p>
                          <p className="text-2xl font-black font-mono text-emerald-700">{lRes.records[0].political_stability_score.toFixed(2)}</p>
                          <div className="w-full h-2 border-2 border-stone-900 mt-2 bg-stone-100">
                            <div className="h-full bg-emerald-600 transition-all" style={{ width: `${lRes.records[0].political_stability_score * 100}%` }} />
                          </div>
                        </div>
                        <div className="border-[3px] border-stone-900 bg-white p-4">
                          <p className="text-[10px] font-bold font-mono uppercase tracking-wider text-stone-500 mb-1">Volatility</p>
                          <p className="text-2xl font-black font-mono text-amber-700">{lRes.records[0].currency_volatility_index.toFixed(2)}</p>
                          <div className="w-full h-2 border-2 border-stone-900 mt-2 bg-stone-100">
                            <div className="h-full bg-amber-500 transition-all" style={{ width: `${lRes.records[0].currency_volatility_index * 100}%` }} />
                          </div>
                        </div>
                        <div className="border-[3px] border-stone-900 bg-white p-4">
                          <p className="text-[10px] font-bold font-mono uppercase tracking-wider text-stone-500 mb-1">Sanctions</p>
                          <p className={`text-2xl font-black font-mono ${lRes.records[0].trade_sanctions_flag ? 'text-rose-700' : 'text-emerald-700'}`}>
                            {lRes.records[0].trade_sanctions_flag ? 'YES' : 'NO'}
                          </p>
                          <div className="w-full h-2 border-2 border-stone-900 mt-2 bg-stone-100">
                            <div className={`h-full transition-all ${lRes.records[0].trade_sanctions_flag ? 'bg-rose-600 w-full' : 'bg-emerald-600 w-[10%]'}`} />
                          </div>
                        </div>
                      </div>
                      <p className="text-[10px] font-mono text-stone-500 mt-3">{lRes.records.length} months tracked</p>
                    </div>

                    {/* Stability trend — mini table */}
                    <div className="mt-4">
                      <p className="text-[11px] font-bold font-mono uppercase tracking-wider text-stone-500 mb-2">Stability Trend (last 12 months)</p>
                      <div className="border-[3px] border-stone-900 divide-y-[2px] divide-stone-900">
                        {lRes.records.slice(-12).reverse().map((r, i) => (
                          <div key={i} className="flex items-center gap-3 px-3 py-1.5 text-xs font-mono bg-white">
                            <span className="w-20 font-bold text-stone-600">{r.month.slice(0, 7)}</span>
                            <div className="flex-1 h-3 border-[2px] border-stone-900 bg-stone-100">
                              <div className={`h-full ${r.political_stability_score > 0.6 ? 'bg-emerald-600' : r.political_stability_score > 0.3 ? 'bg-amber-500' : 'bg-rose-600'}`}
                                style={{ width: `${r.political_stability_score * 100}%` }} />
                            </div>
                            <span className="w-12 text-right font-bold text-stone-700">{r.political_stability_score.toFixed(2)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {!lRes && !lBusy && (
                  <div className="text-center py-12 font-mono text-stone-400">
                    <p className="text-sm font-bold uppercase tracking-wider">Search a country</p>
                    <p className="text-xs mt-1">to see its risk profile</p>
                  </div>
                )}
              </div>
            </div>

            {/* ── SIDEBAR ── */}
            <div className="lg:col-span-2 space-y-5">
              {/* HS CODES */}
              <div className="card-retro p-5">
                <h3 className="text-sm font-bold font-mono uppercase tracking-wider mb-3">HS Codes</h3>
                <div className="text-xs space-y-0.5 max-h-64 overflow-y-auto">
                  {[[1,'Textiles'],[2,'Chemicals'],[3,'Machinery'],[4,'Electronics'],[5,'Automotive'],[6,'Pharma'],[7,'Plastics'],[8,'Agricultural'],[9,'Steel'],[10,'Ceramics'],[11,'Leather'],[12,'Paper'],[13,'Wood'],[14,'Minerals'],[15,'Food'],[16,'Rubber'],[17,'Glass'],[18,'Precious Metals'],[19,'Base Metals'],[20,'Footwear'],[21,'Optical']].map(([k,v]) => (
                    <div key={k} onClick={() => { setHs(String(k)); setTab('score') }}
                      className="flex justify-between px-2 py-1.5 border-b-2 border-stone-200 hover:bg-amber-50 hover:border-stone-900 cursor-pointer transition-colors font-mono">
                      <span className="font-bold">HS {String(k).padStart(2,'0')}</span>
                      <span className="text-stone-500">{v as string}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* PAYMENT TERMS */}
              <div className="card-retro p-5">
                <h3 className="text-sm font-bold font-mono uppercase tracking-wider mb-3">Payment Terms</h3>
                <div className="space-y-2">
                  <div className="border-[3px] border-emerald-600 bg-emerald-50 p-3">
                    <p className="text-xs font-black font-mono text-emerald-700">SCORE 0-30</p>
                    <p className="text-[11px] font-bold text-emerald-600 mt-0.5">CREDIT OK &mdash; Safe to offer net 30/60 terms</p>
                  </div>
                  <div className="border-[3px] border-amber-500 bg-amber-50 p-3">
                    <p className="text-xs font-black font-mono text-amber-700">SCORE 31-60</p>
                    <p className="text-[11px] font-bold text-amber-600 mt-0.5">LC REQUIRED &mdash; Bank guarantee recommended</p>
                  </div>
                  <div className="border-[3px] border-rose-600 bg-rose-50 p-3">
                    <p className="text-xs font-black font-mono text-rose-700">SCORE 61-100</p>
                    <p className="text-[11px] font-bold text-rose-600 mt-0.5">ADVANCE PAYMENT &mdash; Demand full prepayment</p>
                  </div>
                </div>
              </div>

              {/* SESSION */}
              {deals.length > 0 && (
                <div className="card-retro p-5">
                  <h3 className="text-sm font-bold font-mono uppercase tracking-wider mb-3">Session</h3>
                  <div className="grid grid-cols-2 gap-2 text-center">
                    <div className="border-[3px] border-stone-900 bg-stone-50 p-3">
                      <p className="text-2xl font-black font-mono">{deals.length}</p>
                      <p className="text-[10px] font-bold font-mono uppercase tracking-wider text-stone-500">Scored</p>
                    </div>
                    <div className="border-[3px] border-stone-900 bg-stone-50 p-3">
                      <p className="text-2xl font-black font-mono">{new Set(deals.map(d => d.country)).size}</p>
                      <p className="text-[10px] font-bold font-mono uppercase tracking-wider text-stone-500">Countries</p>
                    </div>
                  </div>
                  {(() => { const t = deals.length; const l = deals.filter(d => d.score < 30).length; const m = deals.filter(d => d.score >= 30 && d.score < 60).length; const h = deals.filter(d => d.score >= 60).length; return t > 0 && (
                    <div className="mt-3">
                      <div className="flex h-3 border-[3px] border-stone-900">
                        {l > 0 && <div className="bg-emerald-600" style={{ width: `${(l/t)*100}%` }} />}
                        {m > 0 && <div className="bg-amber-500" style={{ width: `${(m/t)*100}%` }} />}
                        {h > 0 && <div className="bg-rose-600" style={{ width: `${(h/t)*100}%` }} />}
                      </div>
                      <div className="flex justify-center gap-3 mt-1 text-[10px] font-bold font-mono">
                        {l > 0 && <span className="flex items-center gap-1"><span className="w-2 h-2 bg-emerald-600 border border-stone-900" />{l}</span>}
                        {m > 0 && <span className="flex items-center gap-1"><span className="w-2 h-2 bg-amber-500 border border-stone-900" />{m}</span>}
                        {h > 0 && <span className="flex items-center gap-1"><span className="w-2 h-2 bg-rose-600 border border-stone-900" />{h}</span>}
                      </div>
                    </div>
                  )})()}
                </div>
              )}
            </div>
          </div>
        )}

      </div>

      <footer className="border-t-[3px] border-stone-900 mt-8 px-5 py-4 text-center text-[10px] font-mono font-bold text-stone-500">
        EXPORTGUARD &middot; FASTAPI + NEXT.JS + BIGQUERY
      </footer>
    </div>
  )
}
