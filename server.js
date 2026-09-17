require('dotenv').config();

const fs = require('fs');
const path = require('path');
const express = require('express');
const multer = require('multer');
const session = require('express-session');

const app = express();
const PORT = Number(process.env.PORT) || 3000;
const isProduction = process.env.NODE_ENV === 'production';

const ADMIN_USER = process.env.ADMIN_USER || 'admin';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin123';

const DATABASE_URL = process.env.DATABASE_URL;
if (!DATABASE_URL && isProduction) {
  throw new Error('DATABASE_URL is required in production');
}
const uploadsDir = process.env.UPLOADS_DIR || path.join(__dirname, 'uploads');
fs.mkdirSync(uploadsDir, { recursive: true });

let dbBackend = null;

if (DATABASE_URL) {
  const { Pool } = require('pg');
  const pool = new Pool({
    connectionString: DATABASE_URL,
    ssl: process.env.PGSSLMODE === 'disable' ? false : { rejectUnauthorized: false }
  });

  dbBackend = {
    type: 'pg',
    init: async () => {
      await pool.query(`
        CREATE TABLE IF NOT EXISTS works (
          id SERIAL PRIMARY KEY,
          title VARCHAR(255) NOT NULL,
          description TEXT,
          year VARCHAR(50),
          category VARCHAR(100) DEFAULT 'Landscape Paintings',
          image_path VARCHAR(255) NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
      `);
      await pool.query(`
        ALTER TABLE works ADD COLUMN IF NOT EXISTS category VARCHAR(100) DEFAULT 'Landscape Paintings'
      `).catch(() => {});
    },
    all: async (sql, params = []) => {
      let index = 1;
      const pgSql = sql.replace(/\?/g, () => `$${index++}`);
      const result = await pool.query(pgSql, params);
      return result.rows;
    },
    get: async (sql, params = []) => {
      let index = 1;
      const pgSql = sql.replace(/\?/g, () => `$${index++}`);
      const result = await pool.query(pgSql, params);
      return result.rows[0];
    },
    run: async (sql, params = []) => {
      let index = 1;
      let pgSql = sql.replace(/\?/g, () => `$${index++}`);
      if (/^\s*INSERT/i.test(pgSql) && !/RETURNING/i.test(pgSql)) {
        pgSql += ' RETURNING id';
      }
      const result = await pool.query(pgSql, params);
      return {
        lastID: result.rows[0] ? result.rows[0].id : null,
        changes: result.rowCount
      };
    }
  };
} else {
  const state = {
    works: [],
    nextId: 1
  };

  function applyFilters(rows, params, hasCategoryFilter = false) {
    let index = 0;
    let filtered = [...rows];

    if (params.length >= 3) {
      const rawQuery = String(params[index] || '');
      if (rawQuery.includes('%')) {
        const q = rawQuery.replace(/%/g, '').toLowerCase();
        if (q) {
          filtered = filtered.filter((row) => {
            const title = String(row.title || '').toLowerCase();
            const description = String(row.description || '').toLowerCase();
            const year = String(row.year || '').toLowerCase();
            return title.includes(q) || description.includes(q) || year.includes(q);
          });
        }
        index += 3;
      }
    }

    const remaining = params.slice(index);
    if (hasCategoryFilter && remaining.length > 0 && typeof remaining[0] === 'string' && remaining[0].trim()) {
      const category = remaining[0].trim();
      filtered = filtered.filter((row) => String(row.category || '') === category);
    }

    return filtered;
  }

  dbBackend = {
    type: 'memory',
    init: async () => {},
    all: async (sql, params = []) => {
      if (/SELECT\s+id,\s*title,\s*description,\s*year,\s*category,\s*image_path,\s*created_at\s+FROM\s+works/i.test(sql)) {
        const hasCategoryFilter = /category\s*=\s*(\?|\$\d+)/i.test(sql);
        const rows = applyFilters(state.works, params, hasCategoryFilter)
          .sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));

        const limit = Number(params[params.length - 2] || rows.length);
        const offset = Number(params[params.length - 1] || 0);
        return rows.slice(offset, offset + limit);
      }
      return [];
    },
    get: async (sql, params = []) => {
      if (/SELECT\s+COUNT\(\*\)\s+AS\s+total\s+FROM\s+works/i.test(sql)) {
        const hasCategoryFilter = /category\s*=\s*(\?|\$\d+)/i.test(sql);
        const rows = applyFilters(state.works, params, hasCategoryFilter);
        return { total: rows.length };
      }

      if (/SELECT\s+id,\s*image_path\s+FROM\s+works\s+WHERE\s+id\s*=\s*\?/i.test(sql)) {
        const id = Number(params[0]);
        const row = state.works.find((item) => item.id === id);
        return row ? { id: row.id, image_path: row.image_path } : undefined;
      }

      if (/SELECT\s+id,\s*title,\s*description,\s*year,\s*category,\s*image_path,\s*created_at\s+FROM\s+works\s+WHERE\s+id\s*=\s*\?/i.test(sql)) {
        const id = Number(params[0]);
        return state.works.find((item) => item.id === id);
      }

      return undefined;
    },
    run: async (sql, params = []) => {
      if (/INSERT\s+INTO\s+works/i.test(sql)) {
        const [title, description, year, category, imagePath] = params;
        const row = {
          id: state.nextId++,
          title,
          description,
          year,
          category,
          image_path: imagePath,
          created_at: new Date().toISOString()
        };
        state.works.push(row);
        return { lastID: row.id, changes: 1 };
      }

      if (/UPDATE\s+works\s+SET/i.test(sql)) {
        const [title, description, year, category, imagePath, idParam] = params;
        const id = Number(idParam);
        const index = state.works.findIndex((item) => item.id === id);
        if (index === -1) {
          return { lastID: null, changes: 0 };
        }
        state.works[index] = {
          ...state.works[index],
          title,
          description,
          year,
          category,
          image_path: imagePath
        };
        return { lastID: null, changes: 1 };
      }

      if (/DELETE\s+FROM\s+works\s+WHERE\s+id\s*=\s*\?/i.test(sql)) {
        const id = Number(params[0]);
        const before = state.works.length;
        state.works = state.works.filter((item) => item.id !== id);
        const changes = before - state.works.length;
        return { lastID: null, changes };
      }

      return { lastID: null, changes: 0 };
    }
  };
}

dbBackend.init().catch((err) => {
  console.error('Error initializing database:', err);
});

function mapWorkRow(row) {
  if (!row) return null;
  return {
    id: row.id,
    title: row.title,
    description: row.description,
    year: row.year,
    category: row.category || 'Landscape Paintings',
    imageUrl: `/uploads/${row.image_path}`,
    createdAt: row.created_at
  };
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => {
    cb(null, uploadsDir);
  },
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname || '').toLowerCase();
    const safeExt = ext || '.jpg';
    const unique = `${Date.now()}-${Math.round(Math.random() * 1e9)}${safeExt}`;
    cb(null, unique);
  }
});

const upload = multer({
  storage,
  limits: {
    fileSize: 8 * 1024 * 1024
  },
  fileFilter: (_req, file, cb) => {
    if (!file.mimetype.startsWith('image/')) {
      cb(new Error('Only images are allowed.'));
      return;
    }
    cb(null, true);
  }
});

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Render terminates TLS at the proxy, so Express must trust proxy headers.
if (isProduction) {
  app.set('trust proxy', 1);
}

app.use(session({
  name: 'gart.sid',
  secret: process.env.SESSION_SECRET || 'change-this-session-secret',
  resave: false,
  saveUninitialized: false,
  proxy: isProduction,
  cookie: {
    httpOnly: true,
    sameSite: 'lax',
    secure: isProduction ? 'auto' : false,
    maxAge: 1000 * 60 * 60 * 12
  }
}));

app.use('/assets', express.static(path.join(__dirname, 'assets')));
app.use('/uploads', express.static(uploadsDir));
app.use(express.static(__dirname, { index: 'index.html' }));

function requireAuth(req, res, next) {
  if (!req.session || !req.session.user) {
    res.status(401).json({ error: 'Unauthorized' });
    return;
  }
  next();
}

app.get('/api/health', (_req, res) => {
  res.json({ ok: true, dbType: dbBackend.type });
});

app.get('/api/auth/me', (req, res) => {
  res.json({ authenticated: Boolean(req.session && req.session.user) });
});

app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body;

  if (username !== ADMIN_USER || password !== ADMIN_PASSWORD) {
    res.status(401).json({ error: 'Invalid credentials' });
    return;
  }

  req.session.user = { username: ADMIN_USER };
  res.json({ ok: true, username: ADMIN_USER });
});

app.post('/api/auth/logout', (req, res) => {
  if (!req.session) {
    res.json({ ok: true });
    return;
  }

  req.session.destroy(() => {
    res.clearCookie('gart.sid');
    res.json({ ok: true });
  });
});

app.get('/api/works', async (req, res, next) => {
  try {
    const query = String(req.query.q || '').trim();
    const category = String(req.query.category || '').trim();
    const page = Math.max(1, Number.parseInt(String(req.query.page || '1'), 10) || 1);
    const limitRaw = Number.parseInt(String(req.query.limit || '6'), 10) || 6;
    const limit = Math.min(Math.max(limitRaw, 1), 50);
    const offset = (page - 1) * limit;

    const conditions = [];
    const whereParams = [];

    if (query) {
      if (dbBackend.type === 'pg') {
        const idx1 = whereParams.length + 1;
        const idx2 = whereParams.length + 2;
        const idx3 = whereParams.length + 3;
        conditions.push(`(title ILIKE $${idx1} OR description ILIKE $${idx2} OR year ILIKE $${idx3})`);
      } else {
        conditions.push('(title LIKE ? OR description LIKE ? OR year LIKE ?)');
      }
      whereParams.push(`%${query}%`, `%${query}%`, `%${query}%`);
    }

    if (category) {
      if (dbBackend.type === 'pg') {
        const idx = whereParams.length + 1;
        conditions.push(`category = $${idx}`);
      } else {
        conditions.push('category = ?');
      }
      whereParams.push(category);
    }

    const whereSql = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

    const countRow = await dbBackend.get(
      `SELECT COUNT(*) AS total FROM works ${whereSql}`,
      whereParams
    );
    const totalItems = Number(countRow ? countRow.total : 0);

    let orderLimitSql = '';
    let queryParams = [...whereParams];

    if (dbBackend.type === 'pg') {
      const idx1 = whereParams.length + 1;
      const idx2 = whereParams.length + 2;
      orderLimitSql = `ORDER BY created_at DESC LIMIT $${idx1} OFFSET $${idx2}`;
      queryParams.push(limit, offset);
    } else {
      orderLimitSql = 'ORDER BY created_at DESC LIMIT ? OFFSET ?';
      queryParams.push(limit, offset);
    }

    const rows = await dbBackend.all(
      `SELECT id, title, description, year, category, image_path, created_at
       FROM works
       ${whereSql}
       ${orderLimitSql}`,
      queryParams
    );

    const totalPages = Math.max(1, Math.ceil(totalItems / limit));

    res.json({
      items: rows.map(mapWorkRow),
      pagination: {
        page,
        limit,
        totalItems,
        totalPages
      }
    });
  } catch (error) {
    next(error);
  }
});

app.post('/api/works', requireAuth, upload.single('image'), async (req, res, next) => {
  try {
    const title = String(req.body.title || '').trim();
    const description = String(req.body.description || '').trim();
    const year = String(req.body.year || '').trim();
    const category = String(req.body.category || 'Landscape Paintings').trim() || 'Landscape Paintings';

    if (!title) {
      res.status(400).json({ error: 'Title is required' });
      return;
    }

    if (!req.file) {
      res.status(400).json({ error: 'Image is required' });
      return;
    }

    const insert = await dbBackend.run(
      'INSERT INTO works (title, description, year, category, image_path) VALUES (?, ?, ?, ?, ?)',
      [title, description, year, category, req.file.filename]
    );

    const newWork = await dbBackend.get(
      'SELECT id, title, description, year, category, image_path, created_at FROM works WHERE id = ?',
      [insert.lastID]
    );

    res.status(201).json(mapWorkRow(newWork));
  } catch (error) {
    next(error);
  }
});

app.put('/api/works/:id', requireAuth, upload.single('image'), async (req, res, next) => {
  try {
    const workId = Number.parseInt(req.params.id, 10);
    const title = String(req.body.title || '').trim();
    const description = String(req.body.description || '').trim();
    const year = String(req.body.year || '').trim();
    const category = String(req.body.category || 'Landscape Paintings').trim() || 'Landscape Paintings';

    if (!Number.isInteger(workId) || workId <= 0) {
      res.status(400).json({ error: 'Invalid work ID' });
      return;
    }

    if (!title) {
      res.status(400).json({ error: 'Title is required' });
      return;
    }

    const existingWork = await dbBackend.get('SELECT id, image_path FROM works WHERE id = ?', [workId]);
    if (!existingWork) {
      res.status(404).json({ error: 'Work not found' });
      return;
    }

    let newImagePath = existingWork.image_path;
    if (req.file) {
      newImagePath = req.file.filename;
    }

    await dbBackend.run(
      'UPDATE works SET title = ?, description = ?, year = ?, category = ?, image_path = ? WHERE id = ?',
      [title, description, year, category, newImagePath, workId]
    );

    if (req.file && existingWork.image_path && existingWork.image_path !== req.file.filename) {
      const oldPath = path.join(uploadsDir, existingWork.image_path);
      fs.unlink(oldPath, () => {});
    }

    const updatedWork = await dbBackend.get(
      'SELECT id, title, description, year, category, image_path, created_at FROM works WHERE id = ?',
      [workId]
    );

    res.json(mapWorkRow(updatedWork));
  } catch (error) {
    next(error);
  }
});

app.delete('/api/works/:id', requireAuth, async (req, res, next) => {
  try {
    const workId = Number.parseInt(req.params.id, 10);

    if (!Number.isInteger(workId) || workId <= 0) {
      res.status(400).json({ error: 'Invalid work ID' });
      return;
    }

    const work = await dbBackend.get('SELECT id, image_path FROM works WHERE id = ?', [workId]);
    if (!work) {
      res.status(404).json({ error: 'Work not found' });
      return;
    }

    await dbBackend.run('DELETE FROM works WHERE id = ?', [workId]);

    if (work.image_path) {
      const imagePath = path.join(uploadsDir, work.image_path);
      fs.unlink(imagePath, () => {});
    }

    res.json({ ok: true });
  } catch (error) {
    next(error);
  }
});

app.use((error, _req, res, _next) => {
  const knownErrors = ['Only images are allowed.', 'File too large'];
  const status = knownErrors.includes(error.message) ? 400 : 500;
  const message = status === 400 ? error.message : 'Internal server error';

  if (status === 500) {
    console.error(error);
  }

  res.status(status).json({ error: message });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
