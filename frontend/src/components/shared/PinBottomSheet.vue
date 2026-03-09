<!-- PIN entry bottom sheet
     Shown when a role-protected action requires authentication.
     PIN is verified against the backend, then stored in memory (PinStore) for 30 min.
     On 3 failures: locked for 5 minutes with friendly message.
-->
<template>
  <v-bottom-sheet v-model="model" max-width="480" persistent>
    <v-card rounded="t-xl" class="pa-4">
      <v-card-title class="text-h6 text-center mb-1">
        {{ title || $t('pin.enterPin') }}
      </v-card-title>
      <p v-if="subtitle" class="text-body-2 text-center text-medium-emphasis mb-4">
        {{ subtitle }}
      </p>

      <!-- PIN dots display -->
      <div class="d-flex justify-center ga-3 mb-6" aria-live="polite" :aria-label="$t('pin.digitsEntered', { n: digits.length })">
        <div
          v-for="i in 4"
          :key="i"
          class="pin-dot"
          :class="{ filled: digits.length >= i }"
        />
      </div>

      <!-- Lock message -->
      <v-alert
        v-if="locked"
        type="warning"
        variant="tonal"
        class="mb-4 text-body-2"
        icon="mdi-lock-outline"
      >
        {{ $t('pin.tooManyAttempts', { n: lockCountdown }) }}
      </v-alert>

      <!-- Error message -->
      <v-alert
        v-else-if="errorMsg"
        type="error"
        variant="tonal"
        class="mb-4 text-body-2"
        icon="mdi-alert-circle-outline"
      >
        {{ errorMsg }}
      </v-alert>

      <!-- Numeric keypad -->
      <div class="pin-pad" role="group" aria-label="PIN keypad">
        <template v-for="key in keypadKeys" :key="key">
          <v-btn
            v-if="key !== 'del' && key !== 'cancel'"
            class="pin-key"
            variant="tonal"
            size="large"
            :aria-label="$t('pin.enterDigit', { n: key })"
            :disabled="locked || digits.length >= 4"
            @click="pressDigit(key)"
          >
            {{ key }}
          </v-btn>
          <v-btn
            v-else-if="key === 'del'"
            class="pin-key"
            variant="text"
            size="large"
            :aria-label="$t('pin.deleteDigit')"
            :disabled="locked || digits.length === 0"
            @click="deleteDigit"
          >
            <v-icon>mdi-backspace-outline</v-icon>
          </v-btn>
          <v-btn
            v-else
            class="pin-key"
            variant="text"
            size="large"
            :aria-label="$t('pin.cancel')"
            @click="cancel"
          >
            {{ $t('pin.cancel') }}
          </v-btn>
        </template>
      </div>

      <!-- Loading state while verifying -->
      <div v-if="verifying" class="d-flex justify-center mt-3">
        <v-progress-circular indeterminate color="primary" size="24" />
      </div>
    </v-card>
  </v-bottom-sheet>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePinStore } from '../../stores/pin.js'

const { t } = useI18n()

const props = defineProps({
  title:    { type: String, default: '' },
  subtitle: { type: String, default: '' },
  residentId: { type: Number, required: true },
})

const emit = defineEmits(['success', 'cancel'])
const model = defineModel()

const pinStore = usePinStore()

const digits    = ref([])
const errorMsg  = ref('')
const verifying = ref(false)
const attempts  = ref(0)
const locked    = ref(false)
const lockCountdown = ref(0)
let lockTimer = null

const MAX_ATTEMPTS   = 3
const LOCK_DURATION  = 5 * 60  // 300 seconds

const keypadKeys = ['1','2','3','4','5','6','7','8','9','cancel','0','del']

watch(model, (v) => {
  if (v) reset()
})

function reset() {
  digits.value = []
  errorMsg.value = ''
  attempts.value = 0
  if (!locked.value) errorMsg.value = ''
}

function pressDigit(d) {
  if (digits.value.length < 4 && !locked.value) {
    digits.value.push(d)
    if (digits.value.length === 4) submit()
  }
}

function deleteDigit() {
  digits.value.pop()
  errorMsg.value = ''
}

function cancel() {
  model.value = false
  emit('cancel')
  reset()
}

async function submit() {
  verifying.value = true
  errorMsg.value = ''
  const pin = digits.value.join('')
  const ok = await pinStore.verifyAndStore(props.residentId, pin)
  verifying.value = false

  if (ok) {
    model.value = false
    emit('success', pin)
    reset()
  } else {
    attempts.value++
    digits.value = []
    if (attempts.value >= MAX_ATTEMPTS) {
      startLock()
    } else {
      errorMsg.value = pinStore.error || t('pin.incorrectPin')
    }
  }
}

function startLock() {
  locked.value = true
  lockCountdown.value = LOCK_DURATION
  lockTimer = setInterval(() => {
    lockCountdown.value--
    if (lockCountdown.value <= 0) {
      locked.value = false
      attempts.value = 0
      errorMsg.value = ''
      clearInterval(lockTimer)
    }
  }, 1000)
}

onUnmounted(() => {
  if (lockTimer) clearInterval(lockTimer)
})
</script>

<style scoped>
.pin-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid rgb(var(--v-theme-primary));
  background: transparent;
  transition: background 0.15s ease;
}
.pin-dot.filled {
  background: rgb(var(--v-theme-primary));
}

.pin-pad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  max-width: 300px;
  margin: 0 auto;
}

.pin-key {
  height: 64px !important;
  font-size: 1.25rem;
  font-weight: 500;
}
</style>
