const express = require('express');
const path = require('path');
const app = express();

const distDir = path.join(__dirname, 'dist');

// serve static files from dist (no index auto-send so SPA fallback works)
app.use(express.static(distDir, { index: false, maxAge: '1h', etag: false }));

// SPA fallback to index.html
app.get('*', (_, res) => res.sendFile(path.join(distDir, 'index.html')));

const port = process.env.PORT || 5000;
app.listen(port, () => console.log(`Frontend listening on ${port}`));
