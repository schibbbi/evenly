// Session store — daily task session state
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sessionsApi, assignmentsApi } from '../api/index.js'

export const useSessionStore = defineStore('session', () => {
  const currentSession = ref(null)    // active DailySession
  const suggestions = ref([])         // TaskSuggestionResponse[]
  const activeAssignment = ref(null)  // currently accepted task
  const completionResult = ref(null)  // last completion response (points, streak, etc.)
  const loading = ref(false)
  const error = ref(null)
  const panicPrompt = ref(null)       // non-null when calendar alert = panic

  async function startSession(residentId, energyLevel, availableMinutes) {
    loading.value = true
    error.value = null
    try {
      const res = await sessionsApi.create({
        resident_id: residentId,
        energy_level: energyLevel,
        available_minutes: availableMinutes,
      })
      currentSession.value = res.data
      suggestions.value = res.data.suggestions || []
      // Check for panic prompt on any suggestion
      panicPrompt.value = suggestions.value.find((s) => s.panic_prompt)?.panic_prompt || null
    } catch (e) {
      error.value = e.userMessage
    } finally {
      loading.value = false
    }
  }

  async function reroll() {
    if (!currentSession.value) return
    loading.value = true
    try {
      const res = await sessionsApi.reroll(currentSession.value.session_id)
      currentSession.value = res.data
      suggestions.value = res.data.suggestions || []
      panicPrompt.value = suggestions.value.find((s) => s.panic_prompt)?.panic_prompt || null
    } catch (e) {
      error.value = e.userMessage
    } finally {
      loading.value = false
    }
  }

  async function acceptTask(assignmentId) {
    try {
      const res = await assignmentsApi.accept(assignmentId)
      activeAssignment.value = res.data
    } catch (e) {
      error.value = e.userMessage
    }
  }

  async function completeTask(assignmentId) {
    loading.value = true
    try {
      const res = await assignmentsApi.complete(assignmentId)
      completionResult.value = res.data
      activeAssignment.value = null
      // Remove from suggestions list
      suggestions.value = suggestions.value.filter((s) => s.assignment_id !== assignmentId)
    } catch (e) {
      error.value = e.userMessage
    } finally {
      loading.value = false
    }
  }

  async function skipTask(assignmentId) {
    try {
      await assignmentsApi.skip(assignmentId)
      suggestions.value = suggestions.value.filter((s) => s.assignment_id !== assignmentId)
    } catch (e) {
      error.value = e.userMessage
    }
  }

  function clearSession() {
    currentSession.value = null
    suggestions.value = []
    activeAssignment.value = null
    completionResult.value = null
    panicPrompt.value = null
    error.value = null
  }

  function clearCompletion() {
    completionResult.value = null
  }

  return {
    currentSession,
    suggestions,
    activeAssignment,
    completionResult,
    panicPrompt,
    loading,
    error,
    startSession,
    reroll,
    acceptTask,
    completeTask,
    skipTask,
    clearSession,
    clearCompletion,
  }
})
