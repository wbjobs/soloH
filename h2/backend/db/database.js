const Database = require('better-sqlite3');
const path = require('path');
const { loadDefaultRules } = require('../data/mappingRules');

let db;

function initDatabase() {
  const dbPath = path.join(__dirname, 'braille.db');
  db = new Database(dbPath);

  db.exec(`
    CREATE TABLE IF NOT EXISTS mapping_rules (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      category TEXT NOT NULL,
      braille_pattern TEXT NOT NULL,
      meaning TEXT NOT NULL,
      midi_value INTEGER,
      duration REAL,
      description TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS parse_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      filename TEXT NOT NULL,
      parsed_data TEXT NOT NULL,
      midi_path TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_mapping_category ON mapping_rules(category);
    CREATE INDEX IF NOT EXISTS idx_mapping_pattern ON mapping_rules(braille_pattern);
  `);

  const count = db.prepare('SELECT COUNT(*) as count FROM mapping_rules').get();
  if (count.count === 0) {
    seedDefaultRules();
  }

  console.log('Database initialized at', dbPath);
}

function seedDefaultRules() {
  const rules = loadDefaultRules();
  const insert = db.prepare(`
    INSERT INTO mapping_rules (category, braille_pattern, meaning, midi_value, duration, description)
    VALUES (@category, @braille_pattern, @meaning, @midi_value, @duration, @description)
  `);

  const insertMany = db.transaction((items) => {
    for (const item of items) {
      insert.run(item);
    }
  });

  insertMany(rules);
  console.log(`Seeded ${rules.length} default mapping rules`);
}

function getDb() {
  if (!db) {
    initDatabase();
  }
  return db;
}

function getAllRules(category) {
  const database = getDb();
  if (category) {
    return database.prepare('SELECT * FROM mapping_rules WHERE category = ? ORDER BY id').all(category);
  }
  return database.prepare('SELECT * FROM mapping_rules ORDER BY category, id').all();
}

function getRuleByPattern(pattern, category) {
  const database = getDb();
  if (category) {
    return database.prepare('SELECT * FROM mapping_rules WHERE braille_pattern = ? AND category = ?').get(pattern, category);
  }
  return database.prepare('SELECT * FROM mapping_rules WHERE braille_pattern = ?').get(pattern);
}

function addRule(rule) {
  const database = getDb();
  return database.prepare(`
    INSERT INTO mapping_rules (category, braille_pattern, meaning, midi_value, duration, description)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(
    rule.category,
    rule.braille_pattern,
    rule.meaning,
    rule.midi_value || null,
    rule.duration || null,
    rule.description || ''
  );
}

function updateRule(id, rule) {
  const database = getDb();
  return database.prepare(`
    UPDATE mapping_rules SET category=?, braille_pattern=?, meaning=?, midi_value=?, duration=?, description=? WHERE id=?
  `).run(
    rule.category,
    rule.braille_pattern,
    rule.meaning,
    rule.midi_value || null,
    rule.duration || null,
    rule.description || '',
    id
  );
}

function deleteRule(id) {
  const database = getDb();
  return database.prepare('DELETE FROM mapping_rules WHERE id = ?').run(id);
}

function saveParseHistory(filename, parsedData, midiPath) {
  const database = getDb();
  return database.prepare(`
    INSERT INTO parse_history (filename, parsed_data, midi_path) VALUES (?, ?, ?)
  `).run(filename, JSON.stringify(parsedData), midiPath || null);
}

function getParseHistory(limit) {
  const database = getDb();
  return database.prepare('SELECT * FROM parse_history ORDER BY created_at DESC LIMIT ?').all(limit || 20);
}

module.exports = {
  initDatabase,
  getDb,
  getAllRules,
  getRuleByPattern,
  addRule,
  updateRule,
  deleteRule,
  saveParseHistory,
  getParseHistory,
};
