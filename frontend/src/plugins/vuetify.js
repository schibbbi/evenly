// Vuetify 3 + Material Design 3 theme configuration
// All color values are defined as MD3 tokens here — components use only theme tokens,
// never raw hex values.

import { createVuetify } from 'vuetify'
import { md3 } from 'vuetify/blueprints'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'

// Calm, neutral primary — works well in both light and dark
const lightTheme = {
  dark: false,
  colors: {
    primary:          '#5c7a7a',   // muted teal — calm, not saturated
    'on-primary':     '#ffffff',
    'primary-container':   '#cde8e8',
    'on-primary-container': '#002020',

    secondary:        '#e8a020',   // amber — gamification only (streaks, points)
    'on-secondary':   '#000000',
    'secondary-container': '#ffddb3',
    'on-secondary-container': '#2c1600',

    surface:          '#f8fafa',
    'on-surface':     '#191c1c',
    'surface-variant': '#dae5e5',
    'on-surface-variant': '#3f4948',

    background:       '#f8fafa',
    'on-background':  '#191c1c',

    error:            '#ba1a1a',
    'on-error':       '#ffffff',

    // Semantic colors for task states
    success:          '#4caf50',
    warning:          '#fb8c00',
    info:             '#5c7a7a',
  },
}

const darkTheme = {
  dark: true,
  colors: {
    primary:          '#92cbcb',
    'on-primary':     '#003737',
    'primary-container': '#00504f',
    'on-primary-container': '#adf3f2',

    secondary:        '#fdb96b',
    'on-secondary':   '#472900',
    'secondary-container': '#653d00',
    'on-secondary-container': '#ffddb3',

    surface:          '#191c1c',
    'on-surface':     '#e0e3e3',
    'surface-variant': '#3f4948',
    'on-surface-variant': '#bec8c8',

    background:       '#191c1c',
    'on-background':  '#e0e3e3',

    error:            '#ffb4ab',
    'on-error':       '#690005',

    success:          '#81c784',
    warning:          '#ffb74d',
    info:             '#92cbcb',
  },
}

export default createVuetify({
  blueprint: md3,
  theme: {
    defaultTheme: 'light',
    themes: {
      light: lightTheme,
      dark: darkTheme,
    },
  },
  defaults: {
    VCard: { rounded: 'lg', elevation: 0 },
    VBtn: { rounded: 'lg' },
    VTextField: { variant: 'outlined', density: 'comfortable' },
    VSelect: { variant: 'outlined', density: 'comfortable' },
    VChip: { rounded: 'lg' },
  },
})
