<!-- First-Login Wizard — shown to co-residents who have setup_complete = false.
     4 steps: Welcome → Change PIN → Preferences → Done
-->
<template>
  <v-app :theme="themeStore.theme">
    <v-main class="d-flex align-center justify-center" style="min-height: 100dvh">
      <div class="hk-container pa-4">

        <!-- Progress -->
        <div class="d-flex align-center mb-6">
          <v-progress-linear
            :model-value="progressPct"
            color="primary"
            rounded
            height="4"
            class="flex-grow-1"
            :aria-label="`Step ${step} of ${TOTAL_STEPS}`"
          />
          <span class="text-caption text-medium-emphasis ml-3 flex-shrink-0">
            {{ $t('wizard.firstLogin.step', { current: step, total: TOTAL_STEPS }) }}
          </span>
        </div>

        <!-- ── Step 1: Welcome ─────────────────────────── -->
        <div v-if="step === 1">
          <div class="text-center mb-8">
            <ResidentAvatar :resident="residentStore.activeResident" size="80" class="mb-4" />
            <h1 class="text-h5 font-weight-bold mb-2">
              {{ $t('wizard.firstLogin.welcome.title', { name: residentStore.activeResident?.display_name || 'there' }) }}
            </h1>
            <p class="text-body-1 text-medium-emphasis">
              {{ $t('wizard.firstLogin.welcome.sub') }}
            </p>
          </div>
          <v-btn block size="large" color="primary" @click="next">
            {{ $t('wizard.firstLogin.welcome.cta') }}
          </v-btn>
        </div>

        <!-- ── Step 2: Change PIN ──────────────────────── -->
        <div v-else-if="step === 2">
          <h2 class="text-h5 font-weight-bold mb-2">{{ $t('wizard.firstLogin.pin.title') }}</h2>
          <p class="text-body-2 text-medium-emphasis mb-6">
            {{ $t('wizard.firstLogin.pin.sub') }}
          </p>

          <v-btn
            v-if="!changingPin"
            variant="outlined"
            block
            class="mb-4"
            @click="changingPin = true"
          >
            {{ $t('wizard.firstLogin.pin.setNew') }}
          </v-btn>

          <div v-else>
            <p class="text-body-2 font-weight-medium mb-2">{{ $t('wizard.firstLogin.pin.newPin') }}</p>
            <div class="d-flex ga-3 mb-4">
              <div
                v-for="i in 4"
                :key="i"
                class="pin-dot"
                :class="{ filled: newPin.length >= i }"
              />
            </div>
            <div class="pin-pad" role="group" :aria-label="$t('wizard.firstLogin.pin.newPin')">
              <template v-for="key in keypadKeys" :key="key">
                <v-btn
                  v-if="key !== 'del'"
                  class="pin-key"
                  variant="tonal"
                  :aria-label="key === 'clr' ? 'Clear' : `Enter digit ${key}`"
                  :disabled="newPin.length >= 4"
                  @click="key === 'clr' ? (newPin = '') : (newPin += key)"
                >
                  {{ key === 'clr' ? '✕' : key }}
                </v-btn>
                <v-btn
                  v-else
                  class="pin-key"
                  variant="text"
                  :aria-label="$t('pin.deleteDigit')"
                  @click="newPin = newPin.slice(0, -1)"
                >
                  <v-icon>mdi-backspace-outline</v-icon>
                </v-btn>
              </template>
            </div>

            <v-alert v-if="pinError" type="error" variant="tonal" density="compact" class="mt-2">
              {{ pinError }}
            </v-alert>
          </div>

          <WizardNav
            :can-next="!changingPin || newPin.length === 4"
            @back="back"
            @next="handlePinStep"
          />
        </div>

        <!-- ── Step 3: Preferences ─────────────────────── -->
        <div v-else-if="step === 3">
          <h2 class="text-h5 font-weight-bold mb-2">{{ $t('wizard.firstLogin.preferences.title') }}</h2>
          <p class="text-body-2 text-medium-emphasis mb-4">
            {{ $t('wizard.firstLogin.preferences.sub') }}
          </p>

          <PreferenceSelector v-model="preferences" />

          <WizardNav @back="back" @next="savePreferencesAndNext" :loading="saving" />
        </div>

        <!-- ── Step 4: Done ────────────────────────────── -->
        <div v-else-if="step === 4">
          <div class="text-center mb-8">
            <v-icon size="64" color="success" class="mb-4">mdi-check-circle-outline</v-icon>
            <h2 class="text-h5 font-weight-bold mb-2">{{ $t('wizard.firstLogin.done.title') }}</h2>
            <p class="text-body-2 text-medium-emphasis">
              {{ $t('wizard.firstLogin.done.sub') }}
            </p>
          </div>
          <v-btn block size="large" color="primary" :loading="finishing" @click="finish">
            {{ $t('wizard.firstLogin.done.cta') }}
          </v-btn>
        </div>

      </div>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useThemeStore } from '../../stores/theme.js'
import { useResidentStore } from '../../stores/resident.js'
import { authApi, residentsApi } from '../../api/index.js'
import { usePinStore } from '../../stores/pin.js'
import WizardNav from '../../components/wizard/WizardNav.vue'
import PreferenceSelector from '../../components/wizard/PreferenceSelector.vue'
import ResidentAvatar from '../../components/shared/ResidentAvatar.vue'

const { t } = useI18n()
const router       = useRouter()
const themeStore   = useThemeStore()
const residentStore = useResidentStore()
const pinStore     = usePinStore()

const TOTAL_STEPS = 4
const step        = ref(1)
const saving      = ref(false)
const finishing   = ref(false)
const changingPin = ref(false)
const newPin      = ref('')
const pinError    = ref('')
const preferences = ref({})

const keypadKeys = ['1','2','3','4','5','6','7','8','9','clr','0','del']

const progressPct = computed(() => ((step.value - 1) / (TOTAL_STEPS - 1)) * 100)

function next() { step.value++ }
function back() { if (step.value > 1) step.value-- }

async function handlePinStep() {
  if (changingPin.value && newPin.value.length === 4) {
    pinError.value = ''
    saving.value = true
    try {
      const currentPin = pinStore.getPinForResident(residentStore.activeResidentId)
      if (!currentPin) {
        pinError.value = t('wizard.firstLogin.pin.noPin')
        saving.value = false
        return
      }
      await authApi.changePin(residentStore.activeResidentId, currentPin, newPin.value)
      pinStore.setPin(residentStore.activeResidentId, newPin.value)
    } catch (e) {
      pinError.value = e.userMessage || t('wizard.firstLogin.pin.changeFailed')
      saving.value = false
      return
    } finally {
      saving.value = false
    }
  }
  next()
}

async function savePreferencesAndNext() {
  saving.value = true
  try {
    const pin = pinStore.getPinForResident(residentStore.activeResidentId)
    for (const [category, pref] of Object.entries(preferences.value)) {
      if (pref) {
        await residentsApi.setPreference(residentStore.activeResidentId, { task_category: category, preference: pref }, pin)
      }
    }
  } catch (_) {
    // non-critical — skip silently
  } finally {
    saving.value = false
  }
  next()
}

async function finish() {
  finishing.value = true
  try {
    const pin = pinStore.getPinForResident(residentStore.activeResidentId)
    await residentsApi.update(residentStore.activeResidentId, { setup_complete: true }, pin)
  } catch (_) {}
  finally {
    finishing.value = false
  }
  router.push('/')
}
</script>

<style scoped>
.pin-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgb(var(--v-theme-primary));
  background: transparent;
  transition: background 0.15s ease;
  display: inline-block;
  margin-right: 8px;
}
.pin-dot.filled { background: rgb(var(--v-theme-primary)); }

.pin-pad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  max-width: 280px;
  margin-bottom: 8px;
}
.pin-key { height: 56px !important; font-size: 1.1rem; }
</style>
