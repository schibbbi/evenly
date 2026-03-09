<!-- Household Settings Screen
     Role-gated: PIN required on entry.
     Admin: residents, roles, rooms, devices, catalog, calendar.
     Edit: task catalog browse/activate.
     View: read-only, admin controls hidden.
-->
<template>
  <AppLayout>
    <!-- PIN gate — shown until PIN is verified -->
    <div v-if="!unlocked" class="text-center py-10">
      <v-icon size="48" color="primary" class="mb-3" aria-hidden="true">mdi-lock-outline</v-icon>
      <h1 class="text-h5 font-weight-bold mb-2">{{ $t('settings.unlockTitle') }}</h1>
      <p class="text-body-2 text-medium-emphasis mb-6">
        {{ $t('settings.unlockSub') }}
      </p>
      <v-btn color="primary" size="large" @click="showPinSheet = true">
        {{ $t('settings.unlockBtn') }}
      </v-btn>

      <PinBottomSheet
        v-model="showPinSheet"
        :title="$t('settings.pinSheetTitle')"
        :subtitle="$t('settings.pinSheetSub')"
        :resident-id="residentStore.activeResidentId"
        @success="onPinSuccess"
        @cancel="router.push('/')"
      />
    </div>

    <!-- Settings content (unlocked) -->
    <div v-else>
      <h1 class="text-h5 font-weight-bold mb-4">{{ $t('settings.title') }}</h1>

      <!-- ── ADMIN ONLY sections ───────────────────────── -->
      <template v-if="residentStore.isAdmin">
        <!-- Residents -->
        <v-card variant="outlined" rounded="xl" class="mb-4">
          <v-card-title class="text-subtitle-1 pa-4 pb-0">{{ $t('settings.residents') }}</v-card-title>
          <v-list density="compact" class="pa-2">
            <v-list-item
              v-for="r in residentStore.residents"
              :key="r.id"
              rounded="lg"
            >
              <template #prepend>
                <ResidentAvatar :resident="r" size="36" class="mr-3" />
              </template>
              <v-list-item-title class="text-body-2">{{ r.display_name }}</v-list-item-title>
              <v-list-item-subtitle class="text-caption">{{ r.name }} · {{ r.role }}</v-list-item-subtitle>
              <template #append>
                <v-btn
                  icon="mdi-pencil-outline"
                  size="small"
                  variant="text"
                  :aria-label="`${$t('common.edit')} ${r.display_name}`"
                  @click="openEditResident(r)"
                />
              </template>
            </v-list-item>
          </v-list>
          <div class="pa-3 pt-0">
            <v-btn
              block
              variant="tonal"
              color="primary"
              prepend-icon="mdi-account-plus-outline"
              @click="openAddResident"
            >
              {{ $t('settings.addResident') }}
            </v-btn>
          </div>
        </v-card>

        <!-- Rooms -->
        <v-card variant="outlined" rounded="xl" class="mb-4">
          <v-card-title class="text-subtitle-1 pa-4 pb-0">{{ $t('settings.rooms') }}</v-card-title>
          <v-list density="compact" class="pa-2">
            <v-list-item
              v-for="room in rooms"
              :key="room.id"
              rounded="lg"
            >
              <v-list-item-title class="text-body-2">{{ room.name }}</v-list-item-title>
              <template #append>
                <v-switch
                  :model-value="room.is_active"
                  color="primary"
                  density="compact"
                  hide-details
                  :aria-label="`${room.name} active`"
                  @update:model-value="toggleRoom(room)"
                />
              </template>
            </v-list-item>
          </v-list>
          <div class="pa-3 pt-0">
            <v-btn
              block
              variant="tonal"
              color="primary"
              prepend-icon="mdi-plus"
              @click="openAddRoom"
            >
              {{ $t('settings.addRoom') }}
            </v-btn>
          </div>
        </v-card>

        <!-- Devices -->
        <v-card variant="outlined" rounded="xl" class="mb-4">
          <v-card-title class="text-subtitle-1 pa-4 pb-0">{{ $t('settings.devices') }}</v-card-title>
          <v-list density="compact" class="pa-2">
            <v-list-item
              v-for="device in devices"
              :key="device.id"
              rounded="lg"
            >
              <v-list-item-title class="text-body-2">{{ device.name }}</v-list-item-title>
              <v-list-item-subtitle class="text-caption">{{ device.device_type }}</v-list-item-subtitle>
              <template #append>
                <v-btn
                  icon="mdi-delete-outline"
                  size="small"
                  variant="text"
                  color="error"
                  :aria-label="`Remove ${device.name}`"
                  @click="deleteDevice(device)"
                />
              </template>
            </v-list-item>
          </v-list>
        </v-card>

        <!-- Calendar -->
        <v-card variant="outlined" rounded="xl" class="mb-4">
          <v-card-title class="text-subtitle-1 pa-4 pb-2">{{ $t('settings.calendar') }}</v-card-title>
          <v-card-text class="text-body-2 text-medium-emphasis">
            {{ $t('settings.calendarDesc') }}
          </v-card-text>
          <v-card-actions class="pa-4 pt-0">
            <v-btn variant="outlined" prepend-icon="mdi-calendar-sync" @click="syncCalendar">
              {{ $t('settings.syncCalendar') }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </template>

      <!-- ── EDIT + ADMIN section: Task catalog ───────── -->
      <template v-if="residentStore.isEdit || residentStore.isAdmin">
        <v-card variant="outlined" rounded="xl" class="mb-4">
          <v-card-title class="text-subtitle-1 pa-4 pb-0">{{ $t('settings.taskCatalog') }}</v-card-title>

          <div v-if="catalogLoading" class="pa-4">
            <v-skeleton-loader type="list-item-two-line" />
          </div>

          <v-list density="compact" class="pa-2" v-else>
            <v-list-item
              v-for="task in catalog"
              :key="task.id"
              rounded="lg"
            >
              <v-list-item-title class="text-body-2">{{ task.name }}</v-list-item-title>
              <v-list-item-subtitle class="text-caption">{{ task.category }}</v-list-item-subtitle>
              <template #append>
                <v-switch
                  :model-value="task.is_active"
                  color="primary"
                  density="compact"
                  hide-details
                  :aria-label="`${task.name} active`"
                  @update:model-value="toggleTask(task)"
                />
              </template>
            </v-list-item>
          </v-list>

          <!-- Regenerate (admin only) -->
          <div v-if="residentStore.isAdmin" class="pa-3 pt-0">
            <v-btn
              block
              variant="tonal"
              color="warning"
              prepend-icon="mdi-refresh"
              :loading="regenerating"
              @click="confirmRegenerate"
            >
              {{ $t('settings.regenerateCatalog') }}
            </v-btn>
            <p class="text-caption text-medium-emphasis text-center mt-1">
              {{ $t('settings.regenerateInfo') }}
            </p>
          </div>
        </v-card>
      </template>

      <!-- Regenerate confirmation snackbar -->
      <v-snackbar v-model="showRegenConfirm" :timeout="-1" location="bottom" max-width="480">
        {{ $t('settings.regenerateConfirm') }}
        <template #actions>
          <v-btn variant="text" @click="showRegenConfirm = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="warning" variant="text" :loading="regenerating" @click="regenerateCatalog">
            {{ $t('common.regenerate') }}
          </v-btn>
        </template>
      </v-snackbar>

      <!-- Add resident sheet -->
      <v-bottom-sheet v-model="showAddResidentSheet" max-width="480">
        <v-card rounded="t-xl" class="pa-4">
          <v-card-title class="text-h6 mb-3">
            {{ editingResident ? $t('settings.editResident') : $t('settings.addResident') }}
          </v-card-title>
          <v-text-field v-model="residentForm.name" :label="$t('settings.fullName')" class="mb-2" />
          <v-text-field v-model="residentForm.display_name" :label="$t('settings.displayName')" class="mb-2" />
          <v-select
            v-model="residentForm.role"
            :label="$t('settings.role')"
            :items="roleOptions"
            class="mb-3"
          />
          <div v-if="!editingResident" class="mb-3">
            <p class="text-body-2 font-weight-medium mb-1">{{ $t('settings.initialPin') }}</p>
            <v-text-field
              v-model="residentForm.pin"
              type="password"
              maxlength="4"
              inputmode="numeric"
              :placeholder="$t('settings.initialPinPlaceholder')"
              density="compact"
            />
          </div>
          <v-alert v-if="residentFormError" type="error" variant="tonal" density="compact" class="mb-3">
            {{ residentFormError }}
          </v-alert>
          <div class="d-flex ga-2">
            <v-btn variant="text" class="flex-grow-1" @click="showAddResidentSheet = false">{{ $t('common.cancel') }}</v-btn>
            <v-btn color="primary" class="flex-grow-1" :loading="savingResident" @click="saveResident">
              {{ $t('common.save') }}
            </v-btn>
          </div>
        </v-card>
      </v-bottom-sheet>

      <!-- Add room sheet -->
      <v-bottom-sheet v-model="showAddRoomSheet" max-width="480">
        <v-card rounded="t-xl" class="pa-4">
          <v-card-title class="text-h6 mb-3">{{ $t('settings.addRoom') }}</v-card-title>
          <v-text-field v-model="newRoomName" :label="$t('settings.roomName')" class="mb-3" />
          <v-select
            v-model="newRoomType"
            :label="$t('settings.roomType')"
            :items="roomTypeOptions"
            class="mb-3"
          />
          <v-alert v-if="roomError" type="error" variant="tonal" density="compact" class="mb-3">
            {{ roomError }}
          </v-alert>
          <div class="d-flex ga-2">
            <v-btn variant="text" class="flex-grow-1" @click="showAddRoomSheet = false">{{ $t('common.cancel') }}</v-btn>
            <v-btn color="primary" class="flex-grow-1" :loading="savingRoom" @click="saveRoom">
              {{ $t('settings.addRoomBtn') }}
            </v-btn>
          </div>
        </v-card>
      </v-bottom-sheet>

      <!-- Error -->
      <v-alert v-if="errorMsg" type="error" variant="tonal" density="compact" class="mt-2">
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
import { usePinStore } from '../stores/pin.js'
import { roomsApi, devicesApi, catalogApi, residentsApi, calendarApi, householdsApi } from '../api/index.js'
import AppLayout from '../components/layout/AppLayout.vue'
import ResidentAvatar from '../components/shared/ResidentAvatar.vue'
import PinBottomSheet from '../components/shared/PinBottomSheet.vue'

const { t } = useI18n()
const router         = useRouter()
const residentStore  = useResidentStore()
const pinStore       = usePinStore()

const unlocked     = ref(false)
const showPinSheet = ref(false)
const errorMsg     = ref('')

const rooms    = ref([])
const devices  = ref([])
const catalog  = ref([])
const catalogLoading = ref(false)
const regenerating = ref(false)
const showRegenConfirm = ref(false)

// Resident form
const showAddResidentSheet = ref(false)
const editingResident = ref(null)
const savingResident  = ref(false)
const residentFormError = ref('')
const residentForm = ref({ name: '', display_name: '', role: 'edit', pin: '' })

// Room form
const showAddRoomSheet = ref(false)
const newRoomName = ref('')
const newRoomType = ref('other')
const savingRoom  = ref(false)
const roomError   = ref('')

const roleOptions = computed(() => [
  { title: t('settings.roles.admin'), value: 'admin' },
  { title: t('settings.roles.editFull'), value: 'edit' },
  { title: t('settings.roles.viewFull'), value: 'view' },
])

const roomTypeOptions = computed(() => [
  { title: t('settings.roomTypes.kitchen'),        value: 'kitchen' },
  { title: t('settings.roomTypes.bathroom'),       value: 'bathroom' },
  { title: t('settings.roomTypes.bedroom'),        value: 'bedroom' },
  { title: t('settings.roomTypes.living_room'),    value: 'living_room' },
  { title: t('settings.roomTypes.hallway'),        value: 'hallway' },
  { title: t('settings.roomTypes.childrens_room'), value: 'childrens_room' },
  { title: t('settings.roomTypes.garden'),         value: 'garden' },
  { title: t('settings.roomTypes.other'),          value: 'other' },
])

let householdId = null

function onPinSuccess() {
  unlocked.value = true
  loadSettingsData()
}

async function loadSettingsData() {
  try {
    const hhRes = await householdsApi.list()
    householdId = hhRes.data[0]?.id
    if (!householdId) return

    const [roomsRes, devicesRes] = await Promise.allSettled([
      roomsApi.list(householdId),
      devicesApi.list(householdId),
    ])
    if (roomsRes.status === 'fulfilled') rooms.value = roomsRes.value.data || []
    if (devicesRes.status === 'fulfilled') devices.value = devicesRes.value.data || []

    // Catalog
    catalogLoading.value = true
    try {
      const catRes = await catalogApi.list()
      catalog.value = catRes.data || []
    } finally {
      catalogLoading.value = false
    }
  } catch (e) {
    errorMsg.value = e.userMessage || t('errors.loadFailed')
  }
}

async function toggleRoom(room) {
  const pin = pinStore.getPinForResident(residentStore.activeResidentId)
  try {
    const res = await roomsApi.update(room.id, { is_active: !room.is_active }, pin)
    const idx = rooms.value.findIndex((r) => r.id === room.id)
    if (idx >= 0) rooms.value[idx] = res.data
  } catch (e) {
    errorMsg.value = e.userMessage
  }
}

async function toggleTask(task) {
  const pin = pinStore.getPinForResident(residentStore.activeResidentId)
  try {
    const res = await catalogApi.update(task.id, { is_active: !task.is_active }, pin)
    const idx = catalog.value.findIndex((t) => t.id === task.id)
    if (idx >= 0) catalog.value[idx] = res.data
  } catch (e) {
    errorMsg.value = e.userMessage
  }
}

function confirmRegenerate() {
  showRegenConfirm.value = true
}

async function regenerateCatalog() {
  regenerating.value = true
  const pin = pinStore.getPinForResident(residentStore.activeResidentId)
  try {
    await catalogApi.generate(householdId, pin)
    const catRes = await catalogApi.list()
    catalog.value = catRes.data || []
  } catch (e) {
    errorMsg.value = e.userMessage
  } finally {
    regenerating.value = false
    showRegenConfirm.value = false
  }
}

async function deleteDevice(device) {
  const pin = pinStore.getPinForResident(residentStore.activeResidentId)
  try {
    await devicesApi.delete(device.id, pin)
    devices.value = devices.value.filter((d) => d.id !== device.id)
  } catch (e) {
    errorMsg.value = e.userMessage
  }
}

function openAddResident() {
  editingResident.value = null
  residentForm.value = { name: '', display_name: '', role: 'edit', pin: '' }
  residentFormError.value = ''
  showAddResidentSheet.value = true
}

function openEditResident(r) {
  editingResident.value = r
  residentForm.value = { name: r.name, display_name: r.display_name, role: r.role, pin: '' }
  residentFormError.value = ''
  showAddResidentSheet.value = true
}

async function saveResident() {
  savingResident.value = true
  residentFormError.value = ''
  const pin = pinStore.getPinForResident(residentStore.activeResidentId)
  try {
    if (editingResident.value) {
      const res = await residentsApi.update(editingResident.value.id, {
        name: residentForm.value.name,
        display_name: residentForm.value.display_name,
        role: residentForm.value.role,
      }, pin)
      const idx = residentStore.residents.findIndex((r) => r.id === editingResident.value.id)
      if (idx >= 0) residentStore.residents[idx] = res.data
    } else {
      const res = await residentsApi.create({
        household_id: householdId,
        name: residentForm.value.name,
        display_name: residentForm.value.display_name,
        color: residentForm.value.avatar_color || '#5c7a7a',
        role: residentForm.value.role,
        pin: residentForm.value.pin,
      }, pin)
      residentStore.residents.push(res.data)
    }
    showAddResidentSheet.value = false
  } catch (e) {
    residentFormError.value = e.userMessage || t('errors.saveFailed')
  } finally {
    savingResident.value = false
  }
}

function openAddRoom() {
  newRoomName.value = ''
  newRoomType.value = 'other'
  roomError.value = ''
  showAddRoomSheet.value = true
}

async function saveRoom() {
  savingRoom.value = true
  roomError.value = ''
  const pin = pinStore.getPinForResident(residentStore.activeResidentId)
  try {
    const res = await roomsApi.create(householdId, {
      name: newRoomName.value,
      room_type: newRoomType.value,
      is_active: true,
    }, pin)
    rooms.value.push(res.data)
    showAddRoomSheet.value = false
  } catch (e) {
    roomError.value = e.userMessage || t('errors.saveFailed')
  } finally {
    savingRoom.value = false
  }
}

async function syncCalendar() {
  const pin = pinStore.getPinForResident(residentStore.activeResidentId)
  try {
    await calendarApi.sync()
  } catch (e) {
    errorMsg.value = e.userMessage || t('errors.somethingWrong')
  }
}

onMounted(() => {
  // Check if PIN already valid from a previous action
  const pin = pinStore.getPinForResident(residentStore.activeResidentId)
  if (pin) {
    unlocked.value = true
    loadSettingsData()
  }
})
</script>
