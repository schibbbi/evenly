<!-- Active Task Screen
     Shows the currently accepted task with optional cosmetic timer,
     "Mark as done" primary action, and "Delegate" option (if eligible).
-->
<template>
  <AppLayout>
    <!-- No active task guard -->
    <div v-if="!assignment" class="text-center py-10">
      <v-icon size="48" class="text-medium-emphasis mb-3">mdi-alert-circle-outline</v-icon>
      <p class="text-body-2 text-medium-emphasis mb-4">{{ $t('session.active.noTask') }}</p>
      <v-btn color="primary" @click="router.push('/tasks')">{{ $t('session.active.backToTasks') }}</v-btn>
    </div>

    <div v-else>
      <!-- Task header -->
      <div class="mb-6">
        <div class="d-flex align-center ga-2 mb-2">
          <v-icon size="18" class="text-medium-emphasis">mdi-door-open</v-icon>
          <span class="text-body-2 text-medium-emphasis">{{ assignment.room_name || $t('session.suggestions.room') }}</span>
        </div>
        <h1 class="text-h5 font-weight-bold mb-2">{{ assignment.task_name }}</h1>
        <div class="d-flex align-center flex-wrap ga-3">
          <div class="d-flex align-center ga-1">
            <v-icon size="16" class="text-medium-emphasis" aria-hidden="true">mdi-timer-outline</v-icon>
            <span class="text-body-2 text-medium-emphasis">~{{ assignment.estimated_minutes || 15 }} min</span>
          </div>
          <v-chip
            v-if="assignment.is_robot_variant"
            size="x-small"
            color="info"
            variant="tonal"
            prepend-icon="mdi-robot-vacuum"
          >
            {{ $t('session.active.robotTask') }}
          </v-chip>
        </div>
      </div>

      <!-- Task description / tip -->
      <v-card
        v-if="assignment.description"
        variant="tonal"
        color="primary"
        rounded="xl"
        class="pa-4 mb-6"
      >
        <div class="d-flex align-start ga-3">
          <v-icon color="primary" class="mt-0_5" aria-hidden="true">mdi-lightbulb-outline</v-icon>
          <p class="text-body-2">{{ assignment.description }}</p>
        </div>
      </v-card>

      <!-- Cosmetic timer -->
      <div class="d-flex align-center justify-center mb-8">
        <div class="timer-display" aria-live="polite" :aria-label="`Timer: ${formattedTime}`">
          <span class="text-h3 font-weight-light">{{ formattedTime }}</span>
        </div>
      </div>

      <div class="d-flex ga-3 mb-4">
        <v-btn
          :color="timerRunning ? 'error' : 'secondary'"
          variant="tonal"
          :prepend-icon="timerRunning ? 'mdi-pause' : 'mdi-play'"
          :aria-label="timerRunning ? $t('session.active.pauseTimer') : $t('session.active.startTimer')"
          @click="toggleTimer"
        >
          {{ timerRunning ? $t('session.active.pauseTimer') : $t('session.active.startTimer') }}
        </v-btn>
        <v-btn
          variant="text"
          :aria-label="$t('session.active.resetTimer')"
          @click="resetTimer"
          :disabled="elapsed === 0"
        >
          <v-icon>mdi-refresh</v-icon>
        </v-btn>
      </div>

      <!-- Mark as done -->
      <v-btn
        block
        color="primary"
        size="x-large"
        :loading="completing"
        style="height: 64px; font-size: 1.1rem"
        prepend-icon="mdi-check-circle-outline"
        class="mb-3"
        @click="complete"
      >
        {{ $t('session.active.markDone') }}
      </v-btn>

      <!-- Delegate option -->
      <div v-if="canDelegate">
        <v-btn
          block
          variant="text"
          class="mb-1"
          @click="showDelegateSheet = true"
        >
          {{ $t('session.active.delegate') }}
        </v-btn>
      </div>

      <!-- Error -->
      <v-alert
        v-if="errorMsg"
        type="error"
        variant="tonal"
        density="compact"
        class="mt-3"
      >
        {{ errorMsg }}
      </v-alert>

      <!-- Delegate bottom sheet -->
      <v-bottom-sheet v-model="showDelegateSheet" max-width="480">
        <v-card rounded="t-xl" class="pa-4">
          <v-card-title class="text-h6 mb-3">{{ $t('session.active.delegateTitle') }}</v-card-title>
          <p class="text-body-2 text-medium-emphasis mb-4">
            {{ $t('session.active.delegateInfo') }}
          </p>
          <v-list>
            <v-list-item
              v-for="r in eligibleResidents"
              :key="r.id"
              rounded="lg"
              @click="delegate(r.id)"
            >
              <template #prepend>
                <ResidentAvatar :resident="r" size="40" class="mr-3" />
              </template>
              <v-list-item-title>{{ r.display_name }}</v-list-item-title>
            </v-list-item>
          </v-list>
          <v-btn block variant="text" class="mt-2" @click="showDelegateSheet = false">
            {{ $t('common.cancel') }}
          </v-btn>
        </v-card>
      </v-bottom-sheet>

      <!-- PIN sheet for delegate -->
      <PinBottomSheet
        v-model="showPinSheet"
        :title="$t('session.active.confirmDelegation')"
        :subtitle="$t('session.active.confirmDelegationSub')"
        :resident-id="residentStore.activeResidentId"
        @success="onPinSuccess"
        @cancel="showPinSheet = false"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '../../stores/session.js'
import { useResidentStore } from '../../stores/resident.js'
import { assignmentsApi } from '../../api/index.js'
import { usePinStore } from '../../stores/pin.js'
import AppLayout from '../../components/layout/AppLayout.vue'
import ResidentAvatar from '../../components/shared/ResidentAvatar.vue'
import PinBottomSheet from '../../components/shared/PinBottomSheet.vue'

const { t }          = useI18n()
const router         = useRouter()
const sessionStore   = useSessionStore()
const residentStore  = useResidentStore()
const pinStore       = usePinStore()

const assignment = computed(() => sessionStore.activeAssignment)
const completing = ref(false)
const errorMsg   = ref('')
const showDelegateSheet = ref(false)
const showPinSheet      = ref(false)
const pendingDelegateTo = ref(null)

// Timer (cosmetic)
const elapsed     = ref(0)
const timerRunning = ref(false)
let timerInterval = null

const formattedTime = computed(() => {
  const m = Math.floor(elapsed.value / 60).toString().padStart(2, '0')
  const s = (elapsed.value % 60).toString().padStart(2, '0')
  return `${m}:${s}`
})

function toggleTimer() {
  if (timerRunning.value) {
    clearInterval(timerInterval)
    timerRunning.value = false
  } else {
    timerRunning.value = true
    timerInterval = setInterval(() => elapsed.value++, 1000)
  }
}

function resetTimer() {
  clearInterval(timerInterval)
  timerRunning.value = false
  elapsed.value = 0
}

onUnmounted(() => clearInterval(timerInterval))

// Residents eligible for delegation (not self, not in their dislike list — simplification: just not self)
const eligibleResidents = computed(() =>
  residentStore.residents.filter((r) => r.id !== residentStore.activeResidentId)
)

const canDelegate = computed(() => eligibleResidents.value.length > 0)

async function complete() {
  completing.value = true
  errorMsg.value = ''
  await sessionStore.completeTask(assignment.value.assignment_id || assignment.value.id)
  completing.value = false
  if (sessionStore.error) {
    errorMsg.value = sessionStore.error
  } else {
    router.push('/tasks/done')
  }
}

function delegate(toResidentId) {
  pendingDelegateTo.value = toResidentId
  showDelegateSheet.value = false
  showPinSheet.value = true
}

async function onPinSuccess(pin) {
  try {
    await assignmentsApi.delegate(
      assignment.value.assignment_id || assignment.value.id,
      pendingDelegateTo.value,
      pin,
    )
    sessionStore.clearSession()
    router.push('/')
  } catch (e) {
    errorMsg.value = e.userMessage || t('session.active.delegateFailed')
  }
}
</script>

<style scoped>
.timer-display {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 160px;
  height: 80px;
  border: 2px solid rgb(var(--v-theme-surface-variant));
  border-radius: 16px;
}
</style>
