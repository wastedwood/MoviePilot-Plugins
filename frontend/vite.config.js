// 镜像官方示例 MoviePilot-Frontend/examples/plugin-component/vite.config.js
// shared 全部 generate:false —— Vue/Vuetify 运行时一律复用宿主实例，绝不打包
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

const charsetRemovalPlugin = {
  postcssPlugin: 'internal:charset-removal',
  AtRule: {
    charset: (atRule) => {
      if (atRule.name === 'charset') {
        atRule.remove()
      }
    },
  },
}

const vuetifyFilterPlugin = {
  // 构建联邦产物时过滤所有 vuetify 全局规则，避免污染宿主页面样式
  postcssPlugin: 'vuetify-filter',
  Root(root) {
    root.walkRules(rule => {
      if (rule.selector && (
          rule.selector.includes('.v-') ||
          rule.selector.includes('.mdi-'))) {
        rule.remove()
      }
    })
  },
}

export default defineConfig(({ command }) => ({
  plugins: [
    vue(),
    federation({
      name: 'FntvDoubanSync',
      filename: 'remoteEntry.js',
      exposes: {
        './Config': './src/components/Config.vue',
        './Page': './src/components/Page.vue',
        './Dashboard': './src/components/Dashboard.vue',
      },
      shared: {
        vue: {
          requiredVersion: false,
          generate: false,
        },
        vuetify: {
          requiredVersion: false,
          generate: false,
          singleton: true,
        },
        'vuetify/styles': {
          requiredVersion: false,
          generate: false,
          singleton: true,
        },
      },
      format: 'esm',
    }),
  ],
  build: {
    target: 'esnext',   // 顶层 await 必需
    cssCodeSplit: true,  // 分离样式文件
  },
  css: {
    postcss: {
      plugins: command === 'build'
        ? [charsetRemovalPlugin, vuetifyFilterPlugin]
        : [charsetRemovalPlugin],
    },
  },
  server: {
    port: 5001,
    cors: true,
    origin: 'http://localhost:5001',
  },
}))
