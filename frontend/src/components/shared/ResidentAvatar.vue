<!-- Resident avatar — colored circle with initials -->
<template>
  <v-avatar
    :size="size"
    :color="color"
    :aria-label="resident ? resident.display_name : 'No resident'"
  >
    <span class="text-caption font-weight-bold" style="color: white">
      {{ initials }}
    </span>
  </v-avatar>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  resident: { type: Object, default: null },
  size: { type: [Number, String], default: 40 },
})

// 8-color palette — index based on resident ID for consistency
const PALETTE = ['#5c7a7a','#7a5c6e','#6e7a5c','#5c6e7a','#7a6e5c','#7a5c5c','#5c7a6e','#6a5c7a']

const color = computed(() => {
  if (!props.resident) return '#aaa'
  return props.resident.avatar_color || PALETTE[(props.resident.id || 0) % PALETTE.length]
})

const initials = computed(() => {
  if (!props.resident) return '?'
  const name = props.resident.display_name || props.resident.name || '?'
  return name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2)
})
</script>
