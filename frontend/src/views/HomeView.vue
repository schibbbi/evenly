<!-- Home Screen
     Shows: current streak + safes, today's points, alert banner,
     quick "Get tasks" CTA, feed preview (3 entries), Panic Mode button.
-->
<template>
  <AppLayout>
    <!-- Skeleton while loading -->
    <v-skeleton-loader v-if="loading" type="card, list-item-two-line, list-item-two-line" />

    <div v-else>
      <!-- Calendar alert banner -->
      <v-alert
        v-if="calendarAlert"
        :type="alertType"
        variant="tonal"
        class="mb-4"
        density="compact"
        :icon="alertIcon"
      >
        {{ calendarAlert }}
      </v-alert>

      <!-- Greeting + streak card -->
      <v-card variant="tonal" color="primary" rounded="xl" class="mb-4 pa-4">
        <div class="d-flex align-center justify-space-between">
          <div>
            <p class="text-caption text-medium-emphasis mb-1">
              {{ greeting }}, {{ residentStore.activeResident?.display_name || 'there' }}
            </p>
            <div class="d-flex align-center ga-2">
              <v-icon color="secondary" size="28" aria-hidden="true">mdi-fire</v-icon>
              <span class="text-h4 font-weight-bold">{{ gameProfile?.current_streak ?? 0 }}</span>
              <span class="text-body-2 text-medium-emphasis">{{ $t('home.streakDays') }}</span>
            </div>
          </div>
          <div class="text-right">
            <p class="text-caption text-medium-emphasis mb-1">{{ $t('home.todayPoints') }}</p>
            <span class="text-h5 font-weight-bold text-secondary">
              +{{ todayPoints }}
            </span>
          </div>
        </div>

        <!-- Streak safes -->
        <div v-if="(gameProfile?.streak_safes_available ?? 0) > 0" class="mt-3 d-flex align-center ga-1">
          <v-icon size="16" color="secondary" aria-hidden="true">mdi-shield-check</v-icon>
          <span class="text-caption">
            {{ gameProfile.streak_safes_available }} {{ $t('home.streakSafe', gameProfile.streak_safes_available) }}
          </span>
        </div>
      </v-card>

      <!-- Primary CTA -->
      <v-btn
        block
        size="x-large"
        color="primary"
        class="mb-4"
        prepend-icon="mdi-checkbox-marked-circle-outline"
        style="height: 64px; font-size: 1.1rem"
        @click="router.push('/tasks')"
      >
        {{ $t('home.getTasks') }}
      </v-btn>

      <!-- Panic Mode -->
      <v-btn
        block
        variant="outlined"
        color="error"
        class="mb-6"
        prepend-icon="mdi-alert-outline"
        @click="router.push('/panic')"
        aria-label="Activate Panic Mode — for guests or urgent cleaning"
      >
        {{ $t('home.panicMode') }}
      </v-btn>

      <!-- Feed preview -->
      <div class="d-flex align-center justify-space-between mb-3">
        <span class="text-subtitle-2 font-weight-medium">{{ $t('home.recentActivity') }}</span>
        <v-btn
          variant="text"
          size="small"
          density="compact"
          @click="router.push('/feed')"
        >
          {{ $t('home.seeAll') }}
        </v-btn>
      </div>

      <!-- Empty state -->
      <div v-if="feedEntries.length === 0" class="text-center py-6">
        <v-icon size="40" class="text-medium-emphasis mb-2">mdi-history</v-icon>
        <p class="text-body-2 text-medium-emphasis">
          {{ $t('home.emptyFeed') }}
        </p>
      </div>

      <div v-else>
        <v-card
          v-for="entry in feedEntries"
          :key="entry.id"
          variant="outlined"
          rounded="lg"
          class="mb-2 pa-3"
        >
          <div class="d-flex align-center ga-3">
            <ResidentAvatar :resident="residentFor(entry.resident_id)" size="36" />
            <div class="flex-grow-1 overflow-hidden">
              <p class="text-body-2 text-truncate">{{ entry.text }}</p>
              <p class="text-caption text-medium-emphasis">{{ relativeTime(entry.created_at) }}</p>
            </div>
          </div>
        </v-card>
      </div>

      <!-- Error state -->
      <v-alert
        v-if="errorMsg"
        type="error"
        variant="tonal"
        class="mt-4"
        density="compact"
      >
        {{ errorMsg }}
      </v-alert>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useResidentStore } from '../stores/resident.js'
import { useGameStore } from '../stores/game.js'
import { historyApi, calendarApi, householdsApi } from '../api/index.js'
import AppLayout from '../components/layout/AppLayout.vue'
import ResidentAvatar from '../components/shared/ResidentAvatar.vue'

const { t } = useI18n()
const router         = useRouter()
const residentStore  = useResidentStore()
const gameStore      = useGameStore()

const loading     = ref(true)
const errorMsg    = ref('')
const feedEntries = ref([])
const todayPoints = ref(0)
const calendarContext = ref(null)

const gameProfile = computed(() => gameStore.profile)

const calendarAlert = computed(() => {
  if (!calendarContext.value) return null
  const level = calendarContext.value.current_alert_level
  if (level === 'low') return null
  const date = calendarContext.value.event_date
    ? new Date(calendarContext.value.event_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : 'soon'
  if (level === 'high') return t('home.calendarAlertHigh', { date })
  if (level === 'medium') return t('home.calendarAlertMedium', { date })
  return null
})

const alertType = computed(() => {
  const level = calendarContext.value?.current_alert_level
  return level === 'high' ? 'error' : 'warning'
})
const alertIcon = computed(() =>
  calendarContext.value?.current_alert_level === 'high'
    ? 'mdi-alert' : 'mdi-calendar-alert'
)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return t('home.greeting.morning')
  if (h < 18) return t('home.greeting.afternoon')
  return t('home.greeting.evening')
})

function residentFor(id) {
  return residentStore.residents.find((r) => r.id === id) || null
}

function relativeTime(isoStr) {
  if (!isoStr) return ''
  const diff = Date.now() - new Date(isoStr).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (mins < 2)   return t('feed.time.justNow')
  if (mins < 60)  return t('feed.time.minutesAgo', { n: mins })
  if (hours < 24) return t('feed.time.hoursAgo', { n: hours })
  return t('feed.time.daysAgo', { n: days })
}

onMounted(async () => {
  try {
    // Load household + residents if not yet loaded
    if (residentStore.residents.length === 0) {
      const hhRes = await householdsApi.list()
      if (hhRes.data?.length > 0) {
        const hhId = hhRes.data[0].id
        await residentStore.loadResidents(hhId)
      }
    }

    // Check if active resident needs first-login wizard
    const active = residentStore.activeResident
    if (active && active.setup_complete === false) {
      // Will be caught by router guard — navigate away
      return
    }

    // Load game profile, feed, calendar context in parallel
    const [feedRes] = await Promise.allSettled([
      historyApi.feed(),
    ])

    if (feedRes.status === 'fulfilled') {
      feedEntries.value = (feedRes.value.data || []).slice(0, 3)
    }

    if (residentStore.activeResidentId) {
      await gameStore.loadProfile(residentStore.activeResidentId)
      // Calculate today's points from transactions
      await gameStore.loadTransactions(residentStore.activeResidentId)
      const today = new Date().toDateString()
      todayPoints.value = gameStore.transactions
        .filter((t) => new Date(t.created_at).toDateString() === today && t.amount > 0)
        .reduce((sum, t) => sum + t.amount, 0)
    }

    // Calendar context
    try {
      const ctxRes = await calendarApi.status()
      calendarContext.value = ctxRes.data?.context || null
    } catch (_) {}

  } catch (e) {
    errorMsg.value = e.userMessage || t('errors.serverError')
  } finally {
    loading.value = false
  }
})
</script>
