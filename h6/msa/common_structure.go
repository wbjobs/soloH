package msa

import (
	"math"
	"strings"

	"rna-secondary-structure/models"
	"rna-secondary-structure/zuker"
)

const (
	DefaultConsensusCutoff = 0.6
	MinAlignedLength       = 4
)

type SequenceInfo struct {
	Seq        string
	Structure  string
	BasePairs  map[[2]int]bool
	Partners   []int
}

func PredictCommonStructure(sequences []string, consensusCutoff float64, useCovariation bool) *models.MSAResponse {
	if len(sequences) == 0 {
		return &models.MSAResponse{}
	}

	if consensusCutoff <= 0 || consensusCutoff > 1 {
		consensusCutoff = DefaultConsensusCutoff
	}

	alignedSeqs := alignSequences(sequences)
	n := len(alignedSeqs[0])

	seqInfos := make([]*SequenceInfo, 0, len(alignedSeqs))
	individualStructures := make([]string, 0, len(alignedSeqs))

	for _, seq := range alignedSeqs {
		cleanSeq := strings.ReplaceAll(seq, "-", "")
		if len(cleanSeq) < MinAlignedLength {
			continue
		}

		response := zuker.Predict(cleanSeq, nil)
		partners := parseStructure(response.Structure)

		bpMap := make(map[[2]int]bool)
		for i, p := range partners {
			if p > i {
				bpMap[[2]int{i, p}] = true
			}
		}

		seqInfos = append(seqInfos, &SequenceInfo{
			Seq:       cleanSeq,
			Structure: response.Structure,
			BasePairs: bpMap,
			Partners:  partners,
		})
		individualStructures = append(individualStructures, response.Structure)
	}

	if len(seqInfos) == 0 {
		return &models.MSAResponse{
			Sequences:        sequences,
			CommonStructure:  strings.Repeat(".", n),
			ConsensusPairs:   [][2]int{},
			ConservationScores: make([]float64, n),
			IndividualStructures: individualStructures,
		}
	}

	pairFreq := make(map[[2]int]int)
	for _, si := range seqInfos {
		for bp := range si.BasePairs {
			pairFreq[bp]++
		}
	}

	minSupport := int(math.Ceil(float64(len(seqInfos)) * consensusCutoff))

	consensusPairs := make([][2]int, 0)
	for bp, freq := range pairFreq {
		if freq >= minSupport {
			consensusPairs = append(consensusPairs, bp)
		}
	}

	if useCovariation {
		covariationScores := computeCovariationScores(alignedSeqs, consensusPairs)
		filteredPairs := make([][2]int, 0)
		for _, bp := range consensusPairs {
			key := pairKey(bp[0], bp[1])
			if score, ok := covariationScores[key]; ok && score > 0.3 {
				filteredPairs = append(filteredPairs, bp)
			} else if !ok {
				filteredPairs = append(filteredPairs, bp)
			}
		}
		consensusPairs = filteredPairs
	}

	conservationScores := computeConservationScores(alignedSeqs)

	commonStructure := buildCommonStructure(n, consensusPairs)

	covariationScores := make(map[string]float64)
	if useCovariation {
		rawScores := computeCovariationScores(alignedSeqs, consensusPairs)
		for k, v := range rawScores {
			covariationScores[k] = math.Round(v*1000) / 1000
		}
	}

	return &models.MSAResponse{
		Sequences:            alignedSeqs,
		CommonStructure:      commonStructure,
		ConsensusPairs:       consensusPairs,
		ConservationScores:   conservationScores,
		CovariationScores:    covariationScores,
		IndividualStructures: individualStructures,
	}
}

func alignSequences(sequences []string) []string {
	if len(sequences) == 0 {
		return sequences
	}

	maxLen := 0
	for _, s := range sequences {
		if len(s) > maxLen {
			maxLen = len(s)
		}
	}

	aligned := make([]string, len(sequences))
	for i, s := range sequences {
		if len(s) < maxLen {
			aligned[i] = s + strings.Repeat("-", maxLen-len(s))
		} else {
			aligned[i] = s
		}
	}

	return aligned
}

func parseStructure(structure string) []int {
	n := len(structure)
	partners := make([]int, n)
	for i := range partners {
		partners[i] = -1
	}

	stack := make([]int, 0, n)
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

	return partners
}

func computeConservationScores(alignedSeqs []string) []float64 {
	if len(alignedSeqs) == 0 {
		return []float64{}
	}

	n := len(alignedSeqs[0])
	scores := make([]float64, n)
	numSeqs := float64(len(alignedSeqs))

	for i := 0; i < n; i++ {
		baseCounts := make(map[byte]float64)
		gapCount := 0.0

		for _, seq := range alignedSeqs {
			if i < len(seq) {
				c := seq[i]
				if c == '-' {
					gapCount++
				} else {
					baseCounts[c]++
				}
			}
		}

		maxBase := 0.0
		for _, count := range baseCounts {
			if count > maxBase {
				maxBase = count
			}
		}

		conservation := maxBase / (numSeqs - gapCount)
		if math.IsNaN(conservation) {
			conservation = 0
		}
		scores[i] = math.Round(conservation*1000) / 1000
	}

	return scores
}

func computeCovariationScores(alignedSeqs []string, pairs [][2]int) map[string]float64 {
	scores := make(map[string]float64)
	numSeqs := len(alignedSeqs)

	for _, bp := range pairs {
		i, j := bp[0], bp[1]
		key := pairKey(i, j)

		contingency := make(map[[2]byte]int)
		validCount := 0

		for _, seq := range alignedSeqs {
			if i >= len(seq) || j >= len(seq) {
				continue
			}
			ci, cj := seq[i], seq[j]
			if ci == '-' || cj == '-' {
				continue
			}
			if !isValidPair(ci, cj) {
				continue
			}
			contingency[[2]byte{ci, cj}]++
			validCount++
		}

		if validCount < 2 {
			scores[key] = 0
			continue
		}

		expected := make(map[[2]byte]float64)
		marginI := make(map[byte]float64)
		marginJ := make(map[byte]float64)

		for pair, count := range contingency {
			marginI[pair[0]] += float64(count) / float64(validCount)
			marginJ[pair[1]] += float64(count) / float64(validCount)
		}

		for pair := range contingency {
			expected[pair] = marginI[pair[0]] * marginJ[pair[1]] * float64(validCount)
		}

		chiSquare := 0.0
		for pair, observed := range contingency {
			exp := expected[pair]
			if exp > 0 {
				chiSquare += math.Pow(float64(observed)-exp, 2) / exp
			}
		}

		normalized := chiSquare / (float64(validCount) * 3)
		score := 1.0 - math.Exp(-normalized)
		scores[key] = math.Round(score*1000) / 1000
	}

	return scores
}

func buildCommonStructure(n int, pairs [][2]int) string {
	structure := make([]byte, n)
	for i := range structure {
		structure[i] = '.'
	}

	for _, bp := range pairs {
		i, j := bp[0], bp[1]
		if i < n && j < n && structure[i] == '.' && structure[j] == '.' {
			structure[i] = '('
			structure[j] = ')'
		}
	}

	return string(structure)
}

func isValidPair(a, b byte) bool {
	pairs := map[[2]byte]bool{
		{'A', 'U'}: true, {'U', 'A'}: true,
		{'G', 'C'}: true, {'C', 'G'}: true,
		{'G', 'U'}: true, {'U', 'G'}: true,
	}
	return pairs[[2]byte{a, b}]
}

func pairKey(i, j int) string {
	if i < j {
		return string(rune('A'+i)) + "-" + string(rune('A'+j))
	}
	return string(rune('A'+j)) + "-" + string(rune('A'+i))
}
