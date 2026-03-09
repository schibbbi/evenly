<!-- Task Suggestions Screen
     Shows 2–3 task cards. Each card: Accept / Skip actions.
     Reroll button below cards. Panic prompt banner if active.
-->
<template>
  <AppLayout>
    <!-- Panic prompt banner -->
    <v-alert
      v-if="sessionStore.panicPrompt"
      type="error"
      variant="tonal"
      class="mb-4"
      icon="mdi-alert"
    >
      {{ sessionStore.panicPrompt }}
      <template #append>
        <v-btn variant="text" size="small" @click="router.push('/panic')">
          {{ $t('session.suggestions.panicMode') }}
        </v-btn>
      </template>
    </v-alert>

    <h1 class="text-h5 font-weight-bold mb-1">{{ $t('session.suggestions.title') }}</h1>
    <p class="text-body-2 text-medium-emphasis mb-4">
      {{ $t('session.suggestions.subtitle') }}
    </p>

    <!-- Loading state -->
    <div v-if="sessionStore.loading">
      <v-skeleton-loader v-for="i in 3" :key="i" type="card" class="mb-3" />
    </div>

    <!-- Empty state -->
    <div v-else-if="sessionStore.suggestions.length === 0" class="text-center py-10">
      <v-icon size="48" class="text-medium-emphasis mb-3">mdi-checkbox-marked-circle-outline</v-icon>
      <p class="text-body-1 font-weight-medium mb-1">{{ $t('session.suggestions.allDoneTitle') }}</p>
      <p class="text-body-2 text-medium-emphasis mb-4">{{ $t('session.suggestions.allDoneSub') }}</p>
      <v-btn color="primary" @click="router.push('/')">{{ $t('session.suggestions.backToHome') }}</v-btn>
    </div>

    <!-- Task cards -->
    <div v-else>
      <v-card
        v-for="task in sessionStore.suggestions"
        :key="task.assignment_id"
        variant="outlined"
        rounded="xl"
        class="task-card mb-3 pa-4"
      >
        <!-- Badges row -->
        <div class="d-flex flex-wrap ga-1 mb-2">
          <v-chip
            v-if="task.is_overdue"
            color="error"
            size="x-small"
            variant="flat"
            prepend-icon="mdi-clock-alert-outline"
          >
            {{ $t('session.suggestions.badge.overdue') }}
          </v-chip>
          <v-chip
            v-if="task.is_unpopular"
            color="warning"
            size="x-small"
            variant="flat"
            prepend-icon="mdi-thumb-down-outline"
          >
            {{ $t('session.suggestions.badge.dislikedByAll') }}
          </v-chip>
          <v-chip
            v-if="task.is_robot_variant"
            color="info"
            size="x-small"
            variant="tonal"
            prepend-icon="mdi-robot-vacuum"
          >
            {{ $t('session.suggestions.badge.robot') }}
          </v-chip>
        </div>

        <!-- Task name -->
        <p class="text-body-1 font-weight-semibold mb-1">{{ task.task_name }}</p>

        <!-- Room + duration + energy -->
        <div class="d-flex align-center flex-wrap ga-3 mb-4">
          <div class="d-flex align-center ga-1">
            <v-icon size="16" class="text-medium-emphasis" aria-hidden="true">mdi-door-open</v-icon>
            <span class="text-body-2 text-medium-emphasis">{{ task.room_name || $t('session.suggestions.room') }}</span>
          </div>
          <div class="d-flex align-center ga-1">
            <v-icon size="16" class="text-medium-emphasis" aria-hidden="true">mdi-timer-outline</v-icon>
            <span class="text-body-2 text-medium-emphasis">~{{ task.estimated_minutes || 15 }} min</span>
          </div>
          <div class="d-flex align-center ga-1">
            <v-icon
              size="16"
              :color="energyColor(task.energy_required)"
              aria-hidden="true"
            >
              {{ energyIcon(task.energy_required) }}
            </v-icon>
            <span class="text-body-2 text-medium-emphasis">{{ task.energy_required }}</span>
          </div>
        </div>

        <!-- Actions -->
        <div class="d-flex ga-2">
          <v-btn
            color="primary"
            variant="flat"
            class="flex-grow-1"
            min-height="48"
            :loading="accepting === task.assignment_id"
            @click="accept(task)"
          >
            {{ $t('session.suggestions.accept') }}
          </v-btn>
          <v-btn
            variant="text"
            min-height="48"
            :loading="skipping === task.assignment_id"
            @click="skip(task)"
            :aria-label="$t('session.suggestions.skipAriaLabel')"
          >
            {{ $t('session.suggestions.skip') }}
          </v-btn>
        </div>
      </v-card>

      <!-- Reroll -->
      <div class="text-center mt-4">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-refresh"
          :loading="sessionStore.loading"
          @click="reroll"
        >
          {{ $t('session.suggestions.reroll') }}
        </v-btn>
        <p
          v-if="sessionStore.currentSession?.reroll_count > 0"
          class="text-caption text-medium-emphasis mt-2"
        >
          <span v-if="sessionStore.currentSession.reroll_count >= 1">
            {{ $t('session.suggestions.rerollPenalty', { n: sessionStore.currentSession.reroll_count * 2 }) }}
          </span>
        </p>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '../../stores/session.js'
import AppLayout from '../../components/layout/AppLayout.vue'

const { t }        = useI18n()
const router       = useRouter()
const sessionStore = useSessionStore()

const accepting = ref(null)
const skipping  = ref(null)

function energyColor(level) {
  return { high: 'success', medium: 'warning', low: 'info' }[level] || 'primary'
}
function energyIcon(level) {
  return { high: 'mdi-lightning-bolt', medium: 'mdi-battery-60', low: 'mdi-leaf' }[level] || 'mdi-circle'
}

async function accept(task) {
  accepting.value = task.assignment_id
  await sessionStore.acceptTask(task.assignment_id)
  accepting.value = null
  router.push('/tasks/active')
}

async function skip(task) {
  skipping.value = task.assignment_id
  await sessionStore.skipTask(task.assignment_id)
  skipping.value = null
}

async function reroll() {
  await sessionStore.reroll()
}
</script>

<style scoped>
.task-card {
  min-height: 140px;
  transition: box-shadow 0.15s ease;
}
</style>
