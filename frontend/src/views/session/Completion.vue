<!-- Completion Screen
     Shows points awarded (animated), streak status, safes earned, voucher notification.
     CTAs: "Get another task" or "Done for today".
-->
<template>
  <AppLayout>
    <div class="text-center py-4">
      <!-- Success icon -->
      <v-icon size="72" color="success" class="mb-4" aria-hidden="true">
        mdi-check-circle
      </v-icon>

      <h1 class="text-h5 font-weight-bold mb-1">{{ $t('session.completion.title') }}</h1>
      <p class="text-body-2 text-medium-emphasis mb-6">{{ $t('session.completion.subtitle') }}</p>

      <!-- Points card -->
      <v-card variant="tonal" color="secondary" rounded="xl" class="pa-5 mb-4 mx-auto" max-width="300">
        <p class="text-body-2 text-medium-emphasis mb-1">{{ $t('session.completion.pointsEarned') }}</p>
        <div
          class="text-h2 font-weight-bold"
          style="font-variant-numeric: tabular-nums"
          aria-live="polite"
          :aria-label="`${displayedPoints} points earned`"
        >
          +{{ displayedPoints }}
        </div>
      </v-card>

      <!-- Streak info -->
      <v-card
        v-if="result"
        variant="outlined"
        rounded="xl"
        class="pa-4 mb-4 mx-auto text-left"
        max-width="300"
      >
        <div class="d-flex align-center ga-3 mb-2">
          <v-icon color="secondary" aria-hidden="true">mdi-fire</v-icon>
          <div>
            <p class="text-body-2 font-weight-medium">
              {{ streakLabel }}
            </p>
            <p class="text-caption text-medium-emphasis">{{ streakSub }}</p>
          </div>
        </div>

        <!-- Safes earned -->
        <div v-if="result.streak_safe_earned" class="d-flex align-center ga-2 mt-2">
          <v-icon size="18" color="secondary" aria-hidden="true">mdi-shield-check</v-icon>
          <span class="text-body-2">{{ $t('session.completion.streakSafeEarned') }}</span>
        </div>
      </v-card>

      <!-- Voucher earned -->
      <v-alert
        v-if="result?.voucher_earned"
        type="success"
        variant="tonal"
        class="mb-4 mx-auto"
        max-width="300"
        icon="mdi-ticket-percent-outline"
      >
        {{ $t('session.completion.voucherEarned') }}
      </v-alert>

      <!-- CTAs -->
      <div class="d-flex flex-column ga-3 mx-auto" style="max-width: 300px">
        <v-btn
          color="primary"
          size="large"
          prepend-icon="mdi-checkbox-marked-circle-outline"
          @click="getAnother"
        >
          {{ $t('session.completion.getAnother') }}
        </v-btn>
        <v-btn
          variant="text"
          @click="router.push('/')"
        >
          {{ $t('session.completion.doneForToday') }}
        </v-btn>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '../../stores/session.js'
import AppLayout from '../../components/layout/AppLayout.vue'

const { t }        = useI18n()
const router       = useRouter()
const sessionStore = useSessionStore()

const result = computed(() => sessionStore.completionResult)
const displayedPoints = ref(0)

const streakLabel = computed(() => {
  if (!result.value) return ''
  const streak = result.value.current_streak ?? 0
  if (result.value.streak_safe_used) return t('session.completion.streakSafeUsed')
  return t('session.completion.dayStreak', { n: streak })
})

const streakSub = computed(() => {
  if (!result.value) return ''
  if (result.value.streak_safe_used) return t('session.completion.streakPreserved', { n: result.value.current_streak ?? 0 })
  if ((result.value.current_streak ?? 0) >= 7) return t('session.completion.streakBonus')
  return t('session.completion.keepGoing')
})

// Animate points counter
onMounted(() => {
  const target = result.value?.points_awarded ?? 0
  if (target === 0) { displayedPoints.value = 0; return }
  let current = 0
  const step = Math.ceil(target / 20)
  const interval = setInterval(() => {
    current = Math.min(current + step, target)
    displayedPoints.value = current
    if (current >= target) clearInterval(interval)
  }, 40)
})

function getAnother() {
  sessionStore.clearCompletion()
  router.push('/tasks/suggestions')
}
</script>
