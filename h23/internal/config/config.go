package config

type TestConfig struct {
	SignificanceLevel float64 `json:"significance_level"`

	BlockFrequencyBlockSize int `json:"block_frequency_block_size"`

	RunsBlockSize int `json:"runs_block_size"`

	LongestRunBlockSize int `json:"longest_run_block_size"`

	RankMatrixRows int `json:"rank_matrix_rows"`
	RankMatrixCols int `json:"rank_matrix_cols"`

	NonOverlappingTemplateLength int      `json:"non_overlapping_template_length"`
	NonOverlappingTemplates      []string `json:"non_overlapping_templates,omitempty"`

	OverlappingTemplateLength int `json:"overlapping_template_length"`
	OverlappingBlockSize      int `json:"overlapping_block_size"`

	UniversalL        int `json:"universal_L"`
	UniversalQ        int `json:"universal_Q"`
	UniversalK        int `json:"universal_K"`

	LZCompressionBlockSize int `json:"lz_compression_block_size"`

	LinearComplexityBlockSize int `json:"linear_complexity_block_size"`

	SerialBlockSize int `json:"serial_block_size"`

	ApproximateEntropyBlockSize int `json:"approximate_entropy_block_size"`

	CumulativeSumMode int `json:"cumulative_sum_mode"`

	RandomExcursionsState int `json:"random_excursions_state"`
}

func DefaultConfig() *TestConfig {
	return &TestConfig{
		SignificanceLevel:         0.01,
		BlockFrequencyBlockSize:   128,
		RunsBlockSize:             10000,
		LongestRunBlockSize:       10000,
		RankMatrixRows:            32,
		RankMatrixCols:            32,
		NonOverlappingTemplateLength: 9,
		OverlappingTemplateLength: 9,
		OverlappingBlockSize:      1000000,
		UniversalL:                7,
		UniversalQ:                1280,
		UniversalK:                40,
		LZCompressionBlockSize:    1000,
		LinearComplexityBlockSize: 1000,
		SerialBlockSize:           16,
		ApproximateEntropyBlockSize: 10,
		CumulativeSumMode:         0,
		RandomExcursionsState:     1,
	}
}
