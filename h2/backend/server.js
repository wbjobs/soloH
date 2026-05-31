const express = require('express');
const cors = require('cors');
const path = require('path');
const brailleRoutes = require('./routes/brailleRoutes');
const { initDatabase } = require('./db/database');

const app = express();
const PORT = process.env.PORT || 3001;

initDatabase();

app.use(cors());
app.use(express.json());
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

app.use('/api/braille', brailleRoutes);

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', message: 'Braille MIDI Server is running' });
});

app.listen(PORT, () => {
  console.log(`Braille MIDI Server running on http://localhost:${PORT}`);
});
