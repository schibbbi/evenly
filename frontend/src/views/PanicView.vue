<!-- Panic Mode Screen
     3-step flow: Select time → Select available residents → View & execute plan.
     Tasks grouped by resident, ordered by priority room. Progress bar.
-->
<template>
  <AppLayout>
    <!-- Step indicator -->
    <div class="d-flex align-center mb-4">
      <v-btn
        v-if="step > 1 && !planActive"
        icon="mdi-arrow-left"
        variant="text"
        size="small"
        aria-label="Go back"
        @click="step--"
        class="mr-2"
      />
      <h1 class="text-h5 font-weight-bold">{{ $t('panic.title') }}</h1>
      <v-spacer />
      <span v-if="step < 3" class="text-caption text-medium-emphasis">{{ $t('panic.stepIndicator', { current: step }) }}</span>
    </div>

    <v-alert
      v-if="step < 3"
      type="info"
      variant="tonal"
      density="compact"
      class="mb-4"
      icon="mdi-alert-outline"
    >
      {{ $t('panic.info') }}
    </v-alert>

    <!-- ── Step 1: Select time ─────────────────────────── -->
    <div v-if="step === 1">
      <p class="text-body-2 text-medium-emphasis mb-4">{{ $t('panic.stepTime') }}</p>
      <div class="d-flex flex-wrap ga-3 mb-8">
        <v-btn
          v-for="opt in timeOptions"
          :key="opt.value"
          :variant="selectedMinutes === opt.value ? 'flat' : 'outlined'"
          :color="selectedMinutes === opt.value ? 'primary' : undefined"
          class="time-btn"
          size="large"
          :aria-pressed="selectedMinutes === opt.value"
          :aria-label="`${opt.label}`"
          @click="selectedMinutes = opt.value"
        >
          {{ opt.label }}
        </v-btn>
      </div>
      <v-btn
        block
        size="large"
        color="primary"
        :disabled="!selectedMinutes"
        append-icon="mdi-arrow-right"
        @click="step = 2"
      >
        {{ $t('common.continue') }}
      </v-btn>
    </div>

    <!-- ── Step 2: Select residents ───────────────────── -->
    <div v-else-if="step === 2">
      <p class="text-body-2 text-medium-emphasis mb-4">{{ $t('panic.stepResidents') }}</p>
      <v-list class="mb-6">
        <v-list-item
          v-for="r in residentStore.residents"
          :key="r.id"
          rounded="lg"
          class="mb-1"
          :class="{ 'bg-primary-container': selectedResidents.includes(r.id) }"
        >
          <template #prepend>
            <v-checkbox
              :model-value="selectedResidents.includes(r.id)"
              :aria-label="`Include ${r.display_name}`"
              hide-details
              color="primary"
              @update:model-value="toggleResident(r.id)"
            />
          </template>
          <template #default>
            <div class="d-flex align-center ga-3">
              <ResidentAvatar :resident="r" size="36" />
              <span class="text-body-1">{{ r.display_name }}</span>
            </div>
          </template>
        </v-list-item>
      </v-list>

      <v-alert v-if="panicError" type="error" variant="tonal" density="compact" class="mb-3">
        {{ panicError }}
      </v-alert>

      <v-btn
        block
        size="large"
        color="primary"
        :disabled="selectedResidents.length === 0"
        :loading="generating"
        prepend-icon="mdi-lightning-bolt"
        @click="generatePlan"
      >
        {{ $t('panic.generatePlan') }}
      </v-btn>
    </div>

    <!-- ── Step 3: View & execute plan ────────────────── -->
    <div v-else-if="step === 3 && panicSession">
      <!-- Progress -->
      <div class="mb-4">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-body-2 font-weight-medium">{{ $t('panic.progress') }}</span>
          <span class="text-body-2 text-medium-emphasis">
            {{ $t('panic.taskCount', { done: completedCount, total: totalTaskCount }) }}
          </span>
        </div>
        <v-progress-linear
          :model-value="progressPct"
          color="primary"
          rounded
          height="8"
          :aria-label="`${completedCount} of ${totalTaskCount} tasks completed`"
        />
      </div>

      <!-- All done -->
      <div v-if="progressPct === 100" class="text-center py-6">
        <v-icon size="56" color="success" class="mb-3">mdi-check-circle</v-icon>
        <p class="text-h6 font-weight-bold mb-2">{{ $t('panic.allDoneTitle') }}</p>
        <p class="text-body-2 text-medium-emphasis mb-4">{{ $t('panic.allDoneSub') }}</p>
        <v-btn color="primary" @click="router.push('/')">{{ $t('panic.backToHome') }}</v-btn>
      </div>

      <!-- Task groups by resident -->
      <div v-else>
        <div
          v-for="group in taskGroups"
          :key="group.residentId"
          class="mb-5"
        >
          <div class="d-flex align-center ga-2 mb-2">
            <ResidentAvatar :resident="residentFor(group.residentId)" size="32" />
            <span class="text-body-1 font-weight-medium">
              {{ residentName(group.residentId) }}
            </span>
          </div>
          <v-card
            v-for="task in group.tasks"
            :key="task.assignment_id"
            :variant="task.done ? 'tonal' : 'outlined'"
            :color="task.done ? 'success' : undefined"
            rounded="xl"
            class="mb-2 pa-3"
          >
            <div class="d-flex align-center ga-3">
              <v-checkbox
                :model-value="task.done"
                :aria-label="`Mark ${task.task_name} as done`"
                hide-details
                color="success"
                density="compact"
                @update:model-value="markTaskDone(task)"
              />
              <div class="flex-grow-1">
                <p
                  class="text-body-2 font-weight-medium"
                  :class="{ 'text-decoration-line-through text-medium-emphasis': task.done }"
                >
                  {{ task.task_name }}
                </p>
                <p class="text-caption text-medium-emphasis">
                  {{ task.room_name }} · ~{{ task.estimated_minutes || 15 }} min
                </p>
              </div>
            </div>
          </v-card>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useResidentStore } from '../stores/resident.js'
import { panicApi } from '../api/index.js'
import AppLayout from '../components/layout/AppLayout.vue'
import ResidentAvatar from '../components/shared/ResidentAvatar.vue'

const { t }         = useI18n()
const router        = useRouter()
const residentStore = useResidentStore()

const step              = ref(1)
const selectedMinutes   = ref(null)
const selectedResidents = ref([residentStore.activeResidentId].filter(Boolean))
const generating        = ref(false)
const panicError        = ref('')
const panicSession      = ref(null)
const taskGroups        = ref([])   // [{ residentId, tasks: [{...}] }]
const planActive        = ref(false)

const timeOptions = computed(() => [
  { value: 120, label: t('panic.time.2h') },
  { value: 180, label: t('panic.time.3h') },
  { value: 240, label: t('panic.time.4h') },
])

function toggleResident(id) {
  const i = selectedResidents.value.indexOf(id)
  if (i >= 0) selectedResidents.value.splice(i, 1)
  else selectedResidents.value.push(id)
}

async function generatePlan() {
  generating.value = true
  panicError.value = ''
  try {
    const res = await panicApi.activate({
      available_minutes: selectedMinutes.value,
      resident_ids: selectedResidents.value,
    })
    panicSession.value = res.data
    buildTaskGroups(res.data)
    step.value = 3
    planActive.value = true
  } catch (e) {
    panicError.value = e.userMessage || t('panic.generateFailed')
  } finally {
    generating.value = false
  }
}

function buildTaskGroups(session) {
  // Backend returns assignments grouped — build from flat assignment list
  const assignments = session.assignments || []
  const groupMap = {}
  for (const a of assignments) {
    const rid = a.resident_id || selectedResidents.value[0]
    if (!groupMap[rid]) groupMap[rid] = []
    groupMap[rid].push({ ...a, done: a.status === 'completed' })
  }
  taskGroups.value = Object.entries(groupMap).map(([rid, tasks]) => ({
    residentId: parseInt(rid),
    tasks,
  }))
}

const totalTaskCount = computed(() =>
  taskGroups.value.reduce((s, g) => s + g.tasks.length, 0)
)
const completedCount = computed(() =>
  taskGroups.value.reduce((s, g) => s + g.tasks.filter((t) => t.done).length, 0)
)
const progressPct = computed(() =>
  totalTaskCount.value === 0 ? 0 : Math.round((completedCount.value / totalTaskCount.value) * 100)
)

async function markTaskDone(task) {
  if (task.done) return
  task.done = true
  // Individual task completion uses the regular assignments endpoint
  // (panic assignments have a panic_session_id, status is updated via the same flow)
  // The panic session /complete endpoint marks the whole session done — called only when 100% complete.
  try {
    await import('../api/index.js').then(({ assignmentsApi }) =>
      assignmentsApi.complete(task.assignment_id || task.id)
    )
  } catch (_) {
    // Non-critical — task is marked done locally; backend sync is best-effort
  }
  // If all tasks are done, mark the session complete
  if (completedCount.value >= totalTaskCount.value && panicSession.value) {
    try {
      await panicApi.complete(panicSession.value.id)
    } catch (_) {}
  }
}

function residentFor(id) {
  return residentStore.residents.find((r) => r.id === id) || null
}

function residentName(id) {
  return residentFor(id)?.display_name || t('panic.resident')
}
</script>

<style scoped>
.time-btn {
  min-width: 100px !important;
  height: 64px !important;
  font-size: 1rem !important;
}
</style>
