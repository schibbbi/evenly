<!-- WizardNav — back/next/skip buttons for wizard steps -->
<template>
  <div class="d-flex align-center ga-3 mt-6">
    <v-btn
      v-if="showBack"
      variant="text"
      prepend-icon="mdi-arrow-left"
      aria-label="Go back"
      @click="emit('back')"
    >
      {{ $t('wizard.nav.back') }}
    </v-btn>
    <v-spacer />
    <v-btn
      v-if="skipLabel"
      variant="text"
      class="text-medium-emphasis"
      @click="emit('skip')"
    >
      {{ skipLabel }}
    </v-btn>
    <v-btn
      color="primary"
      :disabled="!canNext"
      append-icon="mdi-arrow-right"
      @click="emit('next')"
    >
      {{ nextLabel }}
    </v-btn>
  </div>
</template>

<script setup>
defineProps({
  canNext:   { type: Boolean, default: true },
  showBack:  { type: Boolean, default: true },
  nextLabel: { type: String,  default: 'Continue' },
  skipLabel: { type: String,  default: '' },
})
const emit = defineEmits(['back', 'next', 'skip'])
</script>
