package network

import (
	"fmt"
	"math/rand"
	"net"
	"sync"
	"time"
)

type PerturbationType int

const (
	PerturbDelay PerturbationType = iota
	PerturbPacketLoss
	PerturbPacketDuplication
	PerturbPacketReorder
	PerturbBandwidthLimit
	PerturbBitFlip
)

type PerturbationConfig struct {
	Enabled               bool
	BaseLatency           time.Duration
	LatencyJitter         time.Duration
	LossRate              float64
	DuplicationRate       float64
	ReorderRate           float64
	ReorderMaxDelay       time.Duration
	BandwidthLimitBytesSec int
	BitFlipRate           float64
	BurstLossRate         float64
	BurstLossMinPackets   int
	BurstLossMaxPackets   int
}

type ConnectionStats struct {
	BytesSent       int64
	BytesReceived   int64
	PacketsSent     int64
	PacketsReceived int64
	PacketsDropped  int64
	PacketsDuplicated int64
	PacketsReordered int64
	BitFlips        int64
	AvgLatency      time.Duration
}

type PerturbedConn struct {
	net.Conn
	cfg    *PerturbationConfig
	rng    *rand.Rand
	stats  ConnectionStats
	mu     sync.Mutex
	sendBuf []byte
	recvBuf []byte
	lastSendTime time.Time
	lastRecvTime time.Time
	totalBytesSent int64
	totalBytesRecv int64
	latencySamples []time.Duration
	burstLossRemaining int
}

func NewPerturbedConn(conn net.Conn, cfg *PerturbationConfig) *PerturbedConn {
	if cfg == nil {
		cfg = &PerturbationConfig{Enabled: false}
	}

	return &PerturbedConn{
		Conn:    conn,
		cfg:     cfg,
		rng:     rand.New(rand.NewSource(time.Now().UnixNano())),
		recvBuf: make([]byte, 0, 65536),
	}
}

func DefaultPerturbationConfig() *PerturbationConfig {
	return &PerturbationConfig{
		Enabled:               false,
		BaseLatency:           0,
		LatencyJitter:         0,
		LossRate:              0,
		DuplicationRate:       0,
		ReorderRate:           0,
		ReorderMaxDelay:       100 * time.Millisecond,
		BandwidthLimitBytesSec: 0,
		BitFlipRate:           0,
		BurstLossRate:         0,
		BurstLossMinPackets:   3,
		BurstLossMaxPackets:   10,
	}
}

func (pc *PerturbedConn) Write(b []byte) (int, error) {
	if !pc.cfg.Enabled {
		return pc.Conn.Write(b)
	}

	pc.mu.Lock()
	defer pc.mu.Unlock()

	if pc.burstLossRemaining > 0 {
		pc.burstLossRemaining--
		pc.stats.PacketsDropped++
		return len(b), nil
	}

	if pc.cfg.BurstLossRate > 0 && pc.rng.Float64() < pc.cfg.BurstLossRate {
		pc.burstLossRemaining = pc.rng.Intn(
			pc.cfg.BurstLossMaxPackets-pc.cfg.BurstLossMinPackets+1,
		) + pc.cfg.BurstLossMinPackets
		pc.stats.PacketsDropped++
		return len(b), nil
	}

	if pc.cfg.LossRate > 0 && pc.rng.Float64() < pc.cfg.LossRate {
		pc.stats.PacketsDropped++
		return len(b), nil
	}

	data := make([]byte, len(b))
	copy(data, b)

	if pc.cfg.BitFlipRate > 0 {
		flipped := pc.applyBitFlips(data)
		pc.stats.BitFlips += int64(flipped)
	}

	if pc.cfg.BaseLatency > 0 || pc.cfg.LatencyJitter > 0 {
		latency := pc.calculateLatency()
		pc.recordLatency(latency)
		time.Sleep(latency)
	}

	if pc.cfg.BandwidthLimitBytesSec > 0 {
		pc.applyBandwidthThrottle(len(data), true)
	}

	var totalWritten int
	if pc.cfg.DuplicationRate > 0 && pc.rng.Float64() < pc.cfg.DuplicationRate {
		n1, err := pc.Conn.Write(data)
		if err != nil {
			return n1, err
		}
		time.Sleep(time.Millisecond * time.Duration(pc.rng.Intn(10)+1))
		_, err = pc.Conn.Write(data)
		if err != nil {
			return n1, err
		}
		totalWritten = n1
		pc.stats.PacketsDuplicated++
	} else {
		n, err := pc.Conn.Write(data)
		totalWritten = n
		if err != nil {
			return n, err
		}
	}

	pc.stats.BytesSent += int64(totalWritten)
	pc.stats.PacketsSent++
	pc.lastSendTime = time.Now()
	pc.totalBytesSent += int64(totalWritten)

	return totalWritten, nil
}

func (pc *PerturbedConn) Read(b []byte) (int, error) {
	if !pc.cfg.Enabled {
		return pc.Conn.Read(b)
	}

	pc.mu.Lock()
	if len(pc.recvBuf) > 0 {
		n := copy(b, pc.recvBuf)
		pc.recvBuf = pc.recvBuf[n:]
		pc.stats.BytesReceived += int64(n)
		pc.stats.PacketsReceived++
		pc.mu.Unlock()
		return n, nil
	}
	pc.mu.Unlock()

	tmpBuf := make([]byte, len(b)*2)
	n, err := pc.Conn.Read(tmpBuf)
	if err != nil {
		return n, err
	}

	data := tmpBuf[:n]

	pc.mu.Lock()
	defer pc.mu.Unlock()

	if pc.cfg.BaseLatency > 0 || pc.cfg.LatencyJitter > 0 {
		latency := pc.calculateLatency()
		pc.recordLatency(latency)
		time.Sleep(latency)
	}

	if pc.cfg.BitFlipRate > 0 {
		flipped := pc.applyBitFlips(data)
		pc.stats.BitFlips += int64(flipped)
	}

	if pc.cfg.ReorderRate > 0 && pc.rng.Float64() < pc.cfg.ReorderRate {
		pc.recvBuf = append(pc.recvBuf, data...)
		pc.stats.PacketsReordered++

		go func(d []byte) {
			time.Sleep(pc.cfg.ReorderMaxDelay)
			pc.mu.Lock()
			defer pc.mu.Unlock()
			pc.recvBuf = append(pc.recvBuf, d...)
		}(make([]byte, 0))

		if len(pc.recvBuf) > 0 {
			n = copy(b, pc.recvBuf)
			pc.recvBuf = pc.recvBuf[n:]
			pc.stats.BytesReceived += int64(n)
			pc.stats.PacketsReceived++
			return n, nil
		}
	}

	if pc.cfg.BandwidthLimitBytesSec > 0 {
		pc.applyBandwidthThrottle(len(data), false)
	}

	n = copy(b, data)
	pc.stats.BytesReceived += int64(n)
	pc.stats.PacketsReceived++
	pc.lastRecvTime = time.Now()
	pc.totalBytesRecv += int64(n)

	return n, nil
}

func (pc *PerturbedConn) calculateLatency() time.Duration {
	latency := pc.cfg.BaseLatency
	if pc.cfg.LatencyJitter > 0 {
		jitter := time.Duration(pc.rng.Int63n(int64(pc.cfg.LatencyJitter)*2)) - pc.cfg.LatencyJitter
		latency += jitter
	}
	if latency < 0 {
		latency = 0
	}
	return latency
}

func (pc *PerturbedConn) applyBitFlips(data []byte) int {
	flipped := 0
	for i := range data {
		for bit := 0; bit < 8; bit++ {
			if pc.rng.Float64() < pc.cfg.BitFlipRate {
				data[i] ^= (1 << bit)
				flipped++
			}
		}
	}
	return flipped
}

func (pc *PerturbedConn) applyBandwidthThrottle(bytes int, isSend bool) {
	if pc.cfg.BandwidthLimitBytesSec <= 0 {
		return
	}

	var lastTime time.Time
	var totalBytes int64
	if isSend {
		lastTime = pc.lastSendTime
		totalBytes = pc.totalBytesSent
	} else {
		lastTime = pc.lastRecvTime
		totalBytes = pc.totalBytesRecv
	}

	if lastTime.IsZero() {
		return
	}

	elapsed := time.Since(lastTime).Seconds()
	expectedBytes := float64(pc.cfg.BandwidthLimitBytesSec) * elapsed

	if float64(totalBytes+int64(bytes)) > expectedBytes {
		excessBytes := float64(totalBytes+int64(bytes)) - expectedBytes
		waitTime := excessBytes / float64(pc.cfg.BandwidthLimitBytesSec)
		time.Sleep(time.Duration(waitTime * float64(time.Second)))
	}
}

func (pc *PerturbedConn) recordLatency(latency time.Duration) {
	pc.latencySamples = append(pc.latencySamples, latency)
	if len(pc.latencySamples) > 1000 {
		pc.latencySamples = pc.latencySamples[1:]
	}

	var total time.Duration
	for _, l := range pc.latencySamples {
		total += l
	}
	pc.stats.AvgLatency = total / time.Duration(len(pc.latencySamples))
}

func (pc *PerturbedConn) GetStats() ConnectionStats {
	pc.mu.Lock()
	defer pc.mu.Unlock()
	return pc.stats
}

func (pc *PerturbedConn) ResetStats() {
	pc.mu.Lock()
	defer pc.mu.Unlock()
	pc.stats = ConnectionStats{}
	pc.latencySamples = pc.latencySamples[:0]
}

func (pc *PerturbedConn) UpdateConfig(newCfg *PerturbationConfig) {
	pc.mu.Lock()
	defer pc.mu.Unlock()
	pc.cfg = newCfg
}

type PerturbationProfile struct {
	Name        string
	Description string
	Config      *PerturbationConfig
}

func GetBuiltinProfiles() []*PerturbationProfile {
	return []*PerturbationProfile{
		{
			Name:        "ideal",
			Description: "Ideal network conditions - no perturbation",
			Config: &PerturbationConfig{
				Enabled: false,
			},
		},
		{
			Name:        "wan",
			Description: "WAN conditions - 100ms latency, 20ms jitter, 0.5% loss",
			Config: &PerturbationConfig{
				Enabled:       true,
				BaseLatency:   100 * time.Millisecond,
				LatencyJitter: 20 * time.Millisecond,
				LossRate:      0.005,
			},
		},
		{
			Name:        "cellular_3g",
			Description: "3G cellular network - 300ms latency, 100ms jitter, 2% loss",
			Config: &PerturbationConfig{
				Enabled:               true,
				BaseLatency:           300 * time.Millisecond,
				LatencyJitter:         100 * time.Millisecond,
				LossRate:              0.02,
				BandwidthLimitBytesSec: 1 * 1024 * 1024,
			},
		},
		{
			Name:        "cellular_4g",
			Description: "4G LTE network - 50ms latency, 10ms jitter, 0.5% loss",
			Config: &PerturbationConfig{
				Enabled:               true,
				BaseLatency:           50 * time.Millisecond,
				LatencyJitter:         10 * time.Millisecond,
				LossRate:              0.005,
				BandwidthLimitBytesSec: 10 * 1024 * 1024,
			},
		},
		{
			Name:        "satellite",
			Description: "Satellite network - 600ms latency, 50ms jitter, 1% loss",
			Config: &PerturbationConfig{
				Enabled:               true,
				BaseLatency:           600 * time.Millisecond,
				LatencyJitter:         50 * time.Millisecond,
				LossRate:              0.01,
				BandwidthLimitBytesSec: 512 * 1024,
			},
		},
		{
			Name:        "lossy",
			Description: "Extremely lossy network - 10% loss with bursts",
			Config: &PerturbationConfig{
				Enabled:             true,
				LossRate:            0.05,
				BurstLossRate:       0.01,
				BurstLossMinPackets: 5,
				BurstLossMaxPackets: 20,
			},
		},
		{
			Name:        "unreliable",
			Description: "Highly unreliable - packet loss, duplication, reordering",
			Config: &PerturbationConfig{
				Enabled:         true,
				LossRate:        0.03,
				DuplicationRate: 0.01,
				ReorderRate:     0.02,
				ReorderMaxDelay: 500 * time.Millisecond,
				BitFlipRate:     0.0001,
			},
		},
		{
			Name:        "throttled",
			Description: "Bandwidth throttled to 128KB/s",
			Config: &PerturbationConfig{
				Enabled:               true,
				BandwidthLimitBytesSec: 128 * 1024,
			},
		},
	}
}

func GetProfileByName(name string) (*PerturbationProfile, error) {
	for _, p := range GetBuiltinProfiles() {
		if p.Name == name {
			return p, nil
		}
	}
	return nil, fmt.Errorf("unknown perturbation profile: %s", name)
}

func GetPerturbationProfile(name string) *PerturbationConfig {
	profile, err := GetProfileByName(name)
	if err != nil {
		return nil
	}
	return profile.Config
}
