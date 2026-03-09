<!-- PreferenceSelector — like/neutral/dislike segmented control per category
     v-model: object { category: 'like'|'neutral'|'dislike' }
-->
<template>
  <div>
    <div
      v-for="cat in CATEGORIES"
      :key="cat.value"
      class="d-flex align-center mb-3"
    >
      <div class="flex-grow-1">
        <span class="text-body-2">{{ cat.label }}</span>
      </div>
      <div class="d-flex ga-1" role="group" :aria-label="`${cat.label} preference`">
        <v-btn
          v-for="pref in PREFS"
          :key="pref.value"
          :icon="pref.icon"
          size="small"
          :variant="modelValue[cat.value] === pref.value ? 'flat' : 'text'"
          :color="modelValue[cat.value] === pref.value ? prefColor(pref.value) : undefined"
          :aria-label="`${cat.label}: ${pref.label}`"
          :aria-pressed="modelValue[cat.value] === pref.value"
          @click="set(cat.value, pref.value)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue'])

const CATEGORIES = computed(() => [
  { value: 'kitchen',       label: t('preferences.categories.kitchen') },
  { value: 'bathroom',      label: t('preferences.categories.bathroom') },
  { value: 'living_room',   label: t('preferences.categories.living_room') },
  { value: 'bedroom',       label: t('preferences.categories.bedroom') },
  { value: 'floors',        label: t('preferences.categories.floors') },
  { value: 'windows',       label: t('preferences.categories.windows') },
  { value: 'laundry',       label: t('preferences.categories.laundry') },
  { value: 'garden',        label: t('preferences.categories.garden') },
])

const PREFS = computed(() => [
  { value: 'like',    label: t('preferences.like'),    icon: 'mdi-thumb-up-outline' },
  { value: 'neutral', label: t('preferences.neutral'), icon: 'mdi-minus' },
  { value: 'dislike', label: t('preferences.dislike'), icon: 'mdi-thumb-down-outline' },
])

function set(category, preference) {
  emit('update:modelValue', { ...props.modelValue, [category]: preference })
}

function prefColor(pref) {
  return { like: 'success', neutral: 'primary', dislike: 'error' }[pref]
}
</script>
