// Game store — points, streaks, vouchers
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { gameApi } from '../api/index.js'

export const useGameStore = defineStore('game', () => {
  const profile = ref(null)      // ResidentGameProfile
  const householdProfile = ref(null)
  const vouchers = ref([])
  const transactions = ref([])
  const loading = ref(false)

  async function loadProfile(residentId) {
    loading.value = true
    try {
      const res = await gameApi.profile(residentId)
      profile.value = res.data
    } catch (_) {
      // non-critical — silently fail
    } finally {
      loading.value = false
    }
  }

  async function loadHouseholdProfile() {
    try {
      const res = await gameApi.householdProfile()
      householdProfile.value = res.data
    } catch (_) {}
  }

  async function loadVouchers() {
    try {
      const res = await gameApi.vouchers({ is_redeemed: false })
      vouchers.value = res.data
    } catch (_) {}
  }

  async function loadTransactions(residentId) {
    try {
      const res = await gameApi.transactions(residentId, { limit: 10 })
      transactions.value = res.data
    } catch (_) {}
  }

  async function redeemVoucher(voucherId) {
    await gameApi.redeemVoucher(voucherId)
    vouchers.value = vouchers.value.filter((v) => v.id !== voucherId)
  }

  return {
    profile,
    householdProfile,
    vouchers,
    transactions,
    loading,
    loadProfile,
    loadHouseholdProfile,
    loadVouchers,
    loadTransactions,
    redeemVoucher,
  }
})
