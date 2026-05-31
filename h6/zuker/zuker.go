package zuker

import (
	"math"
	"math/rand"
	"sort"
	"strings"
	"time"

	"rna-secondary-structure/models"
)

const (
	INF          = 1e9
	K            = 0.0019872
	TEMP_37C     = 310.15
	TEMP_47C     = 320.15
	TEMP         = TEMP_37C
	MIN_LOOP     = 3
	MAX_LOOP     = 30
)

var pairEnergy37C = map[string]float64{
	"GC": -3.42,
	"CG": -3.42,
	"AU": -2.24,
	"UA": -2.24,
	"GU": -1.72,
	"UG": -1.72,
}

var stackEnergy37C = map[string]float64{
	"GC/CG": -3.42,
	"CG/GC": -3.42,
	"GC/GC": -3.26,
	"CG/CG": -3.26,
	"AU/UA": -2.24,
	"UA/AU": -2.24,
	"AU/AU": -2.07,
	"UA/UA": -2.07,
	"GU/UG": -1.72,
	"UG/GU": -1.72,
	"GC/AU": -2.50,
	"AU/GC": -2.50,
	"CG/UA": -2.50,
	"UA/CG": -2.50,
	"GC/UG": -2.05,
	"UG/GC": -2.05,
	"CG/GU": -2.05,
	"GU/CG": -2.05,
	"AU/GU": -1.25,
	"GU/AU": -1.25,
	"UA/UG": -1.25,
	"UG/UA": -1.25,
}

var hairpinLoopEnergy = map[int]float64{
	3: 4.0,
	4: 3.5,
	5: 3.0,
	6: 2.5,
	7: 2.7,
	8: 2.9,
	9: 3.1,
	10: 3.3,
}

var internalLoopEnergy = map[int]float64{
	1: 0.0,
	2: 0.4,
	3: 0.8,
	4: 1.2,
	5: 1.6,
	6: 1.8,
}

type ZukerPredictor struct {
	n             int
	seq           string
	V             [][]float64
	W             [][]float64
	VBack         [][]int
	WBack         [][]int
	partition     [][]float64
	constraint    *models.FamilyConstraint
	shapeData     []float64
	shapeSlope    float64
	shapeIntercept float64
	useSHAPE      bool
}

func NewPredictor(seq string, constraint *models.FamilyConstraint) *ZukerPredictor {
	n := len(seq)
	upperSeq := strings.ToUpper(seq)

	V := make([][]float64, n)
	W := make([][]float64, n)
	VBack := make([][]int, n)
	WBack := make([][]int, n)
	partition := make([][]float64, n)

	for i := 0; i < n; i++ {
		V[i] = make([]float64, n)
		W[i] = make([]float64, n)
		VBack[i] = make([]int, n)
		WBack[i] = make([]int, n)
		partition[i] = make([]float64, n)

		for j := 0; j < n; j++ {
			V[i][j] = INF
			VBack[i][j] = -1
			WBack[i][j] = -1

			if j >= i {
				W[i][j] = 0
			} else {
				W[i][j] = INF
			}

			partition[i][j] = 0
			if j >= i {
				partition[i][j] = 1.0
			}
		}
	}

	return &ZukerPredictor{
		n:          n,
		seq:        upperSeq,
		V:          V,
		W:          W,
		VBack:      VBack,
		WBack:      WBack,
		partition:  partition,
		constraint: constraint,
		shapeData:  make([]float64, n),
		useSHAPE:   false,
	}
}

func NewPredictorWithSHAPE(seq string, shapeData []models.SHAPEData, slope, intercept float64, constraint *models.FamilyConstraint) *ZukerPredictor {
	predictor := NewPredictor(seq, constraint)

	n := len(seq)
	shapeArray := make([]float64, n)
	for i := range shapeArray {
		shapeArray[i] = -1.0
	}

	for _, sd := range shapeData {
		if sd.Position >= 0 && sd.Position < n {
			shapeArray[sd.Position] = sd.Reactivity
		}
	}

	if slope == 0 {
		slope = 1.8
	}
	if intercept == 0 {
		intercept = -0.6
	}

	predictor.shapeData = shapeArray
	predictor.shapeSlope = slope
	predictor.shapeIntercept = intercept
	predictor.useSHAPE = true

	return predictor
}

func (z *ZukerPredictor) getSHAPEPseudoEnergy(i, j int) float64 {
	if !z.useSHAPE {
		return 0
	}

	if z.shapeData[i] < 0 || z.shapeData[j] < 0 {
		return 0
	}

	reactivityI := z.shapeData[i]
	reactivityJ := z.shapeData[j]

	if reactivityI > 0.7 || reactivityJ > 0.7 {
		return 3.0
	}

	pseudoE := z.shapeSlope * (reactivityI + reactivityJ) / 2.0
	return math.Max(0, pseudoE+z.shapeIntercept)
}

func (z *ZukerPredictor) getSHAPESingleEnergy(i int) float64 {
	if !z.useSHAPE || z.shapeData[i] < 0 {
		return 0
	}

	reactivity := z.shapeData[i]
	if reactivity > 0.7 {
		return -0.5
	}
	if reactivity < 0.3 {
		return 0.3
	}
	return 0
}

func (z *ZukerPredictor) canPair(i, j int) bool {
	if j-i <= MIN_LOOP {
		return false
	}
	base := string(z.seq[i]) + string(z.seq[j])
	_, ok := pairEnergy[base]
	if !ok {
		return false
	}

	if z.constraint != nil {
		for _, unpair := range z.constraint.MustUnpair {
			if i == unpair || j == unpair {
				return false
			}
		}
	}

	return true
}

func (z *ZukerPredictor) getPairEnergy(i, j int) float64 {
	base := string(z.seq[i]) + string(z.seq[j])
	if e, ok := pairEnergy37C[base]; ok {
		return e
	}
	return INF
}

func (z *ZukerPredictor) getStackEnergy(i, j, ip, jp int) float64 {
	key := string(z.seq[i]) + string(z.seq[j]) + "/" + string(z.seq[ip]) + string(z.seq[jp])
	if e, ok := stackEnergy37C[key]; ok {
		return e
	}
	return z.getPairEnergy(i, j)
}

func (z *ZukerPredictor) getHairpinEnergy(size int) float64 {
	if size < MIN_LOOP {
		return INF
	}
	if e, ok := hairpinLoopEnergy[size]; ok {
		return e
	}
	return 3.0 + 0.1*float64(size)
}

func (z *ZukerPredictor) getInternalLoopEnergy(size int) float64 {
	if size <= 0 {
		return INF
	}
	if e, ok := internalLoopEnergy[size]; ok {
		return e
	}
	return 1.5 + 0.2*float64(size)
}

func (z *ZukerPredictor) getBulgeEnergy(size int) float64 {
	if size <= 0 {
		return INF
	}
	return 1.0 + 0.3*float64(size)
}

func (z *ZukerPredictor) isMustPair(i, j int) bool {
	if z.constraint == nil {
		return false
	}
	for _, p := range z.constraint.MustPair {
		if (p[0] == i && p[1] == j) || (p[0] == j && p[1] == i) {
			return true
		}
	}
	return false
}

func (z *ZukerPredictor) ComputeMFE() (float64, string) {
	n := z.n

	for l := MIN_LOOP + 1; l < n; l++ {
		for i := 0; i+l < n; i++ {
			j := i + l

			if j-i <= MIN_LOOP {
				hairpinSize := j - i - 1
				if hairpinSize >= MIN_LOOP {
					z.V[i][j] = z.getHairpinEnergy(hairpinSize)
					z.VBack[i][j] = -5
				}
				z.W[i][j] = 0
				continue
			}

			z.W[i][j] = z.W[i+1][j]
			z.WBack[i][j] = -2

			if z.W[i][j-1] < z.W[i][j] {
				z.W[i][j] = z.W[i][j-1]
				z.WBack[i][j] = -3
			}

			if z.canPair(i, j) {
				e := z.getPairEnergy(i, j)
				shapeE := z.getSHAPEPseudoEnergy(i, j)
				totalE := e + shapeE
				hairpinSize := j - i - 1

				if hairpinSize >= MIN_LOOP {
					hairpinE := z.getHairpinEnergy(hairpinSize) + totalE
					if hairpinE < z.V[i][j] {
						z.V[i][j] = hairpinE
						z.VBack[i][j] = -5
					}
				}

				if z.W[i+1][j-1] != INF {
					stackE := z.W[i+1][j-1] + totalE
					if stackE < z.V[i][j] {
						z.V[i][j] = stackE
						z.VBack[i][j] = -1
					}
				}

				for k := i + 1; k < j-1; k++ {
					if z.W[i+1][k] != INF && z.W[k+1][j-1] != INF {
						internalSize := (k - i - 1) + (j - k - 2)
						loopE := z.getInternalLoopEnergy(internalSize)
						shapeSingleE := z.getSHAPESingleEnergy(k)
						candidate := z.W[i+1][k] + z.W[k+1][j-1] + totalE + loopE + shapeSingleE
						if candidate < z.V[i][j] {
							z.V[i][j] = candidate
							z.VBack[i][j] = k
						}
					}
				}

				for k := i + MIN_LOOP + 1; k < j; k++ {
					if z.canPair(i, k) && z.canPair(k+1, j) {
						if z.V[i][k] != INF && z.V[k+1][j] != INF {
							pseudoknotE := z.V[i][k] + z.V[k+1][j] - 1.0
							if pseudoknotE < z.V[i][j] {
								z.V[i][j] = pseudoknotE
								z.VBack[i][j] = -6
							}
						}
					}
				}

				for k := i + MIN_LOOP + 2; k < j-1; k++ {
					if z.canPair(i, k) {
						for m := k + 1; m < j; m++ {
							if z.canPair(m, j) && m-k > MIN_LOOP {
								if z.W[i+1][k-1] != INF && z.W[k+1][m-1] != INF && z.W[m+1][j-1] != INF {
									candidate := z.W[i+1][k-1] + z.W[k+1][m-1] + z.W[m+1][j-1] +
										z.getPairEnergy(i, k) + z.getPairEnergy(m, j) +
										z.getSHAPEPseudoEnergy(i, k) + z.getSHAPEPseudoEnergy(m, j)
									if candidate < z.V[i][j] {
										z.V[i][j] = candidate
										z.VBack[i][j] = -7
									}
								}
							}
						}
					}
				}

				if z.V[i][j] < z.W[i][j] {
					z.W[i][j] = z.V[i][j]
					z.WBack[i][j] = -4
				}
			}

			for k := i + 1; k < j; k++ {
				if z.W[i][k] != INF && z.W[k+1][j] != INF {
					if z.W[i][k]+z.W[k+1][j] < z.W[i][j] {
						z.W[i][j] = z.W[i][k] + z.W[k+1][j]
						z.WBack[i][j] = k
					}
				}
			}

			if z.isMustPair(i, j) && z.canPair(i, j) {
				e := z.getPairEnergy(i, j)
				penalty := -10.0
				if z.W[i+1][j-1] != INF {
					candidate := z.W[i+1][j-1] + e + penalty
					if candidate < z.W[i][j] {
						z.W[i][j] = candidate
						z.WBack[i][j] = -4
					}
				}
			}

			if z.W[i][j] > INF/2 {
				z.W[i][j] = 0
			}
		}
	}

	mfe := z.W[0][n-1]
	if math.Abs(mfe) < 1e-6 || mfe >= INF/2 {
		mfe = 0
	}

	structure := z.backtrack(0, n-1)

	if len(structure) != n {
		structure = strings.Repeat(".", n)
	}

	return mfe, structure
}

func (z *ZukerPredictor) backtrack(i, j int) string {
	if i > j {
		return ""
	}
	if i == j {
		return "."
	}

	if z.WBack[i][j] == -2 {
		return "." + z.backtrack(i+1, j)
	}

	if z.WBack[i][j] == -3 {
		return z.backtrack(i, j-1) + "."
	}

	if z.WBack[i][j] == -4 {
		return "(" + z.backtrackV(i, j) + ")"
	}

	if z.WBack[i][j] >= 0 {
		k := z.WBack[i][j]
		return z.backtrack(i, k) + z.backtrack(k+1, j)
	}

	return strings.Repeat(".", j-i+1)
}

func (z *ZukerPredictor) backtrackV(i, j int) string {
	if i >= j-1 {
		return ""
	}

	if z.VBack[i][j] == -1 {
		return z.backtrack(i+1, j-1)
	}

	if z.VBack[i][j] == -5 {
		return strings.Repeat(".", j-i-1)
	}

	if z.VBack[i][j] == -6 {
		for k := i + MIN_LOOP + 1; k < j; k++ {
			if z.canPair(i, k) && z.canPair(k+1, j) {
				return "(" + z.backtrackV(i, k) + ")(" + z.backtrackV(k+1, j) + ")"
			}
		}
		return z.backtrack(i+1, j-1)
	}

	if z.VBack[i][j] == -7 {
		for k := i + MIN_LOOP + 2; k < j-1; k++ {
			if z.canPair(i, k) {
				for m := k + 1; m < j; m++ {
					if z.canPair(m, j) && m-k > MIN_LOOP {
						return "(" + z.backtrack(i+1, k-1) + ")" +
							z.backtrack(k+1, m-1) +
							"(" + z.backtrack(m+1, j-1) + ")"
					}
				}
			}
		}
		return z.backtrack(i+1, j-1)
	}

	k := z.VBack[i][j]
	if k >= 0 {
		if i+1 <= k && k+1 <= j-1 {
			return z.backtrack(i+1, k) + z.backtrack(k+1, j-1)
		}
	}

	return z.backtrack(i+1, j-1)
}

func (z *ZukerPredictor) ComputePartitionFunction() {
	n := z.n

	for i := 0; i < n; i++ {
		z.partition[i][i] = 1.0
		if i+1 < n {
			z.partition[i][i+1] = 1.0
		}
		if i+2 < n {
			z.partition[i][i+2] = 1.0
		}
		if i+3 < n {
			z.partition[i][i+3] = 1.0
		}
	}

	for l := 1; l < n; l++ {
		for i := 0; i+l < n; i++ {
			j := i + l

			if j-i <= MIN_LOOP {
				continue
			}

			z.partition[i][j] += z.partition[i+1][j]
			z.partition[i][j] += z.partition[i][j-1]

			if z.canPair(i, j) {
				e := z.getPairEnergy(i, j)
				boltzmann := math.Exp(-e / (K * TEMP))

				if i+1 <= j-1 {
					z.partition[i][j] += boltzmann * z.partition[i+1][j-1]
				}

				for k := i + 1; k < j; k++ {
					if i+1 <= k && k+1 <= j-1 {
						z.partition[i][j] += boltzmann * z.partition[i+1][k] * z.partition[k+1][j-1]
					}
				}
			}

			for k := i + 1; k < j; k++ {
				z.partition[i][j] += z.partition[i][k] * z.partition[k+1][j]
			}

			if z.partition[i][j] > 1e200 {
				z.partition[i][j] = 1e200
			}
			if z.partition[i][j] < 1e-200 {
				z.partition[i][j] = 1.0
			}
		}
	}
}

func (z *ZukerPredictor) ComputeBasePairProbs() []models.BasePairProb {
	n := z.n
	z.ComputePartitionFunction()

	totalQ := z.partition[0][n-1]
	if totalQ < 1e-10 || math.IsInf(totalQ, 0) || math.IsNaN(totalQ) {
		return []models.BasePairProb{}
	}

	var probs []models.BasePairProb

	for i := 0; i < n; i++ {
		for j := i + MIN_LOOP + 1; j < n; j++ {
			if !z.canPair(i, j) {
				continue
			}

			e := z.getPairEnergy(i, j)
			boltzmann := math.Exp(-e / (K * TEMP))

			var q float64
			if i+1 <= j-1 {
				innerQ := z.partition[i+1][j-1]
				if innerQ > 0 && !math.IsInf(innerQ, 0) && !math.IsNaN(innerQ) {
					q = boltzmann * innerQ
				}
			} else {
				q = boltzmann
			}

			if q <= 0 || math.IsInf(q, 0) || math.IsNaN(q) {
				continue
			}

			prob := q / totalQ

			if prob > 1.0 {
				prob = 1.0
			}
			if prob > 0.001 {
				probs = append(probs, models.BasePairProb{
					I:           i,
					J:           j,
					BaseI:       string(z.seq[i]),
					BaseJ:       string(z.seq[j]),
					Probability: math.Round(prob*1000) / 1000,
				})
			}
		}
	}

	return probs
}

func Predict(seq string, constraint *models.FamilyConstraint) *models.RNAResponse {
	predictor := NewPredictor(seq, constraint)
	mfe, structure := predictor.ComputeMFE()
	probs := predictor.ComputeBasePairProbs()

	return &models.RNAResponse{
		Sequence:         seq,
		Structure:        structure,
		MinFreeEnergy:    math.Round(mfe*100) / 100,
		BasePairProbs:    probs,
		FromCache:        false,
		FamilyConstraint: constraint,
	}
}

func PredictWithSHAPE(seq string, shapeData []models.SHAPEData, slope, intercept float64, constraint *models.FamilyConstraint) *models.RNAResponse {
	predictor := NewPredictorWithSHAPE(seq, shapeData, slope, intercept, constraint)
	mfe, structure := predictor.ComputeMFE()
	probs := predictor.ComputeBasePairProbs()

	return &models.RNAResponse{
		Sequence:         seq,
		Structure:        structure,
		MinFreeEnergy:    math.Round(mfe*100) / 100,
		BasePairProbs:    probs,
		FromCache:        false,
		FamilyConstraint: constraint,
	}
}

func (z *ZukerPredictor) computeEnergy(structure string) float64 {
	n := z.n
	energy := 0.0

	stack := make([]int, 0, n)
	partners := make([]int, n)
	for i := range partners {
		partners[i] = -1
	}

	for i, c := range structure {
		if c == '(' {
			stack = append(stack, i)
		} else if c == ')' {
			if len(stack) > 0 {
				j := stack[len(stack)-1]
				stack = stack[:len(stack)-1]
				partners[i] = j
				partners[j] = i
			}
		}
	}

	for i := 0; i < n; i++ {
		if partners[i] > i {
			j := partners[i]
			energy += z.getPairEnergy(i, j)
			energy += z.getSHAPEPseudoEnergy(i, j)

			if partners[i+1] != -1 && partners[i+1] == j-1 && j-1 > i+1 {
				energy += z.getStackEnergy(i, j, i+1, j-1)
			}
		} else {
			energy += z.getSHAPESingleEnergy(i)
		}
	}

	for i := 0; i < n; i++ {
		if partners[i] > i {
			j := partners[i]
			unpaired := 0
			for k := i + 1; k < j; k++ {
				if partners[k] == -1 {
					unpaired++
				}
			}
			if unpaired > 0 && unpaired < 10 {
				energy += z.getHairpinEnergy(unpaired)
			}
		}
	}

	return math.Round(energy*100) / 100
}

func (z *ZukerPredictor) stochasticSample(temperature float64) string {
	n := z.n
	if temperature <= 0 {
		temperature = TEMP
	}

	structure := make([]byte, n)
	for i := range structure {
		structure[i] = '.'
	}

	stack := make([]int, 0, n)
	available := make([]bool, n)
	for i := range available {
		available[i] = true
	}

	for i := 0; i < n; i++ {
		if !available[i] {
			continue
		}

		options := make([]struct {
			j     int
			prob  float64
			energy float64
		}, 0)

		options = append(options, struct {
			j     int
			prob  float64
			energy float64
		}{j: -1, prob: 1.0, energy: 0})

		for j := i + MIN_LOOP + 1; j < n; j++ {
			if !available[j] || !z.canPair(i, j) {
				continue
			}

			e := z.getPairEnergy(i, j) + z.getSHAPEPseudoEnergy(i, j)
			prob := math.Exp(-e / (K * temperature))
			options = append(options, struct {
				j     int
				prob  float64
				energy float64
			}{j: j, prob: prob, energy: e})
		}

		total := 0.0
		for _, opt := range options {
			total += opt.prob
		}

		if total > 0 {
			r := rand.Float64() * total
			cumulative := 0.0
			chosen := -1
			for idx, opt := range options {
				cumulative += opt.prob
				if r <= cumulative {
					chosen = idx
					break
				}
			}

			if chosen > 0 {
				j := options[chosen].j
				structure[i] = '('
				structure[j] = ')'
				available[i] = false
				available[j] = false
				stack = append(stack, i)

				for k := i + 1; k < j; k++ {
					available[k] = true
				}
			}
		}
	}

	return string(structure)
}

func SampleStructures(seq string, numSamples int, temperature float64, maxEnergyDiff float64) *models.SamplingResponse {
	rand.Seed(time.Now().UnixNano())

	if numSamples <= 0 {
		numSamples = 100
	}
	if numSamples > 10000 {
		numSamples = 10000
	}

	predictor := NewPredictor(seq, nil)
	mfe, mfeStructure := predictor.ComputeMFE()
	predictor.ComputePartitionFunction()

	if temperature <= 0 {
		temperature = TEMP
	}
	if maxEnergyDiff <= 0 {
		maxEnergyDiff = 5.0
	}

	samples := make([]string, numSamples)
	for i := 0; i < numSamples; i++ {
		samples[i] = predictor.stochasticSample(temperature)
	}

	freqMap := make(map[string]int)
	energyMap := make(map[string]float64)

	for _, s := range samples {
		freqMap[s]++
		if _, ok := energyMap[s]; !ok {
			energyMap[s] = predictor.computeEnergy(s)
		}
	}

	type structInfo struct {
		structure string
		energy    float64
		freq      int
	}

	structList := make([]structInfo, 0, len(freqMap))
	for s, freq := range freqMap {
		e := energyMap[s]
		if e-mfe <= maxEnergyDiff {
			structList = append(structList, structInfo{
				structure: s,
				energy:    e,
				freq:      freq,
			})
		}
	}

	sort.Slice(structList, func(i, j int) bool {
		return structList[i].energy < structList[j].energy
	})

	if len(structList) > 50 {
		structList = structList[:50]
	}

	boltzmannSum := 0.0
	for _, s := range structList {
		boltzmannSum += math.Exp(-(s.energy - mfe) / (K * temperature))
	}

	resultStructures := make([]models.SampledStructure, 0, len(structList))
	ensembleDefect := 0.0

	for _, s := range structList {
		prob := 0.0
		if boltzmannSum > 0 {
			prob = math.Exp(-(s.energy - mfe) / (K * temperature)) / boltzmannSum
		}
		prob = math.Round(prob*1000) / 1000

		resultStructures = append(resultStructures, models.SampledStructure{
			Structure:   s.structure,
			Energy:      math.Round(s.energy*100) / 100,
			Probability: prob,
			Frequency:   s.freq,
		})

		ensembleDefect += prob * math.Abs(s.energy - mfe)
	}

	return &models.SamplingResponse{
		Sequence:         seq,
		MFEStructure:     mfeStructure,
		MFEnergy:         math.Round(mfe*100) / 100,
		NumSamples:       numSamples,
		UniqueStructures: len(structList),
		Structures:       resultStructures,
		EnsembleDefect:   math.Round(ensembleDefect*100) / 100,
	}
}
