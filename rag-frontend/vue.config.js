const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
  devServer: {
    port: 3000,
    proxy: {
      '/api/': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        // webpack-dev-server 自动剥离 context /api/ 前缀，无需 pathRewrite
      },
    },
  },
})
