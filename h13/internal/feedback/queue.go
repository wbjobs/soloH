package feedback

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"hash"
	"math/rand"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"
)

type QueueEntry struct {
	ID            string
	Data          []byte
	Hash          string
	Score         int
	PathSignature uint64
	Depth         int
	ExecutionTime time.Duration
	Favored       bool
	Trimmed       bool
	Importance    float64
	ParentID      string
	MutationType  string
	CreatedAt     time.Time
	UseCount      int
}

type Queue struct {
	entries        []*QueueEntry
	seenSignatures map[uint64]bool
	seenHashes     map[string]bool
	mu             sync.RWMutex
	rng            *rand.Rand
	queueDir       string
	currentIdx     int
	totalTests     uint64
	totalPaths     uint64
}

type QueueConfig struct {
	QueueDir   string
	InitialSeed []byte
	BaseSeed   int64
}

func NewQueue(cfg QueueConfig) (*Queue, error) {
	if cfg.BaseSeed == 0 {
		cfg.BaseSeed = time.Now().UnixNano()
	}

	q := &Queue{
		entries:        make([]*QueueEntry, 0),
		seenSignatures: make(map[uint64]bool),
		seenHashes:     make(map[string]bool),
		rng:            rand.New(rand.NewSource(cfg.BaseSeed)),
		queueDir:       cfg.QueueDir,
	}

	if cfg.QueueDir != "" {
		if err := os.MkdirAll(cfg.QueueDir, 0755); err != nil {
			return nil, fmt.Errorf("failed to create queue directory: %w", err)
		}
	}

	if cfg.InitialSeed != nil && len(cfg.InitialSeed) > 0 {
		if err := q.AddSeed(cfg.InitialSeed, "initial_seed"); err != nil {
			return nil, fmt.Errorf("failed to add initial seed: %w", err)
		}
	}

	return q, nil
}

func (q *Queue) AddSeed(data []byte, mutationType string) error {
	q.mu.Lock()
	defer q.mu.Unlock()

	hash := computeHash(data)
	if q.seenHashes[hash] {
		return nil
	}

	sig := computePathSignature(data)

	entry := &QueueEntry{
		ID:            generateID(),
		Data:          make([]byte, len(data)),
		Hash:          hash,
		PathSignature: sig,
		Score:         1,
		Depth:         1,
		Favored:       true,
		Importance:    1.0,
		MutationType:  mutationType,
		CreatedAt:     time.Now(),
	}
	copy(entry.Data, data)

	q.entries = append(q.entries, entry)
	q.seenHashes[hash] = true

	if !q.seenSignatures[sig] {
		q.seenSignatures[sig] = true
		q.totalPaths++
		entry.Favored = true
	}

	if q.queueDir != "" {
		if err := q.saveEntry(entry); err != nil {
			return err
		}
	}

	return nil
}

func (q *Queue) GetNextSeed() ([]byte, error) {
	q.mu.Lock()
	defer q.mu.Unlock()

	if len(q.entries) == 0 {
		return nil, fmt.Errorf("queue is empty")
	}

	q.totalTests++

	var entry *QueueEntry

	if q.rng.Intn(100) < 70 {
		entry = q.selectFavored()
	} else {
		entry = q.selectRandom()
	}

	if entry == nil {
		entry = q.entries[q.rng.Intn(len(q.entries))]
	}

	entry.UseCount++

	return entry.Data, nil
}

func (q *Queue) selectFavored() *QueueEntry {
	favored := make([]*QueueEntry, 0, len(q.entries))
	for _, e := range q.entries {
		if e.Favored {
			favored = append(favored, e)
		}
	}

	if len(favored) == 0 {
		return nil
	}

	sort.Slice(favored, func(i, j int) bool {
		return q.calculateEffectiveScore(favored[i]) > q.calculateEffectiveScore(favored[j])
	})

	topN := min(20, len(favored))
	idx := q.rng.Intn(topN)
	return favored[idx]
}

func (q *Queue) selectRandom() *QueueEntry {
	if len(q.entries) == 0 {
		return nil
	}

	totalWeight := 0.0
	weights := make([]float64, len(q.entries))
	for i, e := range q.entries {
		weight := q.calculateEffectiveScore(e)
		if weight < 0.1 {
			weight = 0.1
		}
		weights[i] = weight
		totalWeight += weight
	}

	r := q.rng.Float64() * totalWeight
	cumulative := 0.0
	for i, w := range weights {
		cumulative += w
		if r <= cumulative {
			return q.entries[i]
		}
	}

	return q.entries[len(q.entries)-1]
}

func (q *Queue) ReportResult(input, output []byte, isCrash bool) bool {
	q.mu.Lock()
	defer q.mu.Unlock()

	sig := computePathSignature(output)

	if !q.seenSignatures[sig] {
		q.seenSignatures[sig] = true
		q.totalPaths++

		parentHash := computeHash(input)
		parentDepth := 1
		for _, e := range q.entries {
			if e.Hash == parentHash {
				parentDepth = e.Depth
				break
			}
		}

		entry := &QueueEntry{
			ID:            generateID(),
			Data:          make([]byte, len(input)),
			Hash:          parentHash,
			PathSignature: sig,
			Score:         1,
			Depth:         parentDepth + 1,
			Favored:       true,
			Importance:    q.calculateImportance(input, output, isCrash),
			MutationType:  "feedback",
			CreatedAt:     time.Now(),
		}
		copy(entry.Data, input)

		q.entries = append(q.entries, entry)
		q.seenHashes[parentHash] = true

		if q.queueDir != "" {
			q.saveEntry(entry)
		}

		q.rebalance()

		return true
	}

	return false
}

func (q *Queue) calculateImportance(input, output []byte, isCrash bool) float64 {
	importance := 1.0

	if isCrash {
		importance += 10.0
	}

	importance += float64(len(output)) / 100.0
	importance += float64(len(input)) / 100.0

	uniqueness := float64(countUniqueBytes(output)) / float64(len(output))
	importance += uniqueness * 2.0

	return importance
}

func (q *Queue) calculateEffectiveScore(e *QueueEntry) float64 {
	score := e.Importance

	if e.Favored {
		score *= 1.5
	}

	depthPenalty := 1.0
	if e.Depth > 10 {
		depthPenalty = 1.0 / (1.0 + 0.1*float64(e.Depth-10))
	}
	score *= depthPenalty

	usageDecay := 1.0
	if e.UseCount > 100 {
		usageDecay = 1.0 / (1.0 + 0.01*float64(e.UseCount-100))
	}
	score *= usageDecay

	noveltyBonus := 1.0
	age := time.Since(e.CreatedAt).Seconds()
	if age < 60 && e.UseCount < 5 {
		noveltyBonus = 2.0
	} else if age < 300 && e.UseCount < 20 {
		noveltyBonus = 1.3
	}
	score *= noveltyBonus

	return score
}

func countUniqueBytes(data []byte) int {
	seen := make(map[byte]bool)
	for _, b := range data {
		seen[b] = true
	}
	return len(seen)
}

func (q *Queue) rebalance() {
	if len(q.entries) <= 10000 {
		return
	}

	type entryWithScore struct {
		entry *QueueEntry
		score float64
	}

	scored := make([]entryWithScore, 0, len(q.entries))
	for _, e := range q.entries {
		scored = append(scored, entryWithScore{
			entry: e,
			score: q.calculateEffectiveScore(e),
		})
	}

	sort.Slice(scored, func(i, j int) bool {
		return scored[i].score > scored[j].score
	})

	protectedCount := 0
	for i := range scored {
		if scored[i].entry.Favored {
			protectedCount++
		}
	}

	targetSize := 5000
	if protectedCount > targetSize {
		targetSize = protectedCount
	}

	newEntries := make([]*QueueEntry, 0, targetSize)
	newHashes := make(map[string]bool)

	for _, s := range scored {
		if len(newEntries) >= targetSize {
			break
		}
		if s.entry.Favored || len(newEntries) < targetSize/2 {
			newEntries = append(newEntries, s.entry)
			newHashes[s.entry.Hash] = true
		}
	}

	for _, s := range scored {
		if len(newEntries) >= targetSize {
			break
		}
		if !newHashes[s.entry.Hash] {
			newEntries = append(newEntries, s.entry)
			newHashes[s.entry.Hash] = true
		}
	}

	q.entries = newEntries
	q.seenHashes = newHashes
}

func (q *Queue) Stats() (totalEntries int, totalTests uint64, totalPaths uint64) {
	q.mu.RLock()
	defer q.mu.RUnlock()
	return len(q.entries), q.totalTests, q.totalPaths
}

func (q *Queue) GetEntries() []*QueueEntry {
	q.mu.RLock()
	defer q.mu.RUnlock()
	entries := make([]*QueueEntry, len(q.entries))
	copy(entries, q.entries)
	return entries
}

func (q *Queue) saveEntry(entry *QueueEntry) error {
	if q.queueDir == "" {
		return nil
	}

	filename := filepath.Join(q.queueDir, fmt.Sprintf("id_%08d_%s", len(q.entries), entry.ID[:8]))
	return os.WriteFile(filename, entry.Data, 0644)
}

func (q *Queue) LoadFromDir(dir string) error {
	q.mu.Lock()
	defer q.mu.Unlock()

	files, err := os.ReadDir(dir)
	if err != nil {
		return fmt.Errorf("failed to read queue directory: %w", err)
	}

	for _, file := range files {
		if file.IsDir() {
			continue
		}

		path := filepath.Join(dir, file.Name())
		data, err := os.ReadFile(path)
		if err != nil {
			continue
		}

		hash := computeHash(data)
		if q.seenHashes[hash] {
			continue
		}

		sig := computePathSignature(data)

		entry := &QueueEntry{
			ID:            generateID(),
			Data:          data,
			Hash:          hash,
			PathSignature: sig,
			Score:         1,
			Depth:         1,
			Favored:       true,
			Importance:    1.0,
			MutationType:  "loaded",
			CreatedAt:     time.Now(),
		}

		q.entries = append(q.entries, entry)
		q.seenHashes[hash] = true
		if !q.seenSignatures[sig] {
			q.seenSignatures[sig] = true
			q.totalPaths++
		}
	}

	return nil
}

func computeHash(data []byte) string {
	h := sha256.New()
	h.Write(data)
	return hex.EncodeToString(h.Sum(nil))
}

func computePathSignature(data []byte) uint64 {
	var h hash.Hash64 = newFNV1a64()
	h.Write(data)
	return h.Sum64()
}

type fnv1a64 struct {
	sum uint64
}

const (
	fnv64Offset uint64 = 14695981039346656037
	fnv64Prime  uint64 = 1099511628211
)

func newFNV1a64() *fnv1a64 {
	return &fnv1a64{sum: fnv64Offset}
}

func (f *fnv1a64) Write(data []byte) (int, error) {
	for _, b := range data {
		f.sum ^= uint64(b)
		f.sum *= fnv64Prime
	}
	return len(data), nil
}

func (f *fnv1a64) Sum64() uint64 {
	return f.sum
}

func (f *fnv1a64) BlockSize() int {
	return 1
}

func (f *fnv1a64) Size() int {
	return 8
}

func (f *fnv1a64) Reset() {
	f.sum = fnv64Offset
}

func (f *fnv1a64) Sum(b []byte) []byte {
	s := f.Sum64()
	return append(b, byte(s>>56), byte(s>>48), byte(s>>40), byte(s>>32), byte(s>>24), byte(s>>16), byte(s>>8), byte(s))
}

func generateID() string {
	b := make([]byte, 16)
	for i := range b {
		b[i] = byte(rand.Intn(256))
	}
	return hex.EncodeToString(b)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func (q *Queue) Trim() {
	q.mu.Lock()
	defer q.mu.Unlock()

	if len(q.entries) < 100 {
		return
	}

	sort.Slice(q.entries, func(i, j int) bool {
		return q.entries[i].Importance > q.entries[j].Importance
	})

	keepCount := max(100, len(q.entries)/2)
	q.entries = q.entries[:keepCount]

	q.seenHashes = make(map[string]bool)
	for _, e := range q.entries {
		q.seenHashes[e.Hash] = true
	}
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
