import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { contractorsAPI } from '../services/api'

// ── Step dots ──────────────────────────────────────────────────────────────────
function Steps({ current, total }) {
  return (
    <div className="steps">
      {Array.from({ length: total }, (_, i) => (
        <div key={i} className={`step-dot ${i < current ? 'done' : i === current ? 'active' : ''}`} />
      ))}
    </div>
  )
}

export default function ContractorRegister() {
  const { token } = useParams()
  const [step, setStep] = useState(0)
  const [contractor, setContractor] = useState(null)
  const [qrResult, setQrResult] = useState(null)
  const [qrIsExisting, setQrIsExisting] = useState(false)
  const [icNumber, setIcNumber] = useState('')
  const [nameOverride, setNameOverride] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef()

  useEffect(() => {
    contractorsAPI.getByToken(token)
      .then(res => {
        setContractor(res.data)
        if (res.data.bank_name && res.data.account_number) {
          setQrResult({
            bank_name: res.data.bank_name,
            account_number: res.data.account_number,
            payee_name: '',
            acquirer_id: '',
            is_duitnow: true,
          })
          setStep(1)
          setQrIsExisting(true)
        }
      })
      .catch(() => setError('This registration link is invalid or has expired.'))
  }, [token])

  async function handleFile(file) {
    if (!file) return
    setError('')
    setLoading(true)
    setQrIsExisting(false)
    try {
      const res = await contractorsAPI.parseQR(token, file)
      setQrResult(res.data)
      // Save QR data to contractor record
      await contractorsAPI.saveQR(token, res.data)
      setStep(1)
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not read QR code. Please try a clearer image.')
    } finally {
      setLoading(false)
    }
  }

  async function handleConfirm(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = { ic_number: icNumber }
      if (nameOverride) data.name = nameOverride
      await contractorsAPI.confirm(token, data)
      setDone(true)
    } catch (err) {
      const detail = err.response?.data?.detail
      const msg = Array.isArray(detail)
        ? detail.map(d => d.msg).join(', ')
        : (typeof detail === 'string' ? detail : 'Registration failed. Please try again.')
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  if (error && !contractor) {
    return (
      <div className="page">
        <div className="card card-sm text-center stack" style={{ gap: 12 }}>
          <div style={{ fontSize: 32 }}>⚠️</div>
          <h2 style={{ fontSize: 16 }}>Link Error</h2>
          <p className="text-muted">{error}</p>
        </div>
      </div>
    )
  }

  if (done) {
    return (
      <div className="page">
        <div className="card card-sm text-center stack" style={{ gap: 16 }}>
          <div style={{ fontSize: 48 }}>✅</div>
          <h2 style={{ fontSize: 18, fontWeight: 600 }}>Registration Complete</h2>
          <p className="text-muted">Your payment details have been saved successfully.</p>
          <div style={{ background: '#f5f5f5', borderRadius: 8, padding: '12px 16px', textAlign: 'left' }}>
            <div className="text-sm text-muted">Bank</div>
            <div style={{ fontWeight: 600 }}>{qrResult?.bank_name}</div>
            <div className="text-sm text-muted" style={{ marginTop: 8 }}>Account</div>
            <div style={{ fontWeight: 600 }}>···{qrResult?.account_number?.slice(-4)}</div>
          </div>
          <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: 16 }}>
            <p className="text-sm text-muted" style={{ marginBottom: 12 }}>
              You can now submit your timesheet for this month.
            </p>
            <a
              href={`/timesheet/${token}`}
              className="btn btn-primary"
              style={{ display: 'flex', justifyContent: 'center', textDecoration: 'none' }}
            >
              Submit Timesheet →
            </a>
          </div>
        </div>
      </div>
    )
  }

  if (!contractor) {
    return <div className="page"><span className="spinner" /></div>
  }

  return (
    <div className="page">
      <div className="card card-sm">
        <Steps current={step} total={3} />

        {step === 0 && (
          <div className="stack">
            <div>
              <h2 style={{ fontSize: 17, fontWeight: 600 }}>Hi, {contractor.name}</h2>
              <p className="text-muted text-sm" style={{ marginTop: 4 }}>Upload your DuitNow QR code to register your payment details.</p>
            </div>

            <div
              className={`upload-zone ${dragging ? 'drag-over' : ''}`}
              onClick={() => fileRef.current?.click()}
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
            >
              <input ref={fileRef} type="file" accept="image/*" onChange={e => handleFile(e.target.files[0])} />
              <div style={{ fontSize: 32, marginBottom: 10 }}>📷</div>
              <div style={{ fontWeight: 500 }}>Tap to upload QR image</div>
              <div className="text-muted text-sm" style={{ marginTop: 4 }}>PNG, JPG or screenshot</div>
            </div>

            {loading && <div className="text-center"><span className="spinner" /></div>}
            {error && <div className="alert alert-error">{error}</div>}
          </div>
        )}

        {step === 1 && qrResult && (
          <div className="stack">
            <div>
              <h2 style={{ fontSize: 17, fontWeight: 600 }}>Verify Payment Details</h2>
              <p className="text-muted text-sm" style={{ marginTop: 4 }}>Confirm these details match your payment account.</p>
            </div>

            {qrIsExisting && (
              <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 6, padding: '8px 12px', fontSize: 13, color: '#1d4ed8' }}>
                Payment details on file from a previous registration.
              </div>
            )}

            <div
              className="stack"
              style={{ background: '#f9fafb', border: '1px solid #e0e0e0', borderRadius: 8, padding: '16px', gap: 12 }}
            >
              <div>
                <div className="text-sm text-muted">Bank / Wallet</div>
                <div style={{ fontWeight: 600, marginTop: 2 }}>{qrResult.bank_name}</div>
              </div>
              <div>
                <div className="text-sm text-muted">Account Number</div>
                <div style={{ fontWeight: 600, marginTop: 2 }}>{qrResult.account_number}</div>
              </div>
              {qrResult.payee_name && (
                <div>
                  <div className="text-sm text-muted">Name on QR</div>
                  <div style={{ fontWeight: 600, marginTop: 2 }}>{qrResult.payee_name}</div>
                </div>
              )}
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="row" style={{ gap: 8 }}>
              <button className="btn btn-ghost" style={{ flex: 1, justifyContent: 'center' }}
                onClick={() => { setStep(0); setQrResult(null); setQrIsExisting(false); setError('') }}>
                Try Again
              </button>
              <button className="btn btn-primary" style={{ flex: 1, justifyContent: 'center' }}
                onClick={() => setStep(2)}>
                Looks Correct →
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <form onSubmit={handleConfirm} className="stack">
            <div>
              <h2 style={{ fontSize: 17, fontWeight: 600 }}>Confirm Identity</h2>
              <p className="text-muted text-sm" style={{ marginTop: 4 }}>Enter your IC number to complete registration.</p>
            </div>

            <div className="form-group">
              <label className="label">IC Number</label>
              <input
                className="input"
                type="text"
                placeholder="e.g. 901231-14-1234"
                value={icNumber}
                onChange={e => setIcNumber(e.target.value)}
                required
                pattern="\d{6}-\d{2}-\d{4}|\d{12}"
                title="Format: 901231-14-1234 or 12 digits"
              />
            </div>

            <div className="form-group">
              <label className="label">Name correction <span className="text-muted">(optional)</span></label>
              <input
                className="input"
                type="text"
                placeholder={contractor.name}
                value={nameOverride}
                onChange={e => setNameOverride(e.target.value)}
              />
              <span className="text-muted text-sm">Leave blank to keep: {contractor.name}</span>
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="row" style={{ gap: 8 }}>
              <button type="button" className="btn btn-ghost" style={{ flex: 1, justifyContent: 'center' }}
                onClick={() => setStep(1)}>
                ← Back
              </button>
              <button type="submit" className="btn btn-primary" style={{ flex: 1, justifyContent: 'center' }} disabled={loading}>
                {loading ? <span className="spinner" /> : 'Complete Registration'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
