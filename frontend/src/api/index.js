// Evenly API service — all backend calls defined here
// Separates HTTP concerns from component logic.

import api, { withPin } from './client.js'

// ── Households ────────────────────────────────────────────────
export const householdsApi = {
  list: () => api.get('/households'),
  create: (data) => api.post('/households', data),
  get: (id) => api.get(`/households/${id}`),
  update: (id, data, pin) => api.put(`/households/${id}`, data, withPin(pin)),
}

// ── Residents ─────────────────────────────────────────────────
export const residentsApi = {
  // List residents — optional filter by householdId via query param
  list: (householdId) => api.get('/residents', { params: { household_id: householdId } }),
  // Bootstrap: create first admin resident, no auth required (only works when household has 0 residents)
  bootstrap: (data) => api.post('/residents/bootstrap', data),
  // Create resident — requires admin PIN
  create: (data, pin) => api.post('/residents', data, withPin(pin)),
  get: (id) => api.get(`/residents/${id}`),
  update: (id, data, pin) => api.put(`/residents/${id}`, data, withPin(pin)),
  delete: (id, pin) => api.delete(`/residents/${id}`, withPin(pin)),
  getPreferences: (id) => api.get(`/residents/${id}/preferences`),
  setPreference: (id, data, pin) => api.post(`/residents/${id}/preferences`, data, withPin(pin)),
}

// ── Auth / PIN ────────────────────────────────────────────────
export const authApi = {
  verifyPin: (residentId, pin) =>
    api.post('/auth/verify-pin', { resident_id: residentId, pin }),
  changePin: (residentId, currentPin, newPin) =>
    api.post('/auth/change-pin', { resident_id: residentId, current_pin: currentPin, new_pin: newPin }, withPin(currentPin)),
  resetPin: (residentId, newPin, pin) =>
    api.post('/auth/reset-pin', { resident_id: residentId, new_pin: newPin }, withPin(pin)),
}

// ── Rooms ─────────────────────────────────────────────────────
// Backend: POST /rooms with { household_id, name, room_type, is_active } in body
export const roomsApi = {
  list: (householdId) => api.get('/rooms', { params: { household_id: householdId } }),
  create: (householdId, data, pin) => api.post('/rooms', { household_id: householdId, ...data }, withPin(pin)),
  update: (id, data, pin) => api.put(`/rooms/${id}`, data, withPin(pin)),
  delete: (id, pin) => api.delete(`/rooms/${id}`, withPin(pin)),
}

// ── Devices ───────────────────────────────────────────────────
// Backend: POST /devices with { household_id, ... } in body
export const devicesApi = {
  list: (householdId) => api.get('/devices', { params: { household_id: householdId } }),
  create: (householdId, data, pin) => api.post('/devices', { household_id: householdId, ...data }, withPin(pin)),
  update: (id, data, pin) => api.put(`/devices/${id}`, data, withPin(pin)),
  delete: (id, pin) => api.delete(`/devices/${id}`, withPin(pin)),
}

// ── Catalog ───────────────────────────────────────────────────
export const catalogApi = {
  generate: (householdId, pin) =>
    api.post('/catalog/generate', {}, { ...withPin(pin), params: { household_id: householdId } }),
  list: (params) => api.get('/catalog', { params }),
  get: (id) => api.get(`/catalog/${id}`),
  update: (id, data, pin) => api.put(`/catalog/${id}`, data, withPin(pin)),
  export: () => api.get('/catalog/export'),
}

// ── Sessions ──────────────────────────────────────────────────
export const sessionsApi = {
  create: (data) => api.post('/sessions', data),
  getSuggestions: (sessionId) => api.get(`/sessions/${sessionId}/suggestions`),
  reroll: (sessionId) => api.post(`/sessions/${sessionId}/reroll`),
}

// ── Assignments ───────────────────────────────────────────────
export const assignmentsApi = {
  accept: (id) => api.post(`/assignments/${id}/accept`),
  complete: (id) => api.post(`/assignments/${id}/complete`),
  skip: (id) => api.post(`/assignments/${id}/skip`),
  delegate: (id, toResidentId, pin) =>
    api.post(`/assignments/${id}/delegate`, { to_resident_id: toResidentId }, withPin(pin)),
}

// ── History ───────────────────────────────────────────────────
export const historyApi = {
  feed: () => api.get('/feed'),
  history: (params) => api.get('/history', { params }),
  residentStats: (id) => api.get(`/residents/${id}/stats`),
  householdStats: () => api.get('/household/stats'),
  scoringProfile: (id) => api.get(`/residents/${id}/scoring-profile`),
}

// ── Gamification ──────────────────────────────────────────────
export const gameApi = {
  profile: (id) => api.get(`/residents/${id}/game-profile`),
  transactions: (id, params) => api.get(`/residents/${id}/transactions`, { params }),
  householdProfile: () => api.get('/household/game-profile'),
  vouchers: (params) => api.get('/vouchers', { params }),
  redeemVoucher: (id) => api.post(`/vouchers/${id}/redeem`),
}

// ── Panic ─────────────────────────────────────────────────────
export const panicApi = {
  activate: (data) => api.post('/panic', data),
  get: (id) => api.get(`/panic/${id}`),
  complete: (id) => api.post(`/panic/${id}/complete`),
}

// ── Calendar ──────────────────────────────────────────────────
export const calendarApi = {
  status: () => api.get('/calendar/status'),
  sync: () => api.post('/calendar/sync'),
  events: () => api.get('/calendar/events'),
  updateConfig: (data, pin) => api.put('/calendar/config', data, withPin(pin)),
}
