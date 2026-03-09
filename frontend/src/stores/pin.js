// PIN store — holds the current PIN in memory only (never persisted)
// PIN is cleared on page reload or after 30 minutes of inactivity.
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '../api/index.js'

const PIN_TTL_MS = 30 * 60 * 1000 // 30 minutes

export const usePinStore = defineStore('pin', () => {
  const currentPin = ref(null)      // PIN string, in memory only
  const pinResidentId = ref(null)   // which resident this PIN belongs to
  const pinExpiresAt = ref(null)
  const verifying = ref(false)
  const error = ref(null)

  const isValid = () => {
    if (!currentPin.value || !pinExpiresAt.value) return false
    return Date.now() < pinExpiresAt.value
  }

  function setPin(residentId, pin) {
    currentPin.value = pin
    pinResidentId.value = residentId
    pinExpiresAt.value = Date.now() + PIN_TTL_MS
  }

  async function verifyAndStore(residentId, pin) {
    verifying.value = true
    error.value = null
    try {
      await authApi.verifyPin(residentId, pin)
      setPin(residentId, pin)
      return true
    } catch (e) {
      error.value = e.userMessage || 'Incorrect PIN.'
      return false
    } finally {
      verifying.value = false
    }
  }

  function clearPin() {
    currentPin.value = null
    pinResidentId.value = null
    pinExpiresAt.value = null
  }

  // Return the current valid PIN header value, or null
  function getPinForResident(residentId) {
    if (isValid() && pinResidentId.value === residentId) {
      return currentPin.value
    }
    return null
  }

  return {
    currentPin,
    pinResidentId,
    verifying,
    error,
    isValid,
    setPin,
    verifyAndStore,
    clearPin,
    getPinForResident,
  }
})
