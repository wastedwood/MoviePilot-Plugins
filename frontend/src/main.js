// 本地开发壳：模拟宿主环境（Vue + 全局 Vuetify 组件 + 远程组件 props）
import { createApp } from 'vue'
import App from './App.vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import 'vuetify/styles'

const vuetify = createVuetify({ components, directives })

createApp(App).use(vuetify).mount('#app')
