// 本地开发壳：模拟宿主环境（Vue + 全局 Vuetify 组件 + 远程组件 props）
import { createApp } from 'vue'
import App from './App.vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import 'vuetify/styles'

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        dark: false,
        colors: {
          primary: '#9155FD',
          secondary: '#8A8D93',
          success: '#56CA00',
          info: '#16B1FF',
          warning: '#FFB400',
          error: '#FF4C51',
        },
      },
      dark: {
        dark: true,
        colors: {
          primary: '#9155FD',
          secondary: '#8A8D93',
          success: '#56CA00',
          info: '#16B1FF',
          warning: '#FFB400',
          error: '#FF4C51',
        },
      },
    },
  },
})

createApp(App).use(vuetify).mount('#app')
