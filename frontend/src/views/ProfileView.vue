<!-- My Profile Screen
     Personal stats, last 10 point transactions, vouchers, task preferences.
     PIN change accessible here.
-->
<template>
  <AppLayout>
    <!-- Loading -->
    <v-skeleton-loader v-if="loading" type="card, list-item-two-line, list-item-two-line, list-item-two-line" />

    <div v-else>
      <!-- Profile header -->
      <div class="d-flex align-center ga-4 mb-6">
        <ResidentAvatar :resident="residentStore.activeResident" size="64" />
        <div>
          <h1 class="text-h5 font-weight-bold">
            {{ residentStore.activeResident?.display_name || $t('profile.title') }}
          </h1>
          <v-chip size="x-small" :color="roleColor" variant="tonal">
            {{ residentStore.activeResident?.role }}
          </v-chip>
        </div>
      </div>

      <!-- Stats cards -->
      <div class="d-flex ga-3 mb-4 flex-wrap">
        <v-card variant="tonal" color="primary" rounded="xl" class="stat-card pa-3 flex-grow-1">
          <p class="text-caption text-medium-emphasis">{{ $t('profile.totalPoints') }}</p>
          <p class="text-h5 font-weight-bold">{{ gameStore.profile?.total_points ?? 0 }}</p>
        </v-card>
        <v-card variant="tonal" color="secondary" rounded="xl" class="stat-card pa-3 flex-grow-1">
          <p class="text-caption text-medium-emphasis">{{ $t('profile.streak') }}</p>
          <div class="d-flex align-center ga-1">
            <v-icon size="20" aria-hidden="true">mdi-fire</v-icon>
            <p class="text-h5 font-weight-bold">{{ gameStore.profile?.current_streak ?? 0 }}</p>
          </div>
        </v-card>
        <v-card variant="outlined" rounded="xl" class="stat-card pa-3 flex-grow-1">
          <p class="text-caption text-medium-emphasis">{{ $t('profile.bestStreak') }}</p>
          <p class="text-h5 font-weight-bold">{{ gameStore.profile?.longest_streak ?? 0 }}</p>
        </v-card>
        <v-card variant="outlined" rounded="xl" class="stat-card pa-3 flex-grow-1">
          <p class="text-caption text-medium-emphasis">{{ $t('profile.streakSafes') }}</p>
          <div class="d-flex align-center ga-1">
            <v-icon size="18" color="secondary" aria-hidden="true">mdi-shield-check</v-icon>
            <p class="text-h5 font-weight-bold">{{ gameStore.profile?.streak_safes_available ?? 0 }}</p>
          </div>
        </v-card>
      </div>

      <!-- Vouchers -->
      <div class="mb-4">
        <div class="d-flex align-center justify-space-between mb-2">
          <span class="text-subtitle-2 font-weight-medium">{{ $t('profile.vouchers') }}</span>
          <span class="text-caption text-medium-emphasis">{{ $t('profile.vouchersCount', { n: gameStore.vouchers.length }) }}</span>
        </div>
        <div v-if="gameStore.vouchers.length === 0" class="text-center py-4">
          <p class="text-body-2 text-medium-emphasis">{{ $t('profile.noVouchers') }}</p>
        </div>
        <div v-else>
          <v-card
            v-for="v in gameStore.vouchers"
            :key="v.id"
            variant="outlined"
            rounded="lg"
            class="mb-2 pa-3"
          >
            <div class="d-flex align-center ga-3">
              <v-icon color="secondary" aria-hidden="true">mdi-ticket-percent-outline</v-icon>
              <div class="flex-grow-1">
                <p class="text-body-2 font-weight-medium">{{ v.label }}</p>
                <p class="text-caption text-medium-emphasis">{{ $t('profile.earnedOn', { date: shortDate(v.earned_at) }) }}</p>
              </div>
              <v-btn
                size="small"
                variant="tonal"
                color="secondary"
                @click="redeem(v.id)"
                :loading="redeemingId === v.id"
              >
                {{ $t('common.redeem') }}
              </v-btn>
            </div>
          </v-card>
        </div>
      </div>

      <!-- Point history -->
      <div class="mb-4">
        <span class="text-subtitle-2 font-weight-medium d-block mb-2">{{ $t('profile.recentPoints') }}</span>
        <div v-if="gameStore.transactions.length === 0" class="text-center py-4">
          <p class="text-body-2 text-medium-emphasis">{{ $t('profile.noTransactions') }}</p>
        </div>
        <v-list density="compact" lines="one" class="pa-0">
          <v-list-item
            v-for="t in gameStore.transactions"
            :key="t.id"
            rounded="lg"
            class="px-0"
          >
            <template #prepend>
              <v-icon
                :color="t.amount > 0 ? 'success' : 'error'"
                :icon="t.amount > 0 ? 'mdi-plus-circle-outline' : 'mdi-minus-circle-outline'"
                aria-hidden="true"
              />
            </template>
            <v-list-item-title class="text-body-2">
              {{ reasonLabel(t.reason) }}
            </v-list-item-title>
            <v-list-item-subtitle class="text-caption">
              {{ shortDate(t.created_at) }}
            </v-list-item-subtitle>
            <template #append>
              <span
                class="text-body-2 font-weight-medium"
                :class="t.amount > 0 ? 'text-success' : 'text-error'"
              >
                {{ t.amount > 0 ? '+' : '' }}{{ t.amount }}
              </span>
            </template>
          </v-list-item>
        </v-list>
      </div>

      <!-- Preferences -->
      <div class="mb-6">
        <span class="text-subtitle-2 font-weight-medium d-block mb-2">{{ $t('profile.preferences') }}</span>
        <PreferenceSelector v-model="preferences" />
        <v-btn
          block
          variant="outlined"
          class="mt-3"
          :loading="savingPrefs"
          @click="savePreferences"
        >
          {{ $t('profile.savePreferences') }}
        </v-btn>
        <v-alert
          v-if="prefSaved"
          type="success"
          variant="tonal"
          density="compact"
          class="mt-2"
        >
          {{ $t('profile.preferencesSaved') }}
        </v-alert>
      </div>

      <!-- Change PIN -->
      <v-btn
        block
        variant="outlined"
        prepend-icon="mdi-lock-outline"
        class="mb-2"
        @click="showChangePinSheet = true"
      >
        {{ $t('profile.changePin') }}
      </v-btn>

      <!-- Change PIN sheet -->
      <v-bottom-sheet v-model="showChangePinSheet" max-width="480">
        <v-card rounded="t-xl" class="pa-4">
          <v-card-title class="text-h6 mb-3">{{ $t('profile.changePinTitle') }}</v-card-title>
          <div class="mb-3">
            <p class="text-body-2 font-weight-medium mb-2">{{ $t('profile.currentPin') }}</p>
            <v-text-field
              v-model="currentPinInput"
              type="password"
              maxlength="4"
              inputmode="numeric"
              :placeholder="$t('profile.currentPinPlaceholder')"
              density="compact"
            />
          </div>
          <div class="mb-3">
            <p class="text-body-2 font-weight-medium mb-2">{{ $t('profile.newPin') }}</p>
            <v-text-field
              v-model="newPinInput"
              type="password"
              maxlength="4"
              inputmode="numeric"
              :placeholder="$t('profile.newPinPlaceholder')"
              density="compact"
            />
          </div>
          <v-alert v-if="pinChangeError" type="error" variant="tonal" density="compact" class="mb-3">
            {{ pinChangeError }}
          </v-alert>
          <div class="d-flex ga-2">
            <v-btn variant="text" class="flex-grow-1" @click="showChangePinSheet = false">{{ $t('common.cancel') }}</v-btn>
            <v-btn
              color="primary"
              class="flex-grow-1"
              :loading="changingPin"
              :disabled="currentPinInput.length !== 4 || newPinInput.length !== 4"
              @click="changePin"
            >
              {{ $t('common.change') }}
            </v-btn>
          </div>
        </v-card>
      </v-bottom-sheet>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useResidentStore } from '../stores/resident.js'
import { useGameStore } from '../stores/game.js'
import { usePinStore } from '../stores/pin.js'
import { residentsApi, authApi } from '../api/index.js'
import AppLayout from '../components/layout/AppLayout.vue'
import ResidentAvatar from '../components/shared/ResidentAvatar.vue'
import PreferenceSelector from '../components/wizard/PreferenceSelector.vue'

const { t }         = useI18n()
const residentStore = useResidentStore()
const gameStore     = useGameStore()
const pinStore      = usePinStore()

const loading        = ref(true)
const preferences    = ref({})
const savingPrefs    = ref(false)
const prefSaved      = ref(false)
const redeemingId    = ref(null)
const showChangePinSheet = ref(false)
const currentPinInput = ref('')
const newPinInput     = ref('')
const pinChangeError  = ref('')
const changingPin     = ref(false)

const roleColor = computed(() => {
  return { admin: 'primary', edit: 'secondary', view: 'default' }[residentStore.activeResident?.role] || 'default'
})

function reasonLabel(reason) {
  const map = {
    task_completion: t('profile.pointReason.task_completion'),
    unpopular_bonus: t('profile.pointReason.unpopular_bonus'),
    streak_bonus:    t('profile.pointReason.streak_bonus'),
    reroll_malus:    t('profile.pointReason.reroll_malus'),
    delegation_cost: t('profile.pointReason.delegation_cost'),
  }
  return map[reason] || reason
}

function shortDate(isoStr) {
  if (!isoStr) return ''
  return new Date(isoStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

async function redeem(voucherId) {
  redeemingId.value = voucherId
  try {
    await gameStore.redeemVoucher(voucherId)
  } finally {
    redeemingId.value = null
  }
}

async function savePreferences() {
  savingPrefs.value = true
  prefSaved.value = false
  try {
    const pin = pinStore.getPinForResident(residentStore.activeResidentId)
    for (const [category, pref] of Object.entries(preferences.value)) {
      if (pref) {
        await residentsApi.setPreference(residentStore.activeResidentId, { task_category: category, preference: pref }, pin)
      }
    }
    prefSaved.value = true
    setTimeout(() => { prefSaved.value = false }, 2500)
  } finally {
    savingPrefs.value = false
  }
}

async function changePin() {
  changingPin.value = true
  pinChangeError.value = ''
  try {
    await authApi.changePin(residentStore.activeResidentId, currentPinInput.value, newPinInput.value)
    pinStore.setPin(residentStore.activeResidentId, newPinInput.value)
    showChangePinSheet.value = false
    currentPinInput.value = ''
    newPinInput.value = ''
  } catch (e) {
    pinChangeError.value = e.userMessage || t('profile.pinChangeFailed')
  } finally {
    changingPin.value = false
  }
}

onMounted(async () => {
  try {
    const id = residentStore.activeResidentId
    await Promise.allSettled([
      gameStore.loadProfile(id),
      gameStore.loadTransactions(id),
      gameStore.loadVouchers(),
    ])
    // Load existing preferences
    try {
      const prefRes = await residentsApi.getPreferences(id)
      const prefs = {}
      for (const p of (prefRes.data || [])) {
        prefs[p.category] = p.preference
      }
      preferences.value = prefs
    } catch (_) {}
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.stat-card {
  min-width: 100px;
}
</style>
