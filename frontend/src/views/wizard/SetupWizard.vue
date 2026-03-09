<!-- Admin Setup Wizard — 8 steps, shown when no household exists in DB.
     Creates household, rooms, devices, first admin resident, and triggers catalog generation.
-->
<template>
  <v-app :theme="themeStore.theme">
    <v-main class="d-flex align-center justify-center" style="min-height: 100dvh">
      <div class="hk-container pa-4">

        <!-- Progress indicator -->
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
            {{ $t('wizard.setup.step', { current: step, total: TOTAL_STEPS }) }}
          </span>
        </div>

        <!-- ── Step 1: Welcome ─────────────────────────── -->
        <div v-if="step === 1">
          <div class="text-center mb-8">
            <v-icon size="64" color="primary" class="mb-4">mdi-home-heart</v-icon>
            <h1 class="text-h4 font-weight-bold mb-2">{{ $t('wizard.setup.welcome.title') }}</h1>
            <p class="text-body-1 text-medium-emphasis">
              {{ $t('wizard.setup.welcome.tagline') }}
            </p>
          </div>
          <v-btn block size="large" color="primary" @click="next">
            {{ $t('wizard.setup.welcome.cta') }}
          </v-btn>
        </div>

        <!-- ── Step 2: Household details ──────────────── -->
        <div v-else-if="step === 2">
          <h2 class="text-h5 font-weight-bold mb-6">{{ $t('wizard.setup.household.title') }}</h2>
          <v-text-field
            v-model="household.name"
            :label="$t('wizard.setup.household.name')"
            :placeholder="$t('wizard.setup.household.namePlaceholder')"
            prepend-inner-icon="mdi-home-outline"
            autofocus
            :rules="[v => !!v || 'Name is required']"
          />
          <v-select
            v-model="household.timezone"
            :label="$t('wizard.setup.household.timezone')"
            :items="timezones"
            prepend-inner-icon="mdi-earth"
            clearable
          />
          <WizardNav :can-next="!!household.name.trim()" @back="back" @next="next" />
        </div>

        <!-- ── Step 3: Who lives here? ─────────────────── -->
        <div v-else-if="step === 3">
          <h2 class="text-h5 font-weight-bold mb-2">{{ $t('wizard.setup.composition.title') }}</h2>
          <p class="text-body-2 text-medium-emphasis mb-6">
            {{ $t('wizard.setup.composition.sub') }}
          </p>

          <v-list lines="one" class="mb-2">
            <v-list-item
              v-for="flag in compositionFlags"
              :key="flag.key"
              rounded="lg"
              class="px-2"
            >
              <template #prepend>
                <v-icon :icon="flag.icon" class="mr-2" />
              </template>
              <v-list-item-title>{{ flag.label }}</v-list-item-title>
              <template #append>
                <v-switch
                  v-model="household[flag.key]"
                  color="primary"
                  hide-details
                  :aria-label="flag.label"
                />
              </template>
            </v-list-item>
          </v-list>

          <!-- Child age groups (conditional) -->
          <div v-if="household.has_children" class="mt-4 mb-2">
            <p class="text-body-2 font-weight-medium mb-2">{{ $t('wizard.setup.composition.childAgeGroups') }}</p>
            <div class="d-flex flex-wrap ga-2">
              <v-chip
                v-for="ag in childAgeGroups"
                :key="ag.value"
                :color="childAges.includes(ag.value) ? 'primary' : undefined"
                :variant="childAges.includes(ag.value) ? 'flat' : 'outlined'"
                @click="toggleAge(ag.value)"
              >
                {{ ag.label }}
              </v-chip>
            </div>
          </div>

          <WizardNav @back="back" @next="next" />
        </div>

        <!-- ── Step 4: Appliances ──────────────────────── -->
        <div v-else-if="step === 4">
          <h2 class="text-h5 font-weight-bold mb-2">{{ $t('wizard.setup.appliances.title') }}</h2>
          <p class="text-body-2 text-medium-emphasis mb-6">
            {{ $t('wizard.setup.appliances.sub') }}
          </p>

          <v-list lines="one">
            <v-list-item
              v-for="device in visibleDeviceFlags"
              :key="device.key"
              rounded="lg"
              class="px-2"
            >
              <template #prepend>
                <v-icon :icon="device.icon" class="mr-2" />
              </template>
              <v-list-item-title>{{ device.label }}</v-list-item-title>
              <template #append>
                <v-switch
                  v-model="household[device.key]"
                  color="primary"
                  hide-details
                  :aria-label="device.label"
                />
              </template>
            </v-list-item>
          </v-list>

          <WizardNav @back="back" @next="next" />
        </div>

        <!-- ── Step 5: Rooms ───────────────────────────── -->
        <div v-else-if="step === 5">
          <h2 class="text-h5 font-weight-bold mb-2">{{ $t('wizard.setup.rooms.title') }}</h2>
          <p class="text-body-2 text-medium-emphasis mb-6">
            {{ $t('wizard.setup.rooms.sub') }}
          </p>

          <div class="d-flex flex-wrap ga-2 mb-6">
            <v-chip
              v-for="room in visibleRoomTemplates"
              :key="room.name"
              :color="selectedRooms.includes(room.name) ? 'primary' : undefined"
              :variant="selectedRooms.includes(room.name) ? 'flat' : 'outlined'"
              size="large"
              @click="toggleRoom(room.name)"
            >
              <v-icon :icon="room.icon" start />
              {{ $t(`wizard.setup.rooms.rooms.${room.name}`, room.name) }}
            </v-chip>
          </div>

          <!-- Custom room -->
          <div class="d-flex ga-2 mb-4">
            <v-text-field
              v-model="customRoomInput"
              :label="$t('wizard.setup.rooms.addCustom')"
              density="compact"
              hide-details
              @keyup.enter="addCustomRoom"
            />
            <v-btn
              icon="mdi-plus"
              variant="tonal"
              color="primary"
              :aria-label="$t('settings.addRoom')"
              @click="addCustomRoom"
            />
          </div>

          <v-chip
            v-for="r in customRooms"
            :key="r"
            closable
            class="mr-2 mb-2"
            @click:close="removeCustomRoom(r)"
          >
            {{ r }}
          </v-chip>

          <WizardNav :can-next="selectedRooms.length > 0 || customRooms.length > 0" @back="back" @next="next" />
        </div>

        <!-- ── Step 6: Your profile ────────────────────── -->
        <div v-else-if="step === 6">
          <h2 class="text-h5 font-weight-bold mb-6">{{ $t('wizard.setup.profile.title') }}</h2>

          <v-text-field v-model="admin.name" :label="$t('wizard.setup.profile.fullName')" class="mb-2" :rules="[v => !!v || 'Required']" />
          <v-text-field v-model="admin.display_name" :label="$t('wizard.setup.profile.displayName')" class="mb-4" :rules="[v => !!v || 'Required']" />

          <!-- Avatar color -->
          <p class="text-body-2 font-weight-medium mb-2">{{ $t('wizard.setup.profile.avatarColor') }}</p>
          <div class="d-flex flex-wrap ga-2 mb-6">
            <button
              v-for="color in AVATAR_PALETTE"
              :key="color"
              class="avatar-swatch"
              :style="{ background: color, outline: admin.avatar_color === color ? '3px solid currentColor' : 'none' }"
              :aria-label="`Select color ${color}`"
              @click="admin.avatar_color = color"
            >
              <v-icon v-if="admin.avatar_color === color" color="white" size="18">mdi-check</v-icon>
            </button>
          </div>

          <!-- PIN setup -->
          <p class="text-body-2 font-weight-medium mb-2">{{ $t('wizard.setup.profile.setPin') }}</p>
          <div class="d-flex ga-3 mb-2">
            <div
              v-for="i in 4"
              :key="i"
              class="pin-dot-sm"
              :class="{ filled: adminPin.length >= i }"
            />
          </div>
          <div class="pin-pad-sm mb-4" role="group" :aria-label="$t('wizard.setup.profile.setPin')">
            <template v-for="key in keypadKeys" :key="key">
              <v-btn
                v-if="key !== 'del'"
                class="pin-key-sm"
                variant="tonal"
                :aria-label="key === 'clr' ? 'Clear PIN' : `Enter digit ${key}`"
                :disabled="adminPin.length >= 4"
                @click="key === 'clr' ? (adminPin = '') : (adminPin += key)"
              >
                {{ key === 'clr' ? '✕' : key }}
              </v-btn>
              <v-btn
                v-else
                class="pin-key-sm"
                variant="text"
                :aria-label="$t('pin.deleteDigit')"
                :disabled="adminPin.length === 0"
                @click="adminPin = adminPin.slice(0, -1)"
              >
                <v-icon>mdi-backspace-outline</v-icon>
              </v-btn>
            </template>
          </div>

          <!-- Confirm PIN -->
          <div v-if="adminPin.length === 4">
            <p class="text-body-2 font-weight-medium mb-2">{{ $t('wizard.setup.profile.confirmPin') }}</p>
            <div class="d-flex ga-3 mb-2">
              <div
                v-for="i in 4"
                :key="i"
                class="pin-dot-sm"
                :class="{ filled: adminPinConfirm.length >= i }"
              />
            </div>
            <div class="pin-pad-sm mb-2" role="group" :aria-label="$t('wizard.setup.profile.confirmPin')">
              <template v-for="key in keypadKeys" :key="key">
                <v-btn
                  v-if="key !== 'del'"
                  class="pin-key-sm"
                  variant="tonal"
                  :aria-label="key === 'clr' ? 'Clear' : `Enter digit ${key}`"
                  :disabled="adminPinConfirm.length >= 4"
                  @click="key === 'clr' ? (adminPinConfirm = '') : (adminPinConfirm += key)"
                >
                  {{ key === 'clr' ? '✕' : key }}
                </v-btn>
                <v-btn
                  v-else
                  class="pin-key-sm"
                  variant="text"
                  :aria-label="$t('pin.deleteDigit')"
                  @click="adminPinConfirm = adminPinConfirm.slice(0, -1)"
                >
                  <v-icon>mdi-backspace-outline</v-icon>
                </v-btn>
              </template>
            </div>
            <v-alert v-if="pinMismatch" type="error" variant="tonal" density="compact" class="mb-2">
              {{ $t('wizard.setup.profile.pinMismatch') }}
            </v-alert>
          </div>

          <!-- Preferences -->
          <p class="text-body-2 font-weight-medium mt-4 mb-2">{{ $t('wizard.setup.profile.preferences') }}</p>
          <p class="text-caption text-medium-emphasis mb-3">
            {{ $t('wizard.setup.profile.preferencesSub') }}
          </p>
          <PreferenceSelector v-model="admin.preferences" />

          <WizardNav
            :can-next="canProceedStep6"
            @back="back"
            @next="next"
          />
        </div>

        <!-- ── Step 7: Co-residents ────────────────────── -->
        <div v-else-if="step === 7">
          <h2 class="text-h5 font-weight-bold mb-2">{{ $t('wizard.setup.coresidents.title') }}</h2>
          <p class="text-body-2 text-medium-emphasis mb-6">
            {{ $t('wizard.setup.coresidents.sub') }}
          </p>

          <div v-for="(res, idx) in coResidents" :key="idx" class="mb-4">
            <v-card variant="outlined" rounded="lg" class="pa-3">
              <div class="d-flex align-center mb-3">
                <span class="text-body-1 font-weight-medium flex-grow-1">
                  {{ $t('wizard.setup.coresidents.residentLabel', { n: idx + 1 }) }}
                </span>
                <v-btn
                  icon="mdi-close"
                  variant="text"
                  size="small"
                  :aria-label="`Remove resident ${idx + 1}`"
                  @click="removeCoResident(idx)"
                />
              </div>
              <v-text-field v-model="res.name" :label="$t('wizard.setup.coresidents.fullName')" density="compact" class="mb-2" />
              <v-text-field v-model="res.display_name" :label="$t('wizard.setup.coresidents.displayName')" density="compact" class="mb-2" />
              <v-select
                v-model="res.role"
                :label="$t('wizard.setup.coresidents.role')"
                :items="coResidentRoleOptions"
                density="compact"
                class="mb-3"
              />
              <!-- Color -->
              <p class="text-caption mb-1">{{ $t('wizard.setup.coresidents.avatarColor') }}</p>
              <div class="d-flex flex-wrap ga-1 mb-3">
                <button
                  v-for="color in AVATAR_PALETTE"
                  :key="color"
                  class="avatar-swatch-sm"
                  :style="{ background: color, outline: res.avatar_color === color ? '3px solid currentColor' : 'none' }"
                  :aria-label="`Select color ${color}`"
                  @click="res.avatar_color = color"
                >
                  <v-icon v-if="res.avatar_color === color" color="white" size="14">mdi-check</v-icon>
                </button>
              </div>
              <!-- Initial PIN -->
              <p class="text-caption mb-1">{{ $t('wizard.setup.coresidents.initialPin') }}</p>
              <v-text-field
                v-model="res.pin"
                type="password"
                maxlength="4"
                density="compact"
                :placeholder="$t('wizard.setup.coresidents.pinPlaceholder')"
                :rules="[v => v.length === 4 || '4 digits required']"
                inputmode="numeric"
              />
            </v-card>
          </div>

          <v-btn
            variant="tonal"
            color="primary"
            prepend-icon="mdi-plus"
            block
            class="mb-4"
            @click="addCoResident"
          >
            {{ $t('wizard.setup.coresidents.addAnother') }}
          </v-btn>

          <WizardNav :skip-label="$t('wizard.setup.coresidents.addLater')" @back="back" @next="next" @skip="next" />
        </div>

        <!-- ── Step 8: Ready ───────────────────────────── -->
        <div v-else-if="step === 8">
          <div class="text-center mb-6">
            <v-icon size="56" color="primary" class="mb-3">mdi-check-circle-outline</v-icon>
            <h2 class="text-h5 font-weight-bold mb-2">{{ $t('wizard.setup.summary.title') }}</h2>
            <p class="text-body-2 text-medium-emphasis">{{ $t('wizard.setup.summary.sub') }}</p>
          </div>

          <v-card variant="outlined" rounded="lg" class="pa-4 mb-4">
            <div class="d-flex align-center mb-2">
              <v-icon color="primary" class="mr-2">mdi-home-outline</v-icon>
              <span class="text-body-1 font-weight-medium">{{ household.name }}</span>
            </div>
            <div class="d-flex align-center mb-2">
              <v-icon color="primary" class="mr-2">mdi-account-group-outline</v-icon>
              <span class="text-body-2">{{ $t('wizard.setup.summary.residents', { n: 1 + coResidents.length }) }}</span>
            </div>
            <div class="d-flex align-center mb-2">
              <v-icon color="primary" class="mr-2">mdi-door-open</v-icon>
              <span class="text-body-2">{{ $t('wizard.setup.summary.rooms', { n: selectedRooms.length + customRooms.length }) }}</span>
            </div>
            <div class="d-flex align-center">
              <v-icon color="primary" class="mr-2">mdi-robot-vacuum</v-icon>
              <span class="text-body-2">{{ $t('wizard.setup.summary.appliances', { n: activeDeviceCount }) }}</span>
            </div>
          </v-card>

          <v-alert
            v-if="setupError"
            type="error"
            variant="tonal"
            class="mb-4"
          >
            {{ setupError }}
          </v-alert>

          <v-btn
            v-if="!catalogGenerated"
            block
            size="large"
            color="primary"
            :loading="saving"
            class="mb-3"
            @click="finishSetup"
          >
            {{ $t('wizard.setup.summary.generateCatalog') }}
          </v-btn>

          <div v-if="catalogGenerated">
            <v-alert type="success" variant="tonal" class="mb-4">
              {{ $t('wizard.setup.summary.catalogReady') }}
            </v-alert>
            <v-btn block size="large" color="primary" @click="goToApp">
              {{ $t('wizard.setup.summary.startApp') }}
            </v-btn>
          </div>
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
import { householdsApi, residentsApi, roomsApi, catalogApi } from '../../api/index.js'
import WizardNav from '../../components/wizard/WizardNav.vue'
import PreferenceSelector from '../../components/wizard/PreferenceSelector.vue'

const { t } = useI18n()
const router = useRouter()
const themeStore = useThemeStore()
const residentStore = useResidentStore()

const TOTAL_STEPS = 8
const step = ref(1)
const saving = ref(false)
const setupError = ref('')
const catalogGenerated = ref(false)

const progressPct = computed(() => ((step.value - 1) / (TOTAL_STEPS - 1)) * 100)

// ── Household ──
const household = ref({
  name: '',
  timezone: null,
  has_children: false,
  has_cats: false,
  has_dogs: false,
  has_garden: false,
  has_robot_vacuum: false,
  has_robot_mop: false,
  has_dishwasher: false,
  has_washing_machine: false,
  has_dryer: false,
  has_window_cleaner: false,
  has_steam_cleaner: false,
  has_robot_lawn_mower: false,
  has_irrigation_system: false,
})

const timezones = [
  'Europe/Berlin', 'Europe/London', 'Europe/Paris', 'America/New_York',
  'America/Chicago', 'America/Los_Angeles', 'Asia/Tokyo', 'Australia/Sydney',
]

const compositionFlags = computed(() => [
  { key: 'has_children', label: t('wizard.setup.composition.children'), icon: 'mdi-human-child' },
  { key: 'has_cats',     label: t('wizard.setup.composition.cats'),     icon: 'mdi-cat' },
  { key: 'has_dogs',     label: t('wizard.setup.composition.dogs'),     icon: 'mdi-dog' },
  { key: 'has_garden',   label: t('wizard.setup.composition.garden'),   icon: 'mdi-flower' },
])

const allDeviceFlags = computed(() => [
  { key: 'has_robot_vacuum',      label: t('wizard.setup.appliances.robotVacuum'),    icon: 'mdi-robot-vacuum', gardenOnly: false },
  { key: 'has_robot_mop',         label: t('wizard.setup.appliances.robotMop'),       icon: 'mdi-robot-vacuum-variant', gardenOnly: false },
  { key: 'has_dishwasher',        label: t('wizard.setup.appliances.dishwasher'),     icon: 'mdi-dishwasher', gardenOnly: false },
  { key: 'has_washing_machine',   label: t('wizard.setup.appliances.washer'),         icon: 'mdi-washing-machine', gardenOnly: false },
  { key: 'has_dryer',             label: t('wizard.setup.appliances.dryer'),          icon: 'mdi-tumble-dryer', gardenOnly: false },
  { key: 'has_window_cleaner',    label: t('wizard.setup.appliances.windowCleaner'),  icon: 'mdi-window-open-variant', gardenOnly: false },
  { key: 'has_steam_cleaner',     label: t('wizard.setup.appliances.steamCleaner'),   icon: 'mdi-waves', gardenOnly: false },
  { key: 'has_robot_lawn_mower',  label: t('wizard.setup.appliances.robotMower'),     icon: 'mdi-robot-mower', gardenOnly: true },
  { key: 'has_irrigation_system', label: t('wizard.setup.appliances.irrigation'),     icon: 'mdi-sprinkler', gardenOnly: true },
])

const visibleDeviceFlags = computed(() =>
  allDeviceFlags.value.filter((d) => !d.gardenOnly || household.value.has_garden)
)

const activeDeviceCount = computed(() =>
  allDeviceFlags.value.filter((d) => household.value[d.key]).length
)

// ── Children age groups ──
const childAges = ref([])
const childAgeGroups = computed(() => [
  { label: t('wizard.setup.composition.baby'),    value: 'baby' },
  { label: t('wizard.setup.composition.toddler'), value: 'toddler' },
  { label: t('wizard.setup.composition.school'),  value: 'school' },
])

function toggleAge(v) {
  const i = childAges.value.indexOf(v)
  if (i >= 0) childAges.value.splice(i, 1)
  else childAges.value.push(v)
}

// ── Rooms ──
const roomTemplates = [
  { name: 'Kitchen',         icon: 'mdi-countertop-outline',  gardenOnly: false },
  { name: 'Living Room',     icon: 'mdi-sofa-outline',         gardenOnly: false },
  { name: 'Bathroom',        icon: 'mdi-shower-head',          gardenOnly: false },
  { name: 'Bedroom',         icon: 'mdi-bed-outline',          gardenOnly: false },
  { name: 'Hallway',         icon: 'mdi-door-open',            gardenOnly: false },
  { name: "Children's Room", icon: 'mdi-toy-brick-outline',    gardenOnly: false },
  { name: 'Garden',          icon: 'mdi-flower-outline',       gardenOnly: true },
]
const visibleRoomTemplates = computed(() =>
  roomTemplates.filter((r) => !r.gardenOnly || household.value.has_garden)
)
const selectedRooms = ref(['Kitchen', 'Living Room', 'Bathroom', 'Bedroom'])
const customRooms = ref([])
const customRoomInput = ref('')

function toggleRoom(name) {
  const i = selectedRooms.value.indexOf(name)
  if (i >= 0) selectedRooms.value.splice(i, 1)
  else selectedRooms.value.push(name)
}

function addCustomRoom() {
  const n = customRoomInput.value.trim()
  if (n && !customRooms.value.includes(n)) {
    customRooms.value.push(n)
    customRoomInput.value = ''
  }
}

function removeCustomRoom(r) {
  customRooms.value = customRooms.value.filter((x) => x !== r)
}

// ── Admin resident ──
const AVATAR_PALETTE = ['#5c7a7a','#7a5c6e','#6e7a5c','#5c6e7a','#7a6e5c','#7a5c5c','#5c7a6e','#6a5c7a']

const admin = ref({
  name: '',
  display_name: '',
  avatar_color: AVATAR_PALETTE[0],
  preferences: {},
})

const adminPin = ref('')
const adminPinConfirm = ref('')
const pinMismatch = computed(() =>
  adminPinConfirm.value.length === 4 && adminPin.value !== adminPinConfirm.value
)
const canProceedStep6 = computed(() =>
  admin.value.name.trim() &&
  admin.value.display_name.trim() &&
  adminPin.value.length === 4 &&
  adminPinConfirm.value.length === 4 &&
  !pinMismatch.value
)

const keypadKeys = ['1','2','3','4','5','6','7','8','9','clr','0','del']

// ── Co-residents ──
const coResidents = ref([])

const coResidentRoleOptions = computed(() => [
  { title: t('settings.roles.edit'), value: 'edit' },
  { title: t('settings.roles.view'), value: 'view' },
])

function addCoResident() {
  coResidents.value.push({
    name: '', display_name: '', role: 'edit',
    avatar_color: AVATAR_PALETTE[coResidents.value.length % AVATAR_PALETTE.length],
    pin: '',
  })
}

function removeCoResident(idx) {
  coResidents.value.splice(idx, 1)
}

// ── Navigation ──
function next() { if (step.value < TOTAL_STEPS) step.value++ }
function back() { if (step.value > 1) step.value-- }

// ── Finish setup ──
let householdId = null
let adminResidentId = null

async function finishSetup() {
  saving.value = true
  setupError.value = ''
  try {
    // 1. Create household
    const hhRes = await householdsApi.create({
      name: household.value.name,
      timezone: household.value.timezone,
      has_children: household.value.has_children,
      has_cats: household.value.has_cats,
      has_dogs: household.value.has_dogs,
      has_garden: household.value.has_garden,
      has_robot_vacuum: household.value.has_robot_vacuum,
      has_robot_mop: household.value.has_robot_mop,
      has_dishwasher: household.value.has_dishwasher,
      has_washing_machine: household.value.has_washing_machine,
      has_dryer: household.value.has_dryer,
      has_window_cleaner: household.value.has_window_cleaner,
      has_steam_cleaner: household.value.has_steam_cleaner,
      has_robot_lawn_mower: household.value.has_robot_lawn_mower,
      has_irrigation_system: household.value.has_irrigation_system,
    })
    householdId = hhRes.data.id

    // 2. Bootstrap first admin resident — no PIN required (unprotected endpoint)
    const adminRes = await residentsApi.bootstrap({
      household_id: householdId,
      name: admin.value.name,
      display_name: admin.value.display_name,
      color: admin.value.avatar_color,
      role: 'admin',
      pin: adminPin.value,
    })
    adminResidentId = adminRes.data.id

    // Set active resident immediately so the Axios interceptor injects
    // X-Resident-ID on all subsequent calls (catalog, rooms, co-residents, etc.)
    residentStore.setActiveResident(adminResidentId)

    // Store PIN in memory so subsequent calls work (resident now exists)
    const pinStore = (await import('../../stores/pin.js')).usePinStore()
    pinStore.setPin(adminResidentId, adminPin.value)

    // 3. Set preferences for admin
    const prefs = admin.value.preferences
    for (const [category, pref] of Object.entries(prefs)) {
      if (pref && pref !== 'neutral') {
        await residentsApi.setPreference(adminResidentId, { task_category: category, preference: pref }, adminPin.value)
      }
    }

    // 4. Create rooms
    const allRooms = [...selectedRooms.value, ...customRooms.value]
    for (const roomName of allRooms) {
      await roomsApi.create(householdId, {
        name: roomName,
        room_type: roomTypeFor(roomName),
        is_active: true,
      }, adminPin.value)
    }

    // 5. Create co-residents (authenticated as admin)
    for (const res of coResidents.value) {
      if (res.name && res.display_name && res.pin.length === 4) {
        await residentsApi.create({
          household_id: householdId,
          name: res.name,
          display_name: res.display_name,
          color: res.avatar_color,
          role: res.role,
          pin: res.pin,
        }, adminPin.value)
      }
    }

    // 6. Generate catalog
    await catalogApi.generate(householdId, adminPin.value)
    catalogGenerated.value = true

    // 7. Mark admin setup complete
    await residentsApi.update(adminResidentId, { setup_complete: true }, adminPin.value)

    // Activate resident in store
    await residentStore.loadResidents(householdId)
    residentStore.setActiveResident(adminResidentId)

  } catch (e) {
    setupError.value = e.userMessage || t('errors.somethingWrong')
  } finally {
    saving.value = false
  }
}

function goToApp() {
  router.push('/')
}

function roomTypeFor(name) {
  const map = {
    'Kitchen': 'kitchen', 'Living Room': 'living_room', 'Bathroom': 'bathroom',
    'Bedroom': 'bedroom', 'Hallway': 'hallway', "Children's Room": 'childrens_room',
    'Garden': 'garden',
  }
  return map[name] || 'other'
}
</script>

<style scoped>
.pin-dot-sm {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid rgb(var(--v-theme-primary));
  background: transparent;
  transition: background 0.15s ease;
  display: inline-block;
  margin-right: 8px;
}
.pin-dot-sm.filled { background: rgb(var(--v-theme-primary)); }

.pin-pad-sm {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  max-width: 280px;
  margin-bottom: 8px;
}
.pin-key-sm { height: 52px !important; font-size: 1.1rem; }

.avatar-swatch {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 44px;
}

.avatar-swatch-sm {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  min-height: 36px;
}
</style>
