<!-- AppLayout: wraps all main-app screens with AppBar + BottomNav -->
<template>
  <div class="hk-layout">
    <!-- App Bar -->
    <v-app-bar flat density="comfortable" color="surface">
      <v-app-bar-title>
        <span class="text-h6 font-weight-bold" style="letter-spacing: -0.5px">{{ $t('brand.name') }}</span>
      </v-app-bar-title>
      <template #append>
        <!-- Language switcher -->
        <v-menu>
          <template #activator="{ props: menuProps }">
            <v-btn
              v-bind="menuProps"
              variant="text"
              size="small"
              :aria-label="$t('language.label')"
              class="text-caption font-weight-medium px-2"
            >
              {{ currentLocaleLabel }}
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item
              v-for="loc in SUPPORTED_LOCALES"
              :key="loc.code"
              :active="localeStore.locale === loc.code"
              active-color="primary"
              @click="setLocale(loc.code)"
            >
              <v-list-item-title>{{ loc.label }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>

        <!-- Theme toggle -->
        <v-btn
          :icon="themeStore.theme === 'dark' ? 'mdi-weather-sunny' : 'mdi-weather-night'"
          variant="text"
          :aria-label="themeStore.theme === 'dark' ? $t('nav.switchToLight') : $t('nav.switchToDark')"
          @click="themeStore.toggle(vuetifyTheme)"
        />
        <!-- Resident switcher trigger -->
        <v-btn
          variant="text"
          icon
          :aria-label="$t('nav.switchResident')"
          @click="showSwitcher = true"
        >
          <ResidentAvatar :resident="residentStore.activeResident" size="32" />
        </v-btn>
      </template>
    </v-app-bar>

    <!-- Main content -->
    <v-main>
      <div class="hk-container hk-page pa-4">
        <slot />
      </div>
    </v-main>

    <!-- Bottom navigation -->
    <v-bottom-navigation
      v-model="activeTab"
      color="primary"
      grow
      elevation="0"
      border="t"
    >
      <v-btn value="home" to="/" :aria-label="$t('nav.home')">
        <v-icon>mdi-home-outline</v-icon>
        <span>{{ $t('nav.home') }}</span>
      </v-btn>
      <v-btn value="tasks" to="/tasks" :aria-label="$t('nav.tasks')">
        <v-icon>mdi-checkbox-marked-circle-outline</v-icon>
        <span>{{ $t('nav.tasks') }}</span>
      </v-btn>
      <v-btn value="feed" to="/feed" :aria-label="$t('nav.feed')">
        <v-icon>mdi-history</v-icon>
        <span>{{ $t('nav.feed') }}</span>
      </v-btn>
      <v-btn value="profile" to="/profile" :aria-label="$t('nav.profile')">
        <v-icon>mdi-account-outline</v-icon>
        <span>{{ $t('nav.profile') }}</span>
      </v-btn>
    </v-bottom-navigation>

    <!-- Resident switcher bottom sheet -->
    <ResidentSwitcher v-model="showSwitcher" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useTheme } from 'vuetify'
import { useI18n } from 'vue-i18n'
import { useThemeStore } from '../../stores/theme.js'
import { useResidentStore } from '../../stores/resident.js'
import { useLocaleStore, SUPPORTED_LOCALES } from '../../stores/locale.js'
import ResidentAvatar from '../shared/ResidentAvatar.vue'
import ResidentSwitcher from '../shared/ResidentSwitcher.vue'

const themeStore    = useThemeStore()
const vuetifyTheme  = useTheme()
const residentStore = useResidentStore()
const localeStore   = useLocaleStore()
const { locale }    = useI18n()
const showSwitcher  = ref(false)
const route         = useRoute()

const routeToTab = { '/': 'home', '/tasks': 'tasks', '/feed': 'feed', '/profile': 'profile' }
const activeTab = ref(routeToTab[route.path] || 'home')

const currentLocaleLabel = computed(() =>
  SUPPORTED_LOCALES.find((l) => l.code === localeStore.locale)?.label ?? 'EN'
)

function setLocale(code) {
  localeStore.setLocale(code, { global: { locale } })
}
</script>
