const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const { parseBrailleFile, parseBrailleFileStream } = require('../services/brailleParser');
const { generateMidi } = require('../services/midiGenerator');
const { generateMusicXML } = require('../services/musicxmlGenerator');
const { separateVoices } = require('../services/voiceSeparator');
const {
  getAllRules,
  getRuleByPattern,
  addRule,
  updateRule,
  deleteRule,
  saveParseHistory,
  getParseHistory,
} = require('../db/database');

const router = express.Router();

const LARGE_FILE_THRESHOLD = 500 * 1024; // 500KB

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = path.join(__dirname, '..', 'uploads');
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    cb(null, file.fieldname + '-' + uniqueSuffix + path.extname(file.originalname));
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 50 * 1024 * 1024 }, // 50MB max
  fileFilter: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    if (ext === '.braille' || ext === '.brl' || ext === '.txt') {
      cb(null, true);
    } else {
      cb(new Error('Only .braille, .brl, or .txt files are allowed'));
    }
  },
});

router.post('/upload', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    let parsedData;

    if (req.file.size > LARGE_FILE_THRESHOLD) {
      parsedData = await parseBrailleFileStream(req.file.path);
    } else {
      const fileContent = fs.readFileSync(req.file.path, 'utf-8');
      parsedData = parseBrailleFile(fileContent);
    }

    res.json({
      success: true,
      filename: req.file.originalname,
      parsed: parsedData,
      fileId: req.file.filename,
      isStreaming: req.file.size > LARGE_FILE_THRESHOLD,
      fileSize: req.file.size,
    });
  } catch (error) {
    console.error('Parse error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/parse', express.text({ type: 'text/plain' }), (req, res) => {
  try {
    const content = req.body;
    if (!content || typeof content !== 'string') {
      return res.status(400).json({ error: 'Invalid content' });
    }
    const parsedData = parseBrailleFile(content);
    res.json({ success: true, parsed: parsedData });
  } catch (error) {
    console.error('Parse error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/midi', (req, res) => {
  try {
    const { parsed, options } = req.body;
    if (!parsed) {
      return res.status(400).json({ error: 'Parsed data is required' });
    }

    const midiBuffer = generateMidi(parsed, options);
    const filename = `braille-${Date.now()}.mid`;
    const midiPath = path.join(__dirname, '..', 'uploads', filename);
    fs.writeFileSync(midiPath, Buffer.from(midiBuffer));

    saveParseHistory(req.body.filename || 'untitled', parsed, `/uploads/${filename}`);

    res.json({
      success: true,
      midiUrl: `/uploads/${filename}`,
      filename,
    });
  } catch (error) {
    console.error('MIDI generation error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.get('/rules', (req, res) => {
  try {
    const { category } = req.query;
    const rules = getAllRules(category);
    res.json({ success: true, rules });
  } catch (error) {
    console.error('Get rules error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.get('/rules/:pattern', (req, res) => {
  try {
    const { pattern } = req.params;
    const { category } = req.query;
    const rule = getRuleByPattern(pattern, category);
    if (!rule) {
      return res.status(404).json({ success: false, error: 'Rule not found' });
    }
    res.json({ success: true, rule });
  } catch (error) {
    console.error('Get rule error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/rules', (req, res) => {
  try {
    const rule = addRule(req.body);
    res.json({ success: true, id: rule.lastInsertRowid });
  } catch (error) {
    console.error('Add rule error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.put('/rules/:id', (req, res) => {
  try {
    const { id } = req.params;
    updateRule(id, req.body);
    res.json({ success: true });
  } catch (error) {
    console.error('Update rule error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.delete('/rules/:id', (req, res) => {
  try {
    const { id } = req.params;
    deleteRule(id);
    res.json({ success: true });
  } catch (error) {
    console.error('Delete rule error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.get('/history', (req, res) => {
  try {
    const { limit } = req.query;
    const history = getParseHistory(limit);
    res.json({ success: true, history });
  } catch (error) {
    console.error('Get history error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/musicxml', (req, res) => {
  try {
    const { parsed, title, composer } = req.body;
    if (!parsed) {
      return res.status(400).json({ error: 'Parsed data is required' });
    }

    const musicxml = generateMusicXML(parsed, {
      title: title || parsed.meta?.title || 'Untitled',
      composer: composer || parsed.meta?.composer || 'Unknown',
    });

    const filename = `braille-${Date.now()}.xml`;
    const xmlPath = path.join(__dirname, '..', 'uploads', filename);
    fs.writeFileSync(xmlPath, musicxml, 'utf-8');

    res.json({
      success: true,
      musicxmlUrl: `/uploads/${filename}`,
      filename,
    });
  } catch (error) {
    console.error('MusicXML generation error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/separate-voices', (req, res) => {
  try {
    const { parsed } = req.body;
    if (!parsed) {
      return res.status(400).json({ error: 'Parsed data is required' });
    }

    const voices = separateVoices(parsed);

    res.json({
      success: true,
      voices: voices.map(v => ({
        name: v.name,
        clef: v.clef,
        midiChannel: v.midiChannel,
        noteCount: v.events.filter(e => e.type === 'note').length,
        totalCount: v.events.length,
      })),
      voiceCount: voices.length,
    });
  } catch (error) {
    console.error('Voice separation error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/reparse', (req, res) => {
  try {
    const { tokens } = req.body;
    if (!tokens || !Array.isArray(tokens)) {
      return res.status(400).json({ error: 'Tokens array is required' });
    }

    const fileContent = tokens.map(t => t.normalized || t.pattern).join('\n');
    const parsedData = parseBrailleFile(fileContent);

    res.json({
      success: true,
      parsed: parsedData,
    });
  } catch (error) {
    console.error('Reparse error:', error);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
