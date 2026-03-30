import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Auth ───────────────────────────────────────────────────────────────────────
export const authAPI = {
  login: (email, password) => api.post('/auth/login', { email, password }),
}

// ── Contractors ────────────────────────────────────────────────────────────────
export const contractorsAPI = {
  list: (params) => api.get('/contractors', { params }),
  create: (data) => api.post('/contractors', data),
  get: (id) => api.get(`/contractors/${id}`),
  update: (id, data) => api.patch(`/contractors/${id}`, data),
  deactivate: (id) => api.delete(`/contractors/${id}/deactivate`),

  // Contractor self-service (no auth)
  getByToken: (token) => api.get(`/contractors/register/${token}`),
  parseQR: (token, file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/contractors/register/${token}/parse-qr`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  saveQR: (token, qrData) => api.post(`/contractors/register/${token}/save-qr`, qrData),
  confirm: (token, data) => api.post(`/contractors/register/${token}/confirm`, data),
  getQRImage: (id) => api.get(`/contractors/${id}/qr-image`),
}

// ── Timesheets ─────────────────────────────────────────────────────────────────
export const timesheetsAPI = {
  list: (params) => api.get('/timesheets', { params }),
  submit: (token, data) => api.post(`/timesheets/submit/${token}`, data),
  history: (token) => api.get(`/timesheets/history/${token}`),
  submissionHistory: (token) => api.get(`/timesheets/submission-history/${token}`),
  getSubmittedDays: (token, year, month) => api.get(`/timesheets/submitted-days/${token}`, { params: { year, month } }),
  getDayLogs: (id) => api.get(`/timesheets/${id}/day-logs`),
  getDays: (id) => api.get(`/timesheets/${id}/days`),
  updateDayRate: (dayId, rate) => api.patch(`/timesheets/days/${dayId}`, { hourly_rate: rate }),
  update: (id, data) => api.patch(`/timesheets/${id}`, data),
  approve: (id) => api.post(`/timesheets/${id}/approve`),
  reject: (id, reason) => api.post(`/timesheets/${id}/reject`, { rejection_reason: reason }),
  bulkApprove: (ids) => api.post('/timesheets/bulk-approve', { timesheet_ids: ids }),
}

// ── Notes ──────────────────────────────────────────────────────────────────────
export const notesAPI = {
  list: (contractorId) => api.get(`/notes/contractor/${contractorId}`),
  listExternal: (contractorId) => api.get(`/notes/contractor/${contractorId}/external`),
  listExternalByToken: (token) => api.get(`/notes/token/${token}/external`),
  create: (data) => api.post('/notes', data),
  update: (id, data) => api.patch(`/notes/${id}`, data),
  delete: (id) => api.delete(`/notes/${id}`),
}

export const usersAPI = {
  list: () => api.get('/auth/users'),
  create: (data) => api.post('/auth/users', data),
  deactivate: (id) => api.delete(`/auth/users/${id}/deactivate`),
}

export default api
