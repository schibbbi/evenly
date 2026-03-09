<!-- Resident switcher — bottom sheet, no PIN required to switch -->
<template>
  <v-bottom-sheet v-model="model" max-width="480">
    <v-card rounded="t-xl" class="pa-4">
      <v-card-title class="text-h6 mb-2">{{ $t('residentSwitcher.title') }}</v-card-title>
      <v-list>
        <v-list-item
          v-for="r in residentStore.residents"
          :key="r.id"
          :active="r.id === residentStore.activeResidentId"
          active-color="primary"
          rounded="lg"
          @click="select(r)"
        >
          <template #prepend>
            <ResidentAvatar :resident="r" size="40" class="mr-3" />
          </template>
          <v-list-item-title>{{ r.display_name }}</v-list-item-title>
          <v-list-item-subtitle>
            <v-chip size="x-small" :color="roleColor(r.role)" variant="tonal">
              {{ r.role }}
            </v-chip>
          </v-list-item-subtitle>
          <template #append>
            <v-icon v-if="r.id === residentStore.activeResidentId" color="primary">
              mdi-check-circle
            </v-icon>
          </template>
        </v-list-item>
      </v-list>
      <v-btn
        block
        variant="text"
        class="mt-2"
        @click="model = false"
        aria-label="Close resident switcher"
      >
        {{ $t('residentSwitcher.cancel') }}
      </v-btn>
    </v-card>
  </v-bottom-sheet>
</template>

<script setup>
import { useResidentStore } from '../../stores/resident.js'
import ResidentAvatar from './ResidentAvatar.vue'

const model = defineModel()
const residentStore = useResidentStore()

function select(resident) {
  residentStore.setActiveResident(resident.id)
  model.value = false
}

function roleColor(role) {
  return { admin: 'primary', edit: 'secondary', view: 'default' }[role] || 'default'
}
</script>
