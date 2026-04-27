// server.js
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');

const app = express();
const port = process.env.PORT || 3000; // 前端服务器运行端口
const apiTarget = process.env.API_TARGET || 'http://localhost:8080'; // 后端API地址

// 设置API代理
// 所有对/api/*的请求，都会被转发到后端
app.use('/api/', createProxyMiddleware({
  target: apiTarget,
  changeOrigin: true,
  // Express 的 app.use('/api/', ...) 已剥离 /api/ 前缀，无需 pathRewrite
}));

// 提供Vue构建的静态文件
// __dirname是当前文件所在目录，'dist'是vue build的输出目录
app.use(express.static(path.join(__dirname, 'dist')));

// 对于任何未匹配到静态文件或API的请求，都返回index.html
// 这是单页面应用（SPA）的标准做
app.use((req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

app.listen(port, () => {
  console.log(`Frontend server with API proxy is listening at http://localhost:${port}`);
});
