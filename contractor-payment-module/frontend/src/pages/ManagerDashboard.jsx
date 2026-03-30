import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { contractorsAPI, timesheetsAPI, usersAPI } from '../services/api'
import { OUTLETS } from '../config/outlets'

function statusBadge(status) {
  const map = {
    active: 'badge-green', pending: 'badge-yellow', pending_registration: 'badge-yellow',
    inactive: 'badge-gray', terminated: 'badge-gray',
    submitted: 'badge-yellow', approved: 'badge-green', rejected: 'badge-red',
    synced: 'badge-green', failed: 'badge-red', syncing: 'badge-blue',
  }
  return <span className={`badge ${map[status] || 'badge-gray'}`}>{status}</span>
}

function canProcessTimesheet(timesheet) {
  return timesheet.status === 'approved' && ['pending', 'failed'].includes(timesheet.sync_status)
}

// ── Add Contractor Modal ───────────────────────────────────────────────────────
function AddContractorModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', phone: '', outlet: '', hourly_rate: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await contractorsAPI.create({ ...form, hourly_rate: parseFloat(form.hourly_rate) })
      onCreated(res.data)
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create contractor')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: 16 }}>
      <div className="card" style={{ width: '100%', maxWidth: 440 }}>
        <div className="row-between" style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>Add Contractor</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={submit} className="stack">
          {[['name', 'Full Name', 'text', 'e.g. Ahmad bin Salleh'], ['phone', 'Phone', 'tel', '+601x-xxx xxxx']].map(([key, label, type, ph]) => (
            <div className="form-group" key={key}>
              <label className="label">{label}</label>
              <input className="input" type={type} placeholder={ph} required value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
            </div>
          ))}
          <div className="form-group">
            <label className="label">Outlet</label>
            <select className="input" required value={form.outlet} onChange={e => setForm(f => ({ ...f, outlet: e.target.value }))}>
              <option value="">Select outlet…</option>
              {OUTLETS.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="label">Hourly Rate (RM)</label>
            <input className="input" type="number" min="0.01" step="0.01" placeholder="e.g. 12.50" required value={form.hourly_rate} onChange={e => setForm(f => ({ ...f, hourly_rate: e.target.value }))} />
          </div>
          {error && <div className="alert alert-error">{error}</div>}
          <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? <span className="spinner" /> : 'Create'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Contractor Detail Panel ────────────────────────────────────────────────────
function ContractorDetailPanel({ contractor: c, onClose, onAction }) {
  const [qrImageUrl, setQrImageUrl] = useState(null)
  const [qrLoading, setQrLoading] = useState(false)
  const [qrError, setQrError] = useState(false)
  const [copied, setCopied] = useState(false)
  const [copiedTs, setCopiedTs] = useState(false)

  useEffect(() => {
    if (!c.qr_image_path) return
    setQrLoading(true)
    setQrError(false)
    contractorsAPI.getQRImage(c.id)
      .then(res => setQrImageUrl(res.data.signed_url))
      .catch(() => setQrError(true))
      .finally(() => setQrLoading(false))
  }, [c.id])

  function copyRegLink() {
    navigator.clipboard.writeText(`${window.location.origin}/register/${c.registration_token}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  function copyTsLink() {
    navigator.clipboard.writeText(`${window.location.origin}/timesheet/${c.registration_token}`)
    setCopiedTs(true)
    setTimeout(() => setCopiedTs(false), 1800)
  }

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)', zIndex: 200 }} />
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 400, maxWidth: '95vw',
        background: '#fff', boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
        zIndex: 201, overflowY: 'auto', padding: 24,
        display: 'flex', flexDirection: 'column', gap: 20,
      }}>
        {/* Header */}
        <div className="row-between">
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>Contractor Details</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        {/* Identity */}
        <div style={{ background: '#f9fafb', borderRadius: 8, padding: '14px 16px' }}>
          <div style={{ fontWeight: 600, fontSize: 15 }}>{c.name}</div>
          <div className="text-sm text-muted" style={{ marginTop: 2 }}>{c.phone} · {c.outlet}</div>
          <div style={{ marginTop: 6 }}>{statusBadge(c.status)}</div>
          {c.ic_number && <div className="text-sm text-muted" style={{ marginTop: 6 }}>IC: {c.ic_number}</div>}
        </div>

        {/* Payment details */}
        <div>
          <div className="label" style={{ marginBottom: 6 }}>Payment details</div>
          {c.bank_name && c.account_number ? (
            <div style={{ fontSize: 14 }}>
              <span style={{ fontWeight: 600 }}>{c.bank_name}</span>
              <span className="text-muted" style={{ marginLeft: 8 }}>···{c.account_number.slice(-4)}</span>
            </div>
          ) : (
            <div className="text-muted text-sm">Not registered yet</div>
          )}
        </div>

        {/* Registration info */}
        <div>
          <div className="label" style={{ marginBottom: 6 }}>Registration</div>
          <div className="text-sm text-muted">
            {c.registered_at
              ? new Date(c.registered_at).toLocaleDateString('en-MY', { dateStyle: 'medium' })
              : 'Not yet registered'}
          </div>
        </div>

        {/* QR image */}
        <div>
          <div className="label" style={{ marginBottom: 6 }}>QR Code on file</div>
          {qrLoading && <span className="spinner" />}
          {!qrLoading && qrError && <div className="text-sm text-muted" style={{ color: '#b91c1c' }}>Could not load QR image</div>}
          {!qrLoading && !qrError && qrImageUrl && (
            <img src={qrImageUrl} alt="QR Code" style={{ width: '100%', maxWidth: 220, borderRadius: 8, border: '1px solid #e5e7eb' }} />
          )}
          {!qrLoading && !qrError && !qrImageUrl && !c.qr_image_path && (
            <div className="text-sm text-muted">No QR image on file</div>
          )}
        </div>

        {/* Links */}
        <div>
          <div className="label" style={{ marginBottom: 6 }}>Links</div>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={copyRegLink}>
              {copied ? '✓ Copied' : '🪪 Registration link'}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={copyTsLink}>
              {copiedTs ? '✓ Copied' : '🕐 Timesheet link'}
            </button>
          </div>
        </div>

        {/* Actions */}
        <div>
          {c.status === 'inactive' ? (
            <button className="btn btn-primary btn-sm" onClick={async () => {
              if (confirm('Re-activate this contractor?')) {
                await contractorsAPI.update(c.id, { status: 'pending' })
                onAction()
              }
            }}>
              Re-activate
            </button>
          ) : (c.status === 'active' || c.status === 'pending') ? (
            <button className="btn btn-sm" style={{ background: '#f3f4f6', color: '#374151' }} onClick={async () => {
              if (confirm('Deactivate this contractor?')) {
                await contractorsAPI.deactivate(c.id)
                onAction()
              }
            }}>
              Deactivate
            </button>
          ) : null}
        </div>
      </div>
    </>
  )
}

// ── Contractors Tab ────────────────────────────────────────────────────────────
function ContractorsTab() {
  const [contractors, setContractors] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [copied, setCopied] = useState(null)
  const [copiedTs, setCopiedTs] = useState(null)
  const [filterName, setFilterName] = useState('')
  const [filterOutlet, setFilterOutlet] = useState('')
  const [selectedContractor, setSelectedContractor] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await contractorsAPI.list()
      setContractors(res.data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = contractors.filter(c => {
    const matchName = !filterName || c.name.toLowerCase().includes(filterName.toLowerCase())
    const matchOutlet = !filterOutlet || c.outlet === filterOutlet
    return matchName && matchOutlet
  })

  function copyLink(token) {
    const link = `${window.location.origin}/register/${token}`
    navigator.clipboard.writeText(link)
    setCopied(token)
    setTimeout(() => setCopied(null), 1800)
  }

  function copyTimesheetLink(token) {
    const link = `${window.location.origin}/timesheet/${token}`
    navigator.clipboard.writeText(link)
    setCopiedTs(token)
    setTimeout(() => setCopiedTs(null), 1800)
  }

  return (
    <div className="container" style={{ padding: '24px 16px' }}>
      <div className="row-between" style={{ marginBottom: 12, flexWrap: 'wrap', gap: 10 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600 }}>Contractors</h2>
        <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(true)}>+ Add Contractor</button>
      </div>
      <div className="row" style={{ gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          className="input"
          style={{ width: 180 }}
          type="text"
          placeholder="Search name…"
          value={filterName}
          onChange={e => setFilterName(e.target.value)}
        />
        <select className="input" style={{ width: 160 }} value={filterOutlet} onChange={e => setFilterOutlet(e.target.value)}>
          <option value="">All outlets</option>
          {OUTLETS.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
        {(filterName || filterOutlet) && (
          <button className="btn btn-ghost btn-sm" onClick={() => { setFilterName(''); setFilterOutlet('') }}>Clear</button>
        )}
      </div>

      {showAdd && <AddContractorModal onClose={() => setShowAdd(false)} onCreated={c => setContractors(prev => [c, ...prev])} />}
      {selectedContractor && (
        <ContractorDetailPanel
          contractor={selectedContractor}
          onClose={() => setSelectedContractor(null)}
          onAction={() => { setSelectedContractor(null); load() }}
        />
      )}

      {loading ? (
        <div className="text-center text-muted" style={{ padding: 40 }}><span className="spinner" /></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Outlet</th>
                <th>Status</th>
                <th>Bank</th>
                <th>Rate/hr</th>
                <th>Links</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={7} className="text-center text-muted" style={{ padding: 32 }}>{contractors.length === 0 ? 'No contractors yet' : 'No contractors match the filters'}</td></tr>
              )}
              {filtered.map(c => (
                <tr key={c.id} style={{ cursor: 'pointer' }} onClick={() => setSelectedContractor(c)}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{c.name}</div>
                    <div className="text-muted text-sm">{c.phone}</div>
                  </td>
                  <td>{c.outlet}</td>
                  <td>{statusBadge(c.status)}</td>
                  <td>
                    {c.bank_name
                      ? <><div style={{ fontWeight: 500 }}>{c.bank_name}</div><div className="text-muted text-sm">···{c.account_number?.slice(-4)}</div></>
                      : <span className="text-muted text-sm">Not set</span>
                    }
                  </td>
                  <td>RM {parseFloat(c.hourly_rate).toFixed(2)}</td>
                  <td onClick={e => e.stopPropagation()}>
                    <div className="row" style={{ gap: 4 }}>
                      <button
                        className="btn btn-ghost btn-sm btn-icon"
                        title="Copy registration link"
                        onClick={() => copyLink(c.registration_token)}
                      >
                        {copied === c.registration_token ? '✓' : '🪪'}
                      </button>
                      <button
                        className="btn btn-ghost btn-sm btn-icon"
                        title="Copy timesheet link"
                        onClick={() => copyTimesheetLink(c.registration_token)}
                      >
                        {copiedTs === c.registration_token ? '✓' : '🕐'}
                      </button>
                    </div>
                  </td>
                  <td onClick={e => e.stopPropagation()}>
                    {c.status === 'inactive' ? (
                      <button className="btn btn-primary btn-sm"
                        onClick={async () => { if (confirm('Re-activate this contractor?')) { await contractorsAPI.update(c.id, { status: 'pending' }); load() } }}>
                        Re-activate
                      </button>
                    ) : (
                      <button className="btn btn-sm" style={{ background: '#f3f4f6', color: '#374151' }}
                        onClick={async () => { if (confirm('Deactivate this contractor?')) { await contractorsAPI.deactivate(c.id); load() } }}>
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Timesheet Detail Panel ─────────────────────────────────────────────────────
function TimesheetDetailPanel({ timesheet: ts, months, onClose, onAction, onRefresh }) {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [rejecting, setRejecting] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [days, setDays] = useState([])
  const [dayLogs, setDayLogs] = useState([])
  const [editingDayId, setEditingDayId] = useState(null)
  const [editRate, setEditRate] = useState('')
  const [rateSaving, setRateSaving] = useState(false)
  const [rateError, setRateError] = useState('')
  const [showLog, setShowLog] = useState(false)

  function loadDays() {
    timesheetsAPI.getDays(ts.id).then(res => setDays(res.data)).catch(() => {})
  }

  useEffect(() => {
    loadDays()
    timesheetsAPI.getDayLogs(ts.id).then(res => setDayLogs(res.data)).catch(() => {})
  }, [ts.id])

  function getDayName(day) {
    return new Date(ts.year, ts.month - 1, day).toLocaleDateString('en-MY', { weekday: 'short' })
  }

  function startEditRate(day) {
    setEditingDayId(day.id)
    setEditRate(day.hourly_rate != null ? String(parseFloat(day.hourly_rate).toFixed(2)) : String(parseFloat(ts.hourly_rate).toFixed(2)))
    setRateError('')
  }

  async function saveRate(dayId) {
    const val = parseFloat(editRate)
    if (isNaN(val) || val <= 0) { setRateError('Enter a valid rate > 0'); return }
    setRateSaving(true)
    setRateError('')
    try {
      await timesheetsAPI.updateDayRate(dayId, val)
      setEditingDayId(null)
      loadDays()
      onRefresh && onRefresh()
    } catch (err) {
      setRateError(err.response?.data?.detail || 'Failed to save rate')
    } finally {
      setRateSaving(false)
    }
  }

  async function handleApprove() {
    setLoading(true); setError('')
    try { await timesheetsAPI.approve(ts.id); onAction() }
    catch (err) { setError(err.response?.data?.detail || 'Approve failed') }
    finally { setLoading(false) }
  }

  async function handleReject(e) {
    e.preventDefault()
    if (!rejectReason.trim()) return
    setLoading(true); setError('')
    try { await timesheetsAPI.reject(ts.id, rejectReason); onAction() }
    catch (err) { setError(err.response?.data?.detail || 'Reject failed') }
    finally { setLoading(false) }
  }

  const defaultRate = parseFloat(ts.hourly_rate)

  // Compute totals from live days state so they update immediately after a rate edit
  const activeDays = days.filter(d => d.status !== 'rejected')
  const computedTotalHours = activeDays.reduce((sum, d) => sum + parseFloat(d.hours), 0)
  const computedAmount = activeDays.reduce((sum, d) => {
    const rate = d.hourly_rate != null ? parseFloat(d.hourly_rate) : defaultRate
    return sum + parseFloat(d.hours) * rate
  }, 0)
  // Fall back to ts values while days are still loading
  const displayTotalHours = days.length > 0 ? computedTotalHours : parseFloat(ts.total_hours)
  const displayAmount = days.length > 0 ? computedAmount : parseFloat(ts.amount)

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)', zIndex: 200 }} />
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 400, maxWidth: '95vw',
        background: '#fff', boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
        zIndex: 201, overflowY: 'auto', padding: 24,
        display: 'flex', flexDirection: 'column', gap: 20,
      }}>
        <div className="row-between">
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>Timesheet Detail</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        {/* Contractor summary */}
        <div style={{ background: '#f9fafb', borderRadius: 8, padding: '14px 16px' }}>
          <div style={{ fontWeight: 600, fontSize: 15 }}>{ts.contractor_name}</div>
          <div className="text-sm text-muted" style={{ marginTop: 2 }}>{ts.outlet}</div>
          <div className="text-sm text-muted" style={{ marginTop: 2 }}>
            {months[ts.month - 1]} {ts.year}
            {ts.sequence > 1 && <span className="badge badge-blue" style={{ marginLeft: 6 }}>Submission #{ts.sequence}</span>}
            {' · '}Default rate: RM {defaultRate.toFixed(2)}/hr
          </div>
        </div>

        {/* Status badges */}
        <div className="row" style={{ gap: 8 }}>
          {statusBadge(ts.status)}
          {statusBadge(ts.sync_status)}
        </div>

        {/* Day-level breakdown table */}
        <div>
          <div className="label" style={{ marginBottom: 8 }}>Days worked</div>
          {days.length === 0 ? (
            <div className="text-muted text-sm">Loading…</div>
          ) : (
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
              {/* Header */}
              <div style={{
                display: 'grid', gridTemplateColumns: '52px 1fr 52px 1fr',
                padding: '6px 10px', background: '#f8fafc',
                borderBottom: '1px solid #e5e7eb',
                fontSize: 11, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.3,
              }}>
                <span>Day</span>
                <span>Outlet</span>
                <span style={{ textAlign: 'right' }}>Hrs</span>
                <span style={{ textAlign: 'right' }}>Rate</span>
              </div>

              {days.map((d, i) => {
                const isEditing = editingDayId === d.id
                const hasCustomRate = d.hourly_rate != null
                const effectiveRate = hasCustomRate ? parseFloat(d.hourly_rate) : defaultRate
                const isRejected = d.status === 'rejected'

                return (
                  <div key={d.id} style={{
                    borderBottom: i < days.length - 1 ? '1px solid #f3f4f6' : 'none',
                    background: isRejected ? '#fef9f9' : '#fff',
                    opacity: isRejected ? 0.6 : 1,
                  }}>
                    {/* Main row */}
                    <div style={{
                      display: 'grid', gridTemplateColumns: '52px 1fr 52px 1fr',
                      padding: '8px 10px', alignItems: 'center',
                    }}>
                      <span style={{ fontSize: 12 }}>
                        <span style={{ fontWeight: 700, color: '#374151' }}>{d.day}</span>
                        <span style={{ color: '#9ca3af', marginLeft: 3 }}>{getDayName(d.day)}</span>
                      </span>
                      <span style={{ fontSize: 12, color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {d.outlet}
                        {isRejected && <span style={{ marginLeft: 4, fontSize: 10, color: '#b91c1c', fontWeight: 600 }}>REJ</span>}
                      </span>
                      <span style={{ fontSize: 12, fontWeight: 600, textAlign: 'right' }}>{parseFloat(d.hours).toFixed(1)}h</span>
                      <div style={{ textAlign: 'right' }}>
                        {!isEditing ? (
                          <span
                            style={{
                              fontSize: 12, fontWeight: hasCustomRate ? 700 : 400,
                              color: hasCustomRate ? 'var(--color-primary)' : '#6b7280',
                              cursor: isAdmin && !isRejected ? 'pointer' : 'default',
                              borderBottom: isAdmin && !isRejected ? '1px dashed #bfdbfe' : 'none',
                              paddingBottom: 1,
                            }}
                            onClick={() => isAdmin && !isRejected && startEditRate(d)}
                            title={isAdmin ? 'Click to edit rate' : ''}
                          >
                            RM {effectiveRate.toFixed(2)}
                            {hasCustomRate && <span style={{ fontSize: 10, marginLeft: 2 }}>★</span>}
                          </span>
                        ) : (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
                            <input
                              type="number" min="0.01" step="0.01"
                              value={editRate}
                              onChange={e => setEditRate(e.target.value)}
                              style={{ width: 64, fontSize: 12, padding: '3px 6px', border: '1px solid var(--color-primary)', borderRadius: 4, textAlign: 'right' }}
                              autoFocus
                              onKeyDown={e => { if (e.key === 'Enter') saveRate(d.id); if (e.key === 'Escape') setEditingDayId(null) }}
                            />
                            <button
                              onClick={() => saveRate(d.id)} disabled={rateSaving}
                              style={{ fontSize: 11, padding: '3px 7px', background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
                            >{rateSaving ? '…' : '✓'}</button>
                            <button
                              onClick={() => setEditingDayId(null)}
                              style={{ fontSize: 11, padding: '3px 7px', background: '#f3f4f6', border: 'none', borderRadius: 4, cursor: 'pointer' }}
                            >✕</button>
                          </div>
                        )}
                      </div>
                    </div>
                    {isEditing && rateError && (
                      <div style={{ padding: '0 10px 6px', fontSize: 11, color: '#b91c1c' }}>{rateError}</div>
                    )}
                  </div>
                )
              })}

              {/* Totals footer */}
              <div style={{ padding: '8px 10px', background: '#f8fafc', borderTop: '2px solid #e5e7eb' }}>
                <div className="row-between" style={{ fontSize: 13 }}>
                  <span style={{ fontWeight: 600 }}>Total</span>
                  <span style={{ fontWeight: 700 }}>{displayTotalHours.toFixed(1)}h</span>
                </div>
                <div className="row-between" style={{ fontSize: 14, marginTop: 4 }}>
                  <span style={{ fontWeight: 600 }}>Amount</span>
                  <span style={{ fontWeight: 700, color: 'var(--color-primary)' }}>RM {displayAmount.toFixed(2)}</span>
                </div>
                {isAdmin && days.some(d => d.hourly_rate != null) && (
                  <div style={{ marginTop: 4, fontSize: 11, color: '#6b7280' }}>★ Custom rate applied on some days</div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Rejection reason */}
        {ts.rejection_reason && (
          <div className="alert alert-error" style={{ fontSize: 13 }}>
            Rejected: {ts.rejection_reason}
          </div>
        )}

        {/* Approve / Reject actions */}
        {ts.status === 'submitted' && (
          <div className="stack" style={{ gap: 10 }}>
            {error && <div className="alert alert-error">{error}</div>}
            {!rejecting ? (
              <div className="row" style={{ gap: 8 }}>
                <button className="btn btn-primary" style={{ flex: 1, justifyContent: 'center' }} onClick={handleApprove} disabled={loading}>
                  {loading ? <span className="spinner" /> : 'Approve'}
                </button>
                <button className="btn btn-sm" style={{ flex: 1, justifyContent: 'center', background: '#fee2e2', color: '#b91c1c' }}
                  onClick={() => setRejecting(true)} disabled={loading}>Reject</button>
              </div>
            ) : (
              <form onSubmit={handleReject} className="stack" style={{ gap: 8 }}>
                <textarea className="input" placeholder="Reason for rejection…" rows={3} required
                  value={rejectReason} onChange={e => setRejectReason(e.target.value)} style={{ resize: 'vertical' }} />
                {error && <div className="alert alert-error">{error}</div>}
                <div className="row" style={{ gap: 8 }}>
                  <button type="button" className="btn btn-ghost" style={{ flex: 1, justifyContent: 'center' }}
                    onClick={() => { setRejecting(false); setRejectReason('') }} disabled={loading}>Cancel</button>
                  <button type="submit" className="btn btn-sm" style={{ flex: 1, justifyContent: 'center', background: '#fee2e2', color: '#b91c1c' }} disabled={loading}>
                    {loading ? <span className="spinner" /> : 'Confirm Reject'}
                  </button>
                </div>
              </form>
            )}
          </div>
        )}

        {/* Audit history — collapsible */}
        {dayLogs.length > 0 && (
          <div>
            <button
              onClick={() => setShowLog(v => !v)}
              style={{ background: 'none', border: 'none', padding: 0, fontSize: 13, fontWeight: 600, color: '#6b7280', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <span>{showLog ? '▾' : '▸'}</span> Audit history ({dayLogs.length} events)
            </button>
            {showLog && (
              <div className="stack" style={{ gap: 8, marginTop: 10 }}>
                {(() => {
                  const byDay = {}
                  for (const log of dayLogs) {
                    if (!byDay[log.day]) byDay[log.day] = []
                    byDay[log.day].push(log)
                  }
                  return Object.entries(byDay)
                    .sort(([a], [b]) => Number(a) - Number(b))
                    .map(([day, logs]) => (
                      <div key={day} style={{ borderLeft: '3px solid #e5e7eb', paddingLeft: 10 }}>
                        <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 4, color: '#374151' }}>Day {day}</div>
                        {logs.map(log => (
                          <div key={log.id} style={{ fontSize: 11, marginBottom: 4, lineHeight: 1.5 }}>
                            <span style={{
                              fontWeight: 600, textTransform: 'uppercase', marginRight: 6,
                              color: log.event === 'rejected' ? '#b91c1c' : log.event === 'resubmitted' ? '#d97706' : '#16a34a',
                            }}>{log.event}</span>
                            {log.hours != null && <span style={{ marginRight: 6 }}>{parseFloat(log.hours).toFixed(1)}h</span>}
                            {log.outlet && <span className="text-muted" style={{ marginRight: 6 }}>{log.outlet}</span>}
                            {log.rejection_reason && <span className="text-muted" style={{ marginRight: 6 }}>"{log.rejection_reason}"</span>}
                            <span className="text-muted">{new Date(log.created_at).toLocaleString('en-MY', { dateStyle: 'short', timeStyle: 'short' })}</span>
                          </div>
                        ))}
                      </div>
                    ))
                })()}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}

// ── Timesheets Tab ─────────────────────────────────────────────────────────────
function TimesheetsTab() {
  const { user } = useAuth()
  const now = new Date()
  const [timesheets, setTimesheets] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(new Set())
  const [approving, setApproving] = useState(false)
  const [result, setResult] = useState(null)
  const [filterMonth, setFilterMonth] = useState(now.getMonth() + 1)
  const [filterYear, setFilterYear] = useState(now.getFullYear())
  const [filterStatus, setFilterStatus] = useState('')
  const [filterSyncStatus, setFilterSyncStatus] = useState('')
  const [selectedTs, setSelectedTs] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { month: filterMonth, year: filterYear }
      if (filterStatus) params.status = filterStatus
      if (filterSyncStatus) params.sync_status = filterSyncStatus
      const res = await timesheetsAPI.list(params)
      setTimesheets(res.data)
      setSelected(new Set())
      // Keep the open panel in sync with the refreshed data
      setSelectedTs(prev => {
        if (!prev) return prev
        return res.data.find(t => t.id === prev.id) || prev
      })
    } finally {
      setLoading(false)
    }
  }, [filterMonth, filterYear, filterStatus, filterSyncStatus])

  useEffect(() => { load() }, [load])

  function toggle(id) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleAll() {
    const eligible = timesheets.filter(canProcessTimesheet).map(t => t.id)
    if (eligible.every(id => selected.has(id))) {
      setSelected(new Set())
    } else {
      setSelected(new Set(eligible))
    }
  }

  async function bulkApprove() {
    if (!selected.size) return
    const total = timesheets.filter(t => selected.has(t.id)).reduce((s, t) => s + parseFloat(t.amount), 0)
    if (!confirm(`Process ${selected.size} timesheet(s) totalling RM ${total.toFixed(2)}? Submitted rows will be approved and all selected rows will sync to Swipey.`)) return

    setApproving(true)
    setResult(null)
    try {
      const res = await timesheetsAPI.bulkApprove(Array.from(selected))
      setResult(res.data)
      load()
    } catch (err) {
      setResult({ error: err.response?.data?.detail || 'Bulk approve failed' })
    } finally {
      setApproving(false)
    }
  }

  const eligibleSelected = timesheets.filter(t => selected.has(t.id) && canProcessTimesheet(t))
  const totalSelected = eligibleSelected.reduce((s, t) => s + parseFloat(t.amount), 0)

  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

  return (
    <div className="container" style={{ padding: '24px 16px' }}>
      <div className="row-between" style={{ marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600 }}>Timesheets</h2>
        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <select className="input" style={{ width: 'auto' }} value={filterMonth} onChange={e => setFilterMonth(Number(e.target.value))}>
            {months.map((m, i) => <option key={i+1} value={i+1}>{m}</option>)}
          </select>
          <select className="input" style={{ width: 'auto' }} value={filterYear} onChange={e => setFilterYear(Number(e.target.value))}>
            {[2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <select className="input" style={{ width: 'auto' }} value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="submitted">Submitted</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
          <select className="input" style={{ width: 'auto' }} value={filterSyncStatus} onChange={e => setFilterSyncStatus(e.target.value)}>
            <option value="">All sync</option>
            <option value="pending">Pending</option>
            <option value="syncing">Syncing</option>
            <option value="synced">Synced</option>
            <option value="failed">Failed</option>
          </select>
          {selected.size > 0 && user?.role === 'admin' && (
            <button className="btn btn-primary btn-sm" onClick={bulkApprove} disabled={approving}>
              {approving ? <span className="spinner" /> : `Process ${selected.size} (RM ${totalSelected.toFixed(2)})`}
            </button>
          )}
        </div>
      </div>

      {result && (
        <div className={`alert ${result.error ? 'alert-error' : 'alert-success'}`} style={{ marginBottom: 16 }}>
          {result.error || `Done: ${result.approved} synced, ${result.failed} failed.`}
        </div>
      )}

      {loading ? (
        <div className="text-center text-muted" style={{ padding: 40 }}><span className="spinner" /></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th><input type="checkbox" onChange={toggleAll} checked={timesheets.filter(canProcessTimesheet).every(t => selected.has(t.id)) && timesheets.some(canProcessTimesheet)} /></th>
                <th>Contractor</th>
                <th>Outlet</th>
                <th>Period</th>
                <th>Hours</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Sync</th>
              </tr>
            </thead>
            <tbody>
              {timesheets.length === 0 && (
                <tr><td colSpan={8} className="text-center text-muted" style={{ padding: 32 }}>No timesheets for this period</td></tr>
              )}
              {timesheets.map(t => (
                <tr key={t.id} onClick={() => setSelectedTs(t)} style={{ cursor: 'pointer' }}>
                  <td onClick={e => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.has(t.id)}
                      onChange={() => toggle(t.id)}
                      disabled={!canProcessTimesheet(t)}
                    />
                  </td>
                  <td style={{ fontWeight: 500 }}>{t.contractor_name}</td>
                  <td>{t.outlet}</td>
                  <td>
                    {months[t.month - 1]} {t.year}
                    {t.sequence > 1 && (
                      <span className="badge badge-blue" style={{ marginLeft: 6 }}>#{t.sequence}</span>
                    )}
                  </td>
                  <td>{parseFloat(t.total_hours).toFixed(1)}h</td>
                  <td style={{ fontWeight: 500 }}>RM {parseFloat(t.amount).toFixed(2)}</td>
                  <td>{statusBadge(t.status)}</td>
                  <td>{statusBadge(t.sync_status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedTs && (
        <TimesheetDetailPanel
          timesheet={selectedTs}
          months={months}
          onClose={() => setSelectedTs(null)}
          onAction={() => { setSelectedTs(null); load() }}
          onRefresh={() => { load() }}
        />
      )}
    </div>
  )
}

// ── Users Tab (admin only) ──────────────────────────────────────────────────────
function AddUserModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'manager' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await usersAPI.create(form)
      onCreated(res.data)
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: 16 }}>
      <div className="card" style={{ width: '100%', maxWidth: 400 }}>
        <div className="row-between" style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>Add User</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={submit} className="stack">
          <div className="form-group">
            <label className="label">Name</label>
            <input className="input" type="text" required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="label">Email</label>
            <input className="input" type="email" required value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="label">Password</label>
            <input className="input" type="password" required minLength={8} value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="label">Role</label>
            <select className="input" value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
              <option value="manager">Site Manager (review &amp; edit hours only)</option>
              <option value="admin">Admin / HR (full access including Swipey sync)</option>
            </select>
          </div>
          {error && <div className="alert alert-error">{error}</div>}
          <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? <span className="spinner" /> : 'Create User'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function UsersTab() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await usersAPI.list()
      setUsers(res.data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function deactivate(userId, name) {
    if (!confirm(`Deactivate ${name}? They will no longer be able to log in.`)) return
    try {
      await usersAPI.deactivate(userId)
      load()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to deactivate user')
    }
  }

  const ROLE_LABEL = { admin: 'Admin / HR', manager: 'Site Manager' }

  return (
    <div className="container" style={{ padding: '24px 16px' }}>
      <div className="row-between" style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600 }}>Users</h2>
        <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(true)}>+ Add User</button>
      </div>

      {showAdd && <AddUserModal onClose={() => setShowAdd(false)} onCreated={() => load()} />}

      {loading ? (
        <div className="text-center text-muted" style={{ padding: 40 }}><span className="spinner" /></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 && (
                <tr><td colSpan={5} className="text-center text-muted" style={{ padding: 32 }}>No users yet</td></tr>
              )}
              {users.map(u => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 500 }}>{u.name}{u.id === currentUser?.user_id && <span className="text-muted text-sm" style={{ marginLeft: 6 }}>(you)</span>}</td>
                  <td className="text-muted">{u.email}</td>
                  <td>
                    <span className={`badge ${u.role === 'admin' ? 'badge-blue' : 'badge-gray'}`}>
                      {ROLE_LABEL[u.role] || u.role}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${u.is_active ? 'badge-green' : 'badge-red'}`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    {u.is_active && u.id !== currentUser?.user_id && (
                      <button className="btn btn-sm" style={{ background: '#f3f4f6', color: '#374151' }}
                        onClick={() => deactivate(u.id, u.name)}>
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────
export default function ManagerDashboard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState('contractors')
  const isAdmin = user?.role === 'admin'

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="page-top">
      <div className="topbar">
        <span className="topbar-title">Ben's Contractor Payments</span>
        <div className="topbar-right">
          <span>{user?.name}</span>
          <button className="btn btn-ghost btn-sm" onClick={handleLogout}>Log out</button>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab ${tab === 'contractors' ? 'active' : ''}`} onClick={() => setTab('contractors')}>Contractors</button>
        <button className={`tab ${tab === 'timesheets' ? 'active' : ''}`} onClick={() => setTab('timesheets')}>Timesheets</button>
        {isAdmin && <button className={`tab ${tab === 'users' ? 'active' : ''}`} onClick={() => setTab('users')}>Users</button>}
      </div>

      {tab === 'contractors' && <ContractorsTab />}
      {tab === 'timesheets' && <TimesheetsTab />}
      {tab === 'users' && isAdmin && <UsersTab />}
    </div>
  )
}
