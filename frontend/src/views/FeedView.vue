<!-- Activity Feed Screen
     Chronological list of household actions.
     Filter: All / Mine.
-->
<template>
  <AppLayout>
    <div class="d-flex align-center justify-space-between mb-4">
      <h1 class="text-h5 font-weight-bold">{{ $t('feed.title') }}</h1>
      <v-btn-toggle
        v-model="filter"
        mandatory
        color="primary"
        variant="outlined"
        density="compact"
        rounded="lg"
        :aria-label="$t('feed.filterAriaLabel')"
      >
        <v-btn value="all" :aria-label="$t('feed.filterAll')">{{ $t('feed.filterAll') }}</v-btn>
        <v-btn value="mine" :aria-label="$t('feed.filterMine')">{{ $t('feed.filterMine') }}</v-btn>
      </v-btn-toggle>
    </div>

    <!-- Loading -->
    <div v-if="loading">
      <v-skeleton-loader
        v-for="i in 5"
        :key="i"
        type="list-item-avatar-two-line"
        class="mb-2"
      />
    </div>

    <!-- Empty state -->
    <div v-else-if="filteredEntries.length === 0" class="text-center py-10">
      <v-icon size="48" class="text-medium-emphasis mb-3">mdi-history</v-icon>
      <p class="text-body-2 text-medium-emphasis">
        {{ filter === 'mine' ? $t('feed.emptyMine') : $t('feed.emptyAll') }}
      </p>
    </div>

    <!-- Feed list -->
    <div v-else>
      <v-card
        v-for="entry in filteredEntries"
        :key="entry.id"
        variant="outlined"
        rounded="lg"
        class="mb-2 pa-3"
      >
        <div class="d-flex align-start ga-3">
          <ResidentAvatar :resident="residentFor(entry.resident_id)" size="40" />
          <div class="flex-grow-1 overflow-hidden">
            <p class="text-body-2">
              <strong>{{ residentName(entry.resident_id) }}</strong>
              {{ ' ' }}{{ actionVerb(entry.action_type) }}
              <strong>{{ entry.task_name }}</strong>
            </p>
            <p class="text-caption text-medium-emphasis">{{ relativeTime(entry.created_at) }}</p>
          </div>
          <v-chip
            :color="actionColor(entry.action_type)"
            size="x-small"
            variant="tonal"
          >
            {{ actionLabel(entry.action_type) }}
          </v-chip>
        </div>
      </v-card>
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
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useResidentStore } from '../stores/resident.js'
import { historyApi } from '../api/index.js'
import AppLayout from '../components/layout/AppLayout.vue'
import ResidentAvatar from '../components/shared/ResidentAvatar.vue'

const { t } = useI18n()
const residentStore = useResidentStore()

const loading  = ref(true)
const errorMsg = ref('')
const entries  = ref([])
const filter   = ref('all')

const filteredEntries = computed(() => {
  if (filter.value === 'mine') {
    return entries.value.filter((e) => e.resident_id === residentStore.activeResidentId)
  }
  return entries.value
})

function residentFor(id) {
  return residentStore.residents.find((r) => r.id === id) || null
}

function residentName(id) {
  return residentFor(id)?.display_name || t('feed.someone')
}

function actionVerb(type) {
  const map = {
    completed: t('feed.action.completed'),
    skipped:   t('feed.action.skipped'),
    delegated: t('feed.action.delegated'),
    rerolled:  t('feed.action.rerolled'),
  }
  return (map[type] || type) + ' '
}

function actionLabel(type) {
  const map = {
    completed: t('feed.label.completed'),
    skipped:   t('feed.label.skipped'),
    delegated: t('feed.label.delegated'),
    rerolled:  t('feed.label.rerolled'),
  }
  return map[type] || type
}

function actionColor(type) {
  return { completed: 'success', skipped: 'warning', delegated: 'info', rerolled: 'default' }[type] || 'default'
}

function relativeTime(isoStr) {
  if (!isoStr) return ''
  const diff  = Date.now() - new Date(isoStr).getTime()
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
    const res = await historyApi.feed()
    entries.value = res.data || []
  } catch (e) {
    errorMsg.value = e.userMessage || t('errors.loadFeedFailed')
  } finally {
    loading.value = false
  }
})
</script>
