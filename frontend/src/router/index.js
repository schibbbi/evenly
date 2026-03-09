import { createRouter, createWebHistory } from 'vue-router'
import { householdsApi, residentsApi } from '../api/index.js'
import i18n from '../plugins/i18n.js'

// Lazy-load all views for better initial load performance
const SetupWizard      = () => import('../views/wizard/SetupWizard.vue')
const FirstLoginWizard = () => import('../views/wizard/FirstLoginWizard.vue')
const HomeView         = () => import('../views/HomeView.vue')
const SessionStart     = () => import('../views/session/SessionStart.vue')
const Suggestions      = () => import('../views/session/Suggestions.vue')
const ActiveTask       = () => import('../views/session/ActiveTask.vue')
const Completion       = () => import('../views/session/Completion.vue')
const FeedView         = () => import('../views/FeedView.vue')
const ProfileView      = () => import('../views/ProfileView.vue')
const SettingsView     = () => import('../views/SettingsView.vue')
const PanicView        = () => import('../views/PanicView.vue')

const routes = [
  { path: '/setup',        name: 'setup',        component: SetupWizard,      meta: { titleKey: 'wizard.setup.welcome.cta', hideNav: true } },
  { path: '/first-login',  name: 'first-login',  component: FirstLoginWizard, meta: { titleKey: 'wizard.firstLogin.welcome.title', hideNav: true } },
  { path: '/',             name: 'home',         component: HomeView,         meta: { titleKey: null } },
  { path: '/tasks',        name: 'session-start',component: SessionStart,     meta: { titleKey: 'session.start.title' } },
  { path: '/tasks/suggestions', name: 'suggestions', component: Suggestions,  meta: { titleKey: 'session.suggestions.title' } },
  { path: '/tasks/active', name: 'active-task',  component: ActiveTask,       meta: { titleKey: 'session.suggestions.title' } },
  { path: '/tasks/done',   name: 'completion',   component: Completion,       meta: { titleKey: 'session.completion.title' } },
  { path: '/feed',         name: 'feed',         component: FeedView,         meta: { titleKey: 'feed.title' } },
  { path: '/profile',      name: 'profile',      component: ProfileView,      meta: { titleKey: 'profile.title' } },
  { path: '/settings',     name: 'settings',     component: SettingsView,     meta: { titleKey: 'settings.title' } },
  { path: '/panic',        name: 'panic',        component: PanicView,        meta: { titleKey: 'panic.title' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// Update document.title on route change (translated)
router.afterEach((to) => {
  const t = i18n.global.t
  const brand = t('brand.name')
  if (to.meta.titleKey) {
    // titleKey may contain interpolation placeholders — pass empty params to avoid errors
    const title = t(to.meta.titleKey, { name: '', current: '', total: '' })
    document.title = `${title} — ${brand}`
  } else {
    document.title = brand
  }
})

// Global navigation guard: redirect to /setup if no household exists,
// redirect to /first-login if active resident has setup_complete = false
const WIZARD_ROUTES = new Set(['setup', 'first-login'])
let checkedSetup = false

router.beforeEach(async (to) => {
  if (WIZARD_ROUTES.has(to.name)) return true

  try {
    const res = await householdsApi.list()
    const households = res.data
    if (!households || households.length === 0) {
      checkedSetup = true
      return { name: 'setup' }
    }

    // Check if active resident needs first-login wizard
    if (!checkedSetup) {
      const activeId = parseInt(localStorage.getItem('activeResidentId'))
      if (activeId) {
        try {
          const rRes = await residentsApi.get(activeId)
          if (rRes.data?.setup_complete === false) {
            checkedSetup = true
            return { name: 'first-login' }
          }
        } catch (_) {}
      }
      checkedSetup = true
    }
    return true
  } catch (_) {
    // Backend unreachable — let the view handle the error
    checkedSetup = true
    return true
  }
})

export default router
