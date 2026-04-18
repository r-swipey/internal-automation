import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { contractorsAPI, timesheetsAPI } from '../services/api'
import { OUTLETS } from '../config/outlets'

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']
const DAY_LABELS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']

function getDaysInMonth(year, month) {
  return new Date(year, month, 0).getDate()
}

function getFirstDayOfMonth(year, month) {
  return new Date(year, month - 1, 1).getDay()
}

function getDayName(year, month, day) {
  return new Date(year, month - 1, day).toLocaleDateString('en-MY', { weekday: 'short' })
}

function statusBadge(status) {
  const map = {
    submitted: 'badge-yellow', approved: 'badge-green',
    rejected: 'badge-red', synced: 'badge-green', failed: 'badge-red', pending: 'badge-gray',
  }
  return <span className={`badge ${map[status] || 'badge-gray'}`}>{status}</span>
}

// Shared style for stepper +/− buttons — 40×40px, meets mobile tap target guidance
const STEP_BTN = {
  width: 40, height: 40, borderRadius: 8,
  border: '1px solid #e2e8f0', background: '#f9fafb',
  fontSize: 22, fontWeight: 300, lineHeight: 1,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  flexShrink: 0, cursor: 'pointer',
  touchAction: 'manipulation',
  WebkitTapHighlightColor: 'transparent',
  userSelect: 'none',
}

export default function ContractorTimesheet() {
  const { token } = useParams()
  const now = new Date()

  const [contractor, setContractor] = useState(null)
  const [submissions, setSubmissions] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)

  // Outlet for this submission — all days in a submission share one outlet
  const [outlet, setOutlet] = useState('')

  // submittedDays: { [day]: { status, hours, outlet } }
  const [submittedDays, setSubmittedDays] = useState({})
  // dailyHours: hours for newly selected days { [day]: hours }
  const [dailyHours, setDailyHours] = useState({})

  useEffect(() => {
    async function load() {
      try {
        const [cRes, hRes] = await Promise.all([
          contractorsAPI.getByToken(token),
          timesheetsAPI.submissionHistory(token),
        ])
        setContractor(cRes.data)
        setOutlet(cRes.data.outlet)
        setSubmissions(hRes.data)
      } catch {
        setError('This link is invalid or has expired.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [token])

  // Reset selections whenever the period changes
  useEffect(() => {
    if (!contractor) return
    setDailyHours({})
    timesheetsAPI.getSubmittedDays(token, year, month)
      .then(res => {
        const map = {}
        for (const d of res.data) map[d.day] = { status: d.status, hours: parseFloat(d.hours), outlet: d.outlet }
        setSubmittedDays(map)
      })
      .catch(() => setSubmittedDays({}))
  }, [contractor, token, year, month])

  const totalHours = Object.values(dailyHours).reduce((s, h) => s + h, 0)
  const estimatedPay = contractor ? (totalHours * parseFloat(contractor.hourly_rate || 0)).toFixed(2) : '0.00'
  const daysSelected = Object.keys(dailyHours).length

  function isDayLocked(day) {
    const s = submittedDays[day]?.status
    return s === 'submitted' || s === 'approved'
  }

  function isDayRejected(day) {
    return submittedDays[day]?.status === 'rejected'
  }

  function toggleDay(day) {
    if (isDayLocked(day)) return
    setDailyHours(prev => {
      const next = { ...prev }
      if (next[day] !== undefined) {
        delete next[day]
      } else {
        next[day] = isDayRejected(day) ? (submittedDays[day]?.hours || 8) : 8
      }
      return next
    })
  }

  function stepHours(day, delta) {
    setDailyHours(prev => {
      const current = prev[day] ?? 8
      const next = Math.round((current + delta) * 2) / 2
      return { ...prev, [day]: Math.min(24, Math.max(0.5, next)) }
    })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (totalHours === 0) return
    setError('')
    setSubmitting(true)
    try {
      const days = Object.entries(dailyHours).map(([day, hours]) => ({
        day: Number(day),
        hours,
        outlet,
      }))
      await timesheetsAPI.submit(token, { year, month, outlet, days })
      const [hRes, dRes] = await Promise.all([
        timesheetsAPI.submissionHistory(token),
        timesheetsAPI.getSubmittedDays(token, year, month),
      ])
      setSubmissions(hRes.data)
      const map = {}
      for (const d of dRes.data) map[d.day] = { status: d.status, hours: parseFloat(d.hours), outlet: d.outlet }
      setSubmittedDays(map)
      setDailyHours({})
      setSubmitted(true)
    } catch (err) {
      setError(err.response?.data?.detail || 'Submission failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="page"><span className="spinner" /></div>

  if (error && !contractor) {
    return (
      <div className="page">
        <div className="card card-sm text-center stack" style={{ gap: 12 }}>
          <div style={{ fontSize: 32 }}>⚠️</div>
          <p className="text-muted">{error}</p>
        </div>
      </div>
    )
  }

  const daysInMonth = getDaysInMonth(year, month)
  const firstDay = getFirstDayOfMonth(year, month)
  const calendarCells = [
    ...Array(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]

  const hasLockedDays = Object.values(submittedDays).some(d => d.status === 'submitted' || d.status === 'approved')
  const hasRejectedDays = Object.values(submittedDays).some(d => d.status === 'rejected')
  const sortedSelectedDays = Object.keys(dailyHours).map(Number).sort((a, b) => a - b)

  // All outlet options, ensuring contractor's home outlet is always present
  const outletOptions = [...new Set([contractor?.outlet, ...OUTLETS].filter(Boolean))]

  return (
    <div className="page" style={{ justifyContent: 'flex-start', paddingTop: 32, gap: 20 }}>
      <div className="card card-sm" style={{ maxWidth: 480 }}>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 17, fontWeight: 600 }}>{contractor?.name}</h2>
          <p className="text-muted text-sm">{contractor?.outlet} · RM {parseFloat(contractor?.hourly_rate || 0).toFixed(2)}/hr</p>
        </div>

        {submitted ? (
          <div className="stack" style={{ gap: 12 }}>
            <div className="alert alert-success">
              ✓ Timesheet updated for {MONTHS[month - 1]} {year}.
            </div>
            <button className="btn btn-ghost" style={{ justifyContent: 'center' }} onClick={() => setSubmitted(false)}>
              Submit more days
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="stack">

            {/* Period selectors — font-size 16px prevents iOS auto-zoom */}
            <div className="row" style={{ gap: 8 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="label">Month</label>
                <select className="input" style={{ fontSize: 16 }} value={month} onChange={e => setMonth(Number(e.target.value))}>
                  {MONTHS.map((m, i) => <option key={i+1} value={i+1}>{m}</option>)}
                </select>
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="label">Year</label>
                <select className="input" style={{ fontSize: 16 }} value={year} onChange={e => setYear(Number(e.target.value))}>
                  {[2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
            </div>

            {/* Outlet for this submission — applies to all days */}
            <div className="form-group">
              <label className="label">
                Outlet
                <span className="text-muted" style={{ fontWeight: 400, marginLeft: 4 }}>(applies to all days in this submission)</span>
              </label>
              <select className="input" style={{ fontSize: 16 }} value={outlet} onChange={e => setOutlet(e.target.value)}>
                {outletOptions.map(o => (
                  <option key={o} value={o}>{o}{o === contractor?.outlet ? ' (your outlet)' : ''}</option>
                ))}
              </select>
            </div>

            {/* Legend */}
            {(hasLockedDays || hasRejectedDays) && (
              <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
                {hasLockedDays && (
                  <div className="row" style={{ gap: 4, alignItems: 'center', fontSize: 12 }}>
                    <div style={{ width: 12, height: 12, borderRadius: 3, background: '#e5e7eb', border: '1px solid #d1d5db' }} />
                    <span className="text-muted">Submitted / locked</span>
                  </div>
                )}
                {hasRejectedDays && (
                  <div className="row" style={{ gap: 4, alignItems: 'center', fontSize: 12 }}>
                    <div style={{ width: 12, height: 12, borderRadius: 3, background: '#fef3c7', border: '1px solid #fbbf24' }} />
                    <span className="text-muted">Rejected — tap to resubmit</span>
                  </div>
                )}
              </div>
            )}

            {/* Calendar — tap to toggle days, no inline inputs */}
            <div>
              <p className="label" style={{ marginBottom: 8 }}>Tap a day to mark it as worked</p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, marginBottom: 4 }}>
                {DAY_LABELS.map(d => (
                  <div key={d} style={{ textAlign: 'center', fontSize: 11, color: '#6b6b6b', fontWeight: 600, padding: '2px 0' }}>{d}</div>
                ))}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
                {calendarCells.map((day, idx) => {
                  if (!day) return <div key={`pad-${idx}`} />
                  const locked = isDayLocked(day)
                  const rejected = isDayRejected(day)
                  const selected = dailyHours[day] !== undefined

                  let bg = '#fafafa'
                  let border = '1px solid #e2e8f0'
                  let numColor = '#374151'
                  let numWeight = 400
                  if (locked) {
                    bg = '#e5e7eb'; border = '1px solid #d1d5db'; numColor = '#9ca3af'
                  } else if (rejected && selected) {
                    bg = '#fffbeb'; border = '2px solid #f59e0b'; numColor = '#d97706'; numWeight = 700
                  } else if (rejected) {
                    bg = '#fef3c7'; border = '1px solid #fbbf24'; numColor = '#d97706'
                  } else if (selected) {
                    bg = 'var(--color-primary)'; border = '2px solid var(--color-primary)'; numColor = '#fff'; numWeight = 700
                  }

                  return (
                    <div
                      key={day}
                      onClick={() => toggleDay(day)}
                      style={{
                        borderRadius: 8, border, background: bg,
                        cursor: locked ? 'default' : 'pointer',
                        padding: '6px 2px',
                        display: 'flex', flexDirection: 'column',
                        alignItems: 'center', justifyContent: 'center',
                        minHeight: 46,
                        userSelect: 'none',
                        opacity: locked ? 0.7 : 1,
                        touchAction: 'manipulation',
                        WebkitTapHighlightColor: 'transparent',
                      }}
                    >
                      <span style={{ fontSize: 13, fontWeight: numWeight, color: numColor, lineHeight: 1 }}>
                        {day}
                      </span>
                      {locked && submittedDays[day] && (
                        <span style={{ fontSize: 9, color: '#9ca3af', marginTop: 3, lineHeight: 1 }}>
                          {submittedDays[day].hours}h
                        </span>
                      )}
                      {selected && !locked && (
                        <span style={{ fontSize: 9, color: rejected ? '#d97706' : 'rgba(255,255,255,0.9)', marginTop: 3, lineHeight: 1 }}>
                          {dailyHours[day]}h
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Per-day hour stepper */}
            {sortedSelectedDays.length > 0 && (
              <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden' }}>
                <div style={{ padding: '10px 14px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#6b6b6b', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    Adjust hours per day
                  </span>
                </div>
                {sortedSelectedDays.map((day, i) => (
                  <div
                    key={day}
                    style={{
                      padding: '12px 14px',
                      borderBottom: i < sortedSelectedDays.length - 1 ? '1px solid #f0f0f0' : 'none',
                      display: 'flex', alignItems: 'center', gap: 8,
                    }}
                  >
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)', flex: 1 }}>
                      {getDayName(year, month, day)} {day}
                      {isDayRejected(day) && (
                        <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 600, color: '#d97706', textTransform: 'uppercase' }}>
                          resubmit
                        </span>
                      )}
                    </span>
                    <button
                      type="button"
                      style={{ ...STEP_BTN, opacity: dailyHours[day] <= 0.5 ? 0.35 : 1 }}
                      onClick={() => stepHours(day, -0.5)}
                      disabled={dailyHours[day] <= 0.5}
                      aria-label={`Decrease hours for day ${day}`}
                    >−</button>
                    <span style={{ minWidth: 38, textAlign: 'center', fontWeight: 700, fontSize: 15, color: 'var(--color-text)', flexShrink: 0 }}>
                      {dailyHours[day]}h
                    </span>
                    <button
                      type="button"
                      style={{ ...STEP_BTN, opacity: dailyHours[day] >= 24 ? 0.35 : 1 }}
                      onClick={() => stepHours(day, 0.5)}
                      disabled={dailyHours[day] >= 24}
                      aria-label={`Increase hours for day ${day}`}
                    >+</button>
                    <button
                      type="button"
                      style={{ ...STEP_BTN, border: 'none', background: 'transparent', color: '#9ca3af', fontSize: 18, width: 32, height: 32 }}
                      onClick={() => toggleDay(day)}
                      aria-label={`Remove day ${day}`}
                    >✕</button>
                  </div>
                ))}
              </div>
            )}

            {/* Summary */}
            <div style={{ background: '#f0f6ff', border: '1px solid #bfdbfe', borderRadius: 8, padding: '12px 16px' }}>
              <div className="row-between">
                <span className="text-sm">Days selected</span>
                <span style={{ fontWeight: 600 }}>{daysSelected} day{daysSelected !== 1 ? 's' : ''}</span>
              </div>
              <div className="row-between" style={{ marginTop: 4 }}>
                <span className="text-sm">Total hours</span>
                <span style={{ fontWeight: 600 }}>{totalHours.toFixed(1)}h</span>
              </div>
              <div className="row-between" style={{ marginTop: 6 }}>
                <span className="text-sm">Estimated payout</span>
                <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--color-primary)' }}>RM {estimatedPay}</span>
              </div>
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <button
              type="submit"
              className="btn btn-primary"
              style={{ justifyContent: 'center', minHeight: 48, fontSize: 15 }}
              disabled={submitting || totalHours === 0}
            >
              {submitting ? <span className="spinner" /> : 'Submit Timesheet'}
            </button>
          </form>
        )}
      </div>

      {submissions.length > 0 && (
        <div className="card card-sm" style={{ maxWidth: 480 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Submission History</h3>
          <div className="stack" style={{ gap: 10 }}>
            {submissions.map((s, i) => {
              const submittedDate = new Date(s.submitted_at)
              const dateLabel = submittedDate.toLocaleDateString('en-MY', { day: 'numeric', month: 'short', year: 'numeric' })
              const timeLabel = submittedDate.toLocaleTimeString('en-MY', { hour: '2-digit', minute: '2-digit' })
              const statusMap = { submitted: 'badge-yellow', approved: 'badge-green', rejected: 'badge-red' }
              return (
                <div
                  key={s.submission_id || i}
                  style={{
                    border: '1px solid var(--color-border)',
                    borderRadius: 8,
                    padding: '12px 14px',
                  }}
                >
                  {/* Header row: period + status */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontWeight: 600, fontSize: 14 }}>{MONTHS[s.month - 1]} {s.year}</span>
                        {s.sequence > 1 && (
                          <span style={{ fontSize: 11, fontWeight: 600, color: '#2563eb', background: '#eff6ff', borderRadius: 4, padding: '1px 6px' }}>
                            #{s.sequence}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 11, color: '#6b6b6b', marginTop: 2 }}>
                        Submitted {dateLabel} · {timeLabel}
                      </div>
                    </div>
                    <span className={`badge ${s.sync_status === 'synced' ? 'badge-blue' : (statusMap[s.timesheet_status] || 'badge-gray')}`}>
                      {s.sync_status === 'synced' ? 'PAID' : s.timesheet_status.toUpperCase()}
                    </span>
                  </div>

                  {/* Details row */}
                  <div style={{ display: 'flex', gap: 16, fontSize: 13 }}>
                    <div>
                      <span style={{ color: '#6b6b6b' }}>Days </span>
                      <span style={{ fontWeight: 600 }}>{s.days_count}</span>
                    </div>
                    <div>
                      <span style={{ color: '#6b6b6b' }}>Hours </span>
                      <span style={{ fontWeight: 600 }}>{parseFloat(s.total_hours).toFixed(1)}h</span>
                    </div>
                    {s.amount != null && (
                      <div>
                        <span style={{ color: '#6b6b6b' }}>Est. </span>
                        <span style={{ fontWeight: 600 }}>RM {parseFloat(s.amount).toFixed(2)}</span>
                      </div>
                    )}
                  </div>

                  {/* Outlets (only if multiple) */}
                  {s.outlets.length > 1 && (
                    <div style={{ marginTop: 6, fontSize: 12, color: '#6b6b6b' }}>
                      {s.outlets.join(' · ')}
                    </div>
                  )}
                  {s.outlets.length === 1 && (
                    <div style={{ marginTop: 4, fontSize: 12, color: '#9ca3af' }}>{s.outlets[0]}</div>
                  )}

                  {/* Rejection reason — only shown when this submission's month is still rejected */}
                  {s.timesheet_status === 'rejected' && s.rejection_reason && (
                    <div style={{ marginTop: 6, fontSize: 12, color: '#991b1b', background: '#fee2e2', borderRadius: 4, padding: '4px 8px' }}>
                      {s.rejection_reason}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
