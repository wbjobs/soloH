package api

import (
	"fmt"
	"math"
	"net/http"
	"regexp"
	"strings"

	"github.com/gin-gonic/gin"

	"rna-secondary-structure/cache"
	"rna-secondary-structure/db"
	"rna-secondary-structure/models"
	"rna-secondary-structure/msa"
	"rna-secondary-structure/zuker"
)

type Handler struct {
	redis    *cache.RedisClient
	postgres *db.PostgresClient
}

func NewHandler(redis *cache.RedisClient, postgres *db.PostgresClient) *Handler {
	return &Handler{
		redis:    redis,
		postgres: postgres,
	}
}

func (h *Handler) PredictRNA(c *gin.Context) {
	var req models.RNARequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request body",
			"details": err.Error(),
		})
		return
	}

	seq := strings.ToUpper(strings.TrimSpace(req.Sequence))

	if !isValidRNASequence(seq) {
		if h.redis != nil {
			_ = h.redis.SetInvalid(seq)
		}
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid RNA sequence. Only A, U, G, C are allowed.",
		})
		return
	}

	if len(seq) < 4 {
		if h.redis != nil {
			_ = h.redis.SetInvalid(seq)
		}
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "RNA sequence must be at least 4 nucleotides long.",
		})
		return
	}

	if h.redis != nil {
		cached, err := h.redis.Get(seq)
		if err != nil && err.Error() == "invalid_cached" {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "Invalid RNA sequence (cached)",
			})
			return
		}
		if err != nil && err.Error() == "null_cached" {
			response := &models.RNAResponse{
				Sequence:     seq,
				Structure:    strings.Repeat(".", len(seq)),
				MinFreeEnergy: 0,
				BasePairProbs: []models.BasePairProb{},
				FromCache:    true,
			}
			c.JSON(http.StatusOK, response)
			return
		}
		if err == nil && cached != nil {
			if cached.BloomFiltered {
				response := &models.RNAResponse{
					Sequence:      seq,
					Structure:     strings.Repeat(".", len(seq)),
					MinFreeEnergy: 0,
					BasePairProbs: []models.BasePairProb{},
					FromCache:     true,
					BloomFiltered: true,
				}
				c.JSON(http.StatusOK, response)
				return
			}
			cached.FromCache = true
			cached.BloomFiltered = false
			c.JSON(http.StatusOK, cached)
			return
		}
	}

	var constraint *models.FamilyConstraint
	if h.postgres != nil {
		var err error
		constraint, err = h.postgres.FindFamilyConstraint(seq)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":   "Failed to query family constraints",
				"details": err.Error(),
			})
			return
		}
	}

	response := zuker.Predict(seq, constraint)

	if h.redis != nil {
		if response.Structure == strings.Repeat(".", len(seq)) {
			_ = h.redis.SetNull(seq)
		} else {
			_ = h.redis.Set(seq, response)
		}
	}

	c.JSON(http.StatusOK, response)
}

func (h *Handler) GetFamilies(c *gin.Context) {
	if h.postgres == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "PostgreSQL connection not available",
		})
		return
	}

	families, err := h.postgres.GetAllFamilies()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to retrieve families",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"families": families,
	})
}

func (h *Handler) Health(c *gin.Context) {
	status := gin.H{
		"status": "ok",
		"services": gin.H{
			"redis":    h.redis != nil,
			"postgres": h.postgres != nil,
		},
	}

	c.JSON(http.StatusOK, status)
}

func (h *Handler) ClearCache(c *gin.Context) {
	if h.redis == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "Redis connection not available",
		})
		return
	}

	err := h.redis.Clear()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to clear cache",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Cache cleared successfully",
	})
}

func isValidRNASequence(seq string) bool {
	if seq == "" {
		return false
	}
	match, _ := regexp.MatchString("^[AUGC]+$", seq)
	return match
}

func (h *Handler) PredictRNAWithSHAPE(c *gin.Context) {
	var req models.SHAPERequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request body",
			"details": err.Error(),
		})
		return
	}

	seq := strings.ToUpper(strings.TrimSpace(req.Sequence))

	if !isValidRNASequence(seq) {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid RNA sequence. Only A, U, G, C are allowed.",
		})
		return
	}

	if len(seq) < 4 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "RNA sequence must be at least 4 nucleotides long.",
		})
		return
	}

	if len(req.SHAPEData) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "SHAPE data is required. Please provide reactivity values for at least some positions.",
		})
		return
	}

	for _, sd := range req.SHAPEData {
		if sd.Position < 0 || sd.Position >= len(seq) {
			c.JSON(http.StatusBadRequest, gin.H{
				"error":   fmt.Sprintf("Invalid SHAPE position %d. Must be between 0 and %d.", sd.Position, len(seq)-1),
				"details": nil,
			})
			return
		}
		if sd.Reactivity < 0 {
			c.JSON(http.StatusBadRequest, gin.H{
				"error":   "SHAPE reactivity must be non-negative.",
				"details": nil,
			})
			return
		}
	}

	var constraint *models.FamilyConstraint
	if h.postgres != nil {
		var err error
		constraint, err = h.postgres.FindFamilyConstraint(seq)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":   "Failed to query family constraints",
				"details": err.Error(),
			})
			return
		}
	}

	response := zuker.PredictWithSHAPE(seq, req.SHAPEData, req.SHAPESlope, req.SHAPEIntercept, constraint)

	if h.redis != nil {
		_ = h.redis.Set(seq+":shape", response)
	}

	c.JSON(http.StatusOK, response)
}

func (h *Handler) SampleSuboptimalStructures(c *gin.Context) {
	var req models.SamplingRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request body",
			"details": err.Error(),
		})
		return
	}

	seq := strings.ToUpper(strings.TrimSpace(req.Sequence))

	if !isValidRNASequence(seq) {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid RNA sequence. Only A, U, G, C are allowed.",
		})
		return
	}

	if len(seq) < 4 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "RNA sequence must be at least 4 nucleotides long.",
		})
		return
	}

	numSamples := req.NumSamples
	if numSamples <= 0 {
		numSamples = 100
	}
	if numSamples > 10000 {
		numSamples = 10000
	}

	response := zuker.SampleStructures(seq, numSamples, req.Temperature, req.MaxEnergyDiff)

	c.JSON(http.StatusOK, response)
}

func (h *Handler) PredictCommonStructure(c *gin.Context) {
	var req models.MSARequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request body",
			"details": err.Error(),
		})
		return
	}

	if len(req.Sequences) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "At least one sequence is required.",
		})
		return
	}

	if len(req.Sequences) > 100 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Maximum 100 sequences are allowed per request.",
		})
		return
	}

	processedSeqs := make([]string, 0, len(req.Sequences))
	for _, s := range req.Sequences {
		seq := strings.ToUpper(strings.TrimSpace(s))
		cleanSeq := strings.ReplaceAll(seq, "-", "")
		if cleanSeq != "" {
			if !isValidRNASequence(cleanSeq) {
				c.JSON(http.StatusBadRequest, gin.H{
					"error":   fmt.Sprintf("Invalid RNA sequence: %s. Only A, U, G, C are allowed.", s),
					"details": nil,
				})
				return
			}
			processedSeqs = append(processedSeqs, seq)
		}
	}

	if len(processedSeqs) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "No valid sequences provided.",
		})
		return
	}

	cutoff := req.ConsensusCutoff
	if cutoff <= 0 || cutoff > 1 {
		cutoff = 0.6
	}

	response := msa.PredictCommonStructure(processedSeqs, cutoff, req.UseCovariation)

	c.JSON(http.StatusOK, response)
}

func (h *Handler) GetCacheStats(c *gin.Context) {
	if h.redis == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "Redis connection not available",
		})
		return
	}

	fillRatio, setBits, err := h.redis.GetBloomFilterStats()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to get bloom filter stats",
			"details": err.Error(),
		})
		return
	}

	falsePositiveRate := math.Pow(
		1-math.Exp(-float64(cache.BloomFilterHashes)*float64(setBits)/float64(cache.BloomFilterBits)),
		float64(cache.BloomFilterHashes),
	)

	c.JSON(http.StatusOK, gin.H{
		"bloom_filter": gin.H{
			"size_bits":              cache.BloomFilterBits,
			"size_bytes":             cache.BloomFilterBits / 8,
			"num_hashes":             cache.BloomFilterHashes,
			"set_bits":               setBits,
			"fill_ratio":             math.Round(fillRatio*10000) / 10000,
			"estimated_false_positive": math.Round(falsePositiveRate*1000000) / 1000000,
		},
		"null_cache_ttl_seconds":    int(cache.NullCacheTTL.Seconds()),
		"invalid_cache_ttl_seconds": int(cache.InvalidCacheTTL.Seconds()),
	})
}

func SetupRoutes(r *gin.Engine, handler *Handler) {
	api := r.Group("/api/v1")
	{
		api.POST("/predict", handler.PredictRNA)
		api.POST("/predict/shape", handler.PredictRNAWithSHAPE)
		api.POST("/sample", handler.SampleSuboptimalStructures)
		api.POST("/msa/common", handler.PredictCommonStructure)
		api.GET("/families", handler.GetFamilies)
		api.GET("/cache/stats", handler.GetCacheStats)
		api.DELETE("/cache", handler.ClearCache)
	}

	r.GET("/health", handler.Health)
}
