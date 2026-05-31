package models

type RNARequest struct {
	Sequence string `json:"sequence" binding:"required"`
}

type SHAPEData struct {
	Position    int     `json:"position"`
	Reactivity  float64 `json:"reactivity"`
}

type SHAPERequest struct {
	Sequence     string      `json:"sequence" binding:"required"`
	SHAPEData    []SHAPEData `json:"shape_data"`
	SHAPESlope   float64     `json:"shape_slope,omitempty"`
	SHAPEIntercept float64   `json:"shape_intercept,omitempty"`
}

type SamplingRequest struct {
	Sequence      string  `json:"sequence" binding:"required"`
	NumSamples    int     `json:"num_samples,omitempty"`
	Temperature   float64 `json:"temperature,omitempty"`
	MaxEnergyDiff float64 `json:"max_energy_diff,omitempty"`
}

type SampledStructure struct {
	Structure    string  `json:"structure"`
	Energy       float64 `json:"energy"`
	Probability  float64 `json:"probability"`
	Frequency    int     `json:"frequency"`
}

type SamplingResponse struct {
	Sequence        string             `json:"sequence"`
	MFEStructure    string             `json:"mfe_structure"`
	MFEnergy        float64            `json:"mfe_energy"`
	NumSamples      int                `json:"num_samples"`
	UniqueStructures int               `json:"unique_structures"`
	Structures      []SampledStructure `json:"structures"`
	EnsembleDefect  float64            `json:"ensemble_defect"`
}

type MSARequest struct {
	Sequences   []string `json:"sequences" binding:"required"`
	ConsensusCutoff float64 `json:"consensus_cutoff,omitempty"`
	UseCovariation bool `json:"use_covariation,omitempty"`
}

type MSAResponse struct {
	Sequences        []string           `json:"sequences"`
	CommonStructure  string             `json:"common_structure"`
	ConsensusPairs   [][2]int           `json:"consensus_pairs"`
	ConservationScores []float64        `json:"conservation_scores"`
	CovariationScores map[string]float64 `json:"covariation_scores,omitempty"`
	IndividualStructures []string       `json:"individual_structures"`
}

type BasePairProb struct {
	I           int     `json:"i"`
	J           int     `json:"j"`
	BaseI       string  `json:"base_i"`
	BaseJ       string  `json:"base_j"`
	Probability float64 `json:"probability"`
}

type RNAResponse struct {
	Sequence         string             `json:"sequence"`
	Structure        string             `json:"structure"`
	MinFreeEnergy    float64            `json:"min_free_energy"`
	BasePairProbs    []BasePairProb     `json:"base_pair_probabilities"`
	FromCache        bool               `json:"from_cache"`
	BloomFiltered    bool               `json:"bloom_filtered,omitempty"`
	FamilyConstraint *FamilyConstraint  `json:"family_constraint,omitempty"`
}

type FamilyConstraint struct {
	FamilyName string   `json:"family_name"`
	MustPair   [][2]int `json:"must_pair"`
	MustUnpair []int    `json:"must_unpair"`
}

type RNAFamily struct {
	ID             int    `json:"id"`
	Name           string `json:"name"`
	Pattern        string `json:"pattern"`
	MustPairJSON   string `json:"must_pair"`
	MustUnpairJSON string `json:"must_unpair"`
	CreatedAt      string `json:"created_at"`
}
