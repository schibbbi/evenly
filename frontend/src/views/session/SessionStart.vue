<!-- Session Start — 2-step picker: Energy level → Available time.
     All tap-based, no text input. Creates the session and navigates to Suggestions.
-->
<template>
  <AppLayout>
    <div class="mb-6">
      <h1 class="text-h5 font-weight-bold mb-1">{{ $t('session.start.title') }}</h1>
      <p class="text-body-2 text-medium-emphasis">
        {{ step === 1 ? $t('session.start.stepEnergy') : $t('session.start.stepTime') }}
      </p>
    </div>

    <!-- Step progress dots -->
    <div class="d-flex ga-2 mb-6" aria-label="Step indicator">
      <div
        v-for="i in 2"
        :key="i"
        class="step-dot"
        :class="{ active: i === step, done: i < step }"
      />
    </div>

    <!-- ── Step 1: Energy level ─────────────────────── -->
    <div v-if="step === 1">
      <div class="d-flex flex-column ga-3">
        <v-card
          v-for="energy in energyOptions"
          :key="energy.value"
          :variant="selectedEnergy === energy.value ? 'flat' : 'outlined'"
          :color="selectedEnergy === energy.value ? 'primary' : undefined"
          rounded="xl"
          class="energy-card pa-4"
          role="button"
          :tabindex="0"
          :aria-pressed="selectedEnergy === energy.value"
          :aria-label="`Energy level: ${energy.label}`"
          @click="selectEnergy(energy.value)"
          @keyup.enter="selectEnergy(energy.value)"
          @keyup.space="selectEnergy(energy.value)"
        >
          <div class="d-flex align-center ga-4">
            <v-icon
              :icon="energy.icon"
              size="36"
              :color="selectedEnergy === energy.value ? 'on-primary' : energy.color"
            />
            <div>
              <p
                class="text-body-1 font-weight-semibold"
                :class="selectedEnergy === energy.value ? 'text-on-primary' : ''"
              >
                {{ energy.label }}
              </p>
              <p
                class="text-body-2"
                :class="selectedEnergy === energy.value ? 'text-on-primary' : 'text-medium-emphasis'"
              >
                {{ energy.description }}
              </p>
            </div>
          </div>
        </v-card>
      </div>
    </div>

    <!-- ── Step 2: Available time ──────────────────── -->
    <div v-if="step === 2">
      <div class="d-flex flex-wrap ga-3 justify-center">
        <v-btn
          v-for="opt in timeOptions"
          :key="opt.value"
          :variant="selectedTime === opt.value ? 'flat' : 'outlined'"
          :color="selectedTime === opt.value ? 'primary' : undefined"
          class="time-btn"
          size="large"
          :aria-pressed="selectedTime === opt.value"
          :aria-label="`${opt.label} minutes`"
          @click="selectedTime = opt.value"
        >
          {{ opt.label }} {{ $t('session.start.timeUnit') }}
        </v-btn>
      </div>
    </div>

    <!-- Error -->
    <v-alert
      v-if="errorMsg"
      type="error"
      variant="tonal"
      class="mt-4"
      density="compact"
    >
      {{ errorMsg }}
    </v-alert>

    <!-- Navigation -->
    <div class="d-flex ga-3 mt-8">
      <v-btn
        v-if="step === 2"
        variant="text"
        prepend-icon="mdi-arrow-left"
        @click="step = 1"
      >
        {{ $t('common.back') }}
      </v-btn>
      <v-spacer />
      <v-btn
        v-if="step === 1"
        color="primary"
        size="large"
        :disabled="!selectedEnergy"
        append-icon="mdi-arrow-right"
        @click="step = 2"
      >
        {{ $t('common.continue') }}
      </v-btn>
      <v-btn
        v-else
        color="primary"
        size="large"
        :disabled="!selectedTime"
        :loading="loading"
        prepend-icon="mdi-check"
        @click="startSession"
      >
        {{ $t('session.start.showTasks') }}
      </v-btn>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '../../stores/session.js'
import { useResidentStore } from '../../stores/resident.js'
import AppLayout from '../../components/layout/AppLayout.vue'

const { t }          = useI18n()
const router         = useRouter()
const sessionStore   = useSessionStore()
const residentStore  = useResidentStore()

const step           = ref(1)
const selectedEnergy = ref('')
const selectedTime   = ref(null)
const loading        = ref(false)
const errorMsg       = ref('')

const energyOptions = computed(() => [
  {
    value: 'high',
    label: t('session.start.energy.high'),
    description: t('session.start.energy.highDesc'),
    icon: 'mdi-lightning-bolt',
    color: 'success',
  },
  {
    value: 'medium',
    label: t('session.start.energy.medium'),
    description: t('session.start.energy.mediumDesc'),
    icon: 'mdi-battery-60',
    color: 'warning',
  },
  {
    value: 'low',
    label: t('session.start.energy.low'),
    description: t('session.start.energy.lowDesc'),
    icon: 'mdi-leaf',
    color: 'info',
  },
])

const timeOptions = [
  { value: 15,  label: '15' },
  { value: 30,  label: '30' },
  { value: 45,  label: '45' },
  { value: 60,  label: '60' },
  { value: 90,  label: '90' },
]

function selectEnergy(value) {
  selectedEnergy.value = value
  // Auto-advance to step 2 after brief delay for UX clarity
  setTimeout(() => { step.value = 2 }, 200)
}

async function startSession() {
  loading.value = true
  errorMsg.value = ''
  sessionStore.clearSession()
  await sessionStore.startSession(
    residentStore.activeResidentId,
    selectedEnergy.value,
    selectedTime.value,
  )
  loading.value = false
  if (sessionStore.error) {
    errorMsg.value = sessionStore.error
  } else {
    router.push('/tasks/suggestions')
  }
}
</script>

<style scoped>
.energy-card {
  cursor: pointer;
  min-height: 80px;
  transition: transform 0.1s ease;
}
.energy-card:active { transform: scale(0.98); }

.time-btn {
  min-width: 80px !important;
  height: 64px !important;
  font-size: 1.1rem !important;
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgb(var(--v-theme-surface-variant));
  transition: background 0.2s ease, width 0.2s ease;
}
.step-dot.active {
  background: rgb(var(--v-theme-primary));
  width: 24px;
  border-radius: 4px;
}
.step-dot.done {
  background: rgb(var(--v-theme-primary));
  opacity: 0.4;
}
</style>
