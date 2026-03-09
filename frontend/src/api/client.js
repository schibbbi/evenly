// Axios API client
// Base URL is set via VITE_API_URL — never hardcoded.
// Resident ID is injected from localStorage on each request.
// PIN is injected per-request by the calling code when an action requires it.

import axios from 'axios'
import i18n from '../plugins/i18n.js'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
  timeout: 10000,
})

// Request interceptor — inject active resident ID from localStorage
api.interceptors.request.use((config) => {
  const residentId = localStorage.getItem('activeResidentId')
  if (residentId) {
    config.headers['X-Resident-Id'] = residentId
  }
  return config
})

// Response interceptor — surface friendly error messages (translated)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const t = i18n.global.t
    if (!error.response) {
      error.userMessage = t('errors.serverUnreachable')
    } else if (error.response.status === 403) {
      error.userMessage = t('errors.accessDenied')
    } else if (error.response.status === 404) {
      error.userMessage = t('errors.notFound')
    } else if (error.response.status === 422) {
      const detail = error.response.data?.detail
      error.userMessage = typeof detail === 'string' ? detail : t('errors.invalidInput')
    } else {
      error.userMessage = error.response.data?.detail || t('errors.somethingWrong')
    }
    return Promise.reject(error)
  }
)

// Helper: make a request with a PIN header (for role-protected actions)
export function withPin(pin) {
  return {
    headers: { 'X-Pin': pin },
  }
}

export default api
