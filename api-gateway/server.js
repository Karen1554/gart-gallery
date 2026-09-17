const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = 3000;

app.use((req, res, next) => {
  const allowedOrigin = process.env.FRONTEND_ORIGIN || 'http://localhost:4321';
  res.header('Access-Control-Allow-Origin', allowedOrigin);
  res.header('Access-Control-Allow-Credentials', 'true');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.header('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS');
  if (req.method === 'OPTIONS') {
    res.sendStatus(204);
    return;
  }
  next();
});

const proxy = (target, prefix) => createProxyMiddleware({
  target,
  changeOrigin: true,
  pathRewrite: (path) => `${prefix}${path === '/' ? '' : path.startsWith('/?') ? path.slice(1) : path}`,
});

// Gallery Service
app.use('/api/galleries', proxy('http://localhost:3001', '/api/galleries'));
app.use('/api/galerias', proxy('http://localhost:3001', '/api/galerias'));

// Works Service
app.use('/api/works', proxy('http://localhost:3002', '/api/works'));

// Auth Service
app.use('/api/auth', proxy('http://localhost:3003', '/api/auth'));

// Purchase Service
app.use('/api/purchases', proxy('http://localhost:3004', '/api/purchases'));
app.use('/api/cart', proxy('http://localhost:3004', '/api/cart'));

// Content Service
app.use('/api/content', proxy('http://localhost:3005', '/api/content'));
app.use('/api/artists', proxy('http://localhost:3005', '/api/artists'));

app.get('/health', (_req, res) => {
  res.json({ service: 'api-gateway', status: 'ok' });
});

app.listen(PORT, () => {
  console.log(`API Gateway en http://localhost:${PORT}`);
});
