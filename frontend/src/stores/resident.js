// Resident store — tracks active resident and all household residents
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { residentsApi } from '../api/index.js'

export const useResidentStore = defineStore('resident', () => {
  const residents = ref([])
  const activeResidentId = ref(parseInt(localStorage.getItem('activeResidentId')) || null)
  const loading = ref(false)

  const activeResident = computed(() =>
    residents.value.find((r) => r.id === activeResidentId.value) || null
  )

  const isAdmin = computed(() => activeResident.value?.role === 'admin')
  const isEdit = computed(() =>
    ['admin', 'edit'].includes(activeResident.value?.role)
  )

  async function loadResidents(householdId) {
    loading.value = true
    try {
      const res = await residentsApi.list(householdId)
      residents.value = res.data
      // Auto-select first resident if none selected
      if (!activeResidentId.value && residents.value.length > 0) {
        setActiveResident(residents.value[0].id)
      }
    } finally {
      loading.value = false
    }
  }

  function setActiveResident(id) {
    activeResidentId.value = id
    localStorage.setItem('activeResidentId', id)
  }

  function $reset() {
    residents.value = []
    activeResidentId.value = null
    localStorage.removeItem('activeResidentId')
  }

  return {
    residents,
    activeResidentId,
    activeResident,
    isAdmin,
    isEdit,
    loading,
    loadResidents,
    setActiveResident,
    $reset,
  }
})
