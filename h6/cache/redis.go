package cache

import (
	"context"
	"encoding/json"
	"fmt"
	"hash/fnv"
	"math"
	"strings"
	"time"

	"github.com/go-redis/redis/v8"

	"rna-secondary-structure/config"
	"rna-secondary-structure/models"
)

var ctx = context.Background()

const (
	NullValueMarker    = "__NULL_MARKER__"
	InvalidValueMarker = "__INVALID_MARKER__"
	BloomFilterKey     = "rna:bloom_filter"
	BloomFilterBits    = 1 << 24
	BloomFilterHashes  = 7
	NullCacheTTL       = 5 * time.Minute
	InvalidCacheTTL    = 1 * time.Hour
)

type BloomFilter struct {
	m uint64
	k uint64
}

func NewBloomFilter(m uint64, k uint64) *BloomFilter {
	return &BloomFilter{m: m, k: k}
}

func (bf *BloomFilter) getHash(data []byte, seed uint64) uint64 {
	h := fnv.New64a()
	h.Write([]byte{byte(seed), byte(seed >> 8), byte(seed >> 16), byte(seed >> 24)})
	h.Write(data)
	return h.Sum64()
}

func (bf *BloomFilter) GetBits(data []byte) []uint64 {
	bits := make([]uint64, bf.k)
	for i := uint64(0); i < bf.k; i++ {
		hash := bf.getHash(data, i)
		bits[i] = hash % bf.m
	}
	return bits
}

type RedisClient struct {
	client      *redis.Client
	ttl         time.Duration
	nullTTL     time.Duration
	invalidTTL  time.Duration
	bloomFilter *BloomFilter
}

func NewRedisClient() (*RedisClient, error) {
	cfg := config.AppConfig

	client := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})

	_, err := client.Ping(ctx).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	bf := NewBloomFilter(BloomFilterBits, BloomFilterHashes)

	rc := &RedisClient{
		client:      client,
		ttl:         time.Duration(cfg.RedisTTL) * time.Second,
		nullTTL:     NullCacheTTL,
		invalidTTL:  InvalidCacheTTL,
		bloomFilter: bf,
	}

	err = rc.initBloomFilter()
	if err != nil {
		return nil, fmt.Errorf("failed to init bloom filter: %w", err)
	}

	return rc, nil
}

func (r *RedisClient) initBloomFilter() error {
	exists, err := r.client.Exists(ctx, BloomFilterKey).Result()
	if err != nil {
		return err
	}

	if exists == 0 {
		sizeBytes := BloomFilterBits / 8
		empty := make([]byte, sizeBytes)
		err = r.client.Set(ctx, BloomFilterKey, empty, 0).Err()
		if err != nil {
			return err
		}
	}

	return nil
}

func (r *RedisClient) addToBloomFilter(sequence string) error {
	bits := r.bloomFilter.GetBits([]byte(sequence))
	pipe := r.client.Pipeline()

	for _, bit := range bits {
		byteIndex := bit / 8
		bitOffset := bit % 8
		pipe.SetBit(ctx, BloomFilterKey, int64(byteIndex*8+bitOffset), 1)
	}

	_, err := pipe.Exec(ctx)
	return err
}

func (r *RedisClient) mightExist(sequence string) (bool, error) {
	bits := r.bloomFilter.GetBits([]byte(sequence))

	for _, bit := range bits {
		byteIndex := bit / 8
		bitOffset := bit % 8
		val, err := r.client.GetBit(ctx, BloomFilterKey, int64(byteIndex*8+bitOffset)).Result()
		if err != nil {
			return true, err
		}
		if val == 0 {
			return false, nil
		}
	}

	return true, nil
}

func (r *RedisClient) Get(sequence string) (*models.RNAResponse, error) {
	exists, err := r.mightExist(sequence)
	if err == nil && !exists {
		bloomResp := &models.RNAResponse{
			Sequence:      sequence,
			Structure:     strings.Repeat(".", len(sequence)),
			MinFreeEnergy: 0,
			FromCache:     true,
			BloomFiltered: true,
		}
		return bloomResp, nil
	}

	key := r.getKey(sequence)

	data, err := r.client.Get(ctx, key).Result()
	if err == redis.Nil {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get from Redis: %w", err)
	}

	if data == NullValueMarker {
		return nil, fmt.Errorf("null_cached")
	}

	if data == InvalidValueMarker {
		return nil, fmt.Errorf("invalid_cached")
	}

	var response models.RNAResponse
	err = json.Unmarshal([]byte(data), &response)
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal Redis data: %w", err)
	}

	response.FromCache = true
	response.BloomFiltered = false
	return &response, nil
}

func (r *RedisClient) Set(sequence string, response *models.RNAResponse) error {
	key := r.getKey(sequence)

	err := r.addToBloomFilter(sequence)
	if err != nil {
		return fmt.Errorf("failed to add to bloom filter: %w", err)
	}

	response.FromCache = false
	data, err := json.Marshal(response)
	if err != nil {
		return fmt.Errorf("failed to marshal response: %w", err)
	}

	err = r.client.Set(ctx, key, data, r.ttl).Err()
	if err != nil {
		return fmt.Errorf("failed to set to Redis: %w", err)
	}

	return nil
}

func (r *RedisClient) SetNull(sequence string) error {
	key := r.getKey(sequence)

	err := r.addToBloomFilter(sequence)
	if err != nil {
		return fmt.Errorf("failed to add to bloom filter: %w", err)
	}

	err = r.client.Set(ctx, key, NullValueMarker, r.nullTTL).Err()
	if err != nil {
		return fmt.Errorf("failed to set null to Redis: %w", err)
	}

	return nil
}

func (r *RedisClient) SetInvalid(sequence string) error {
	key := r.getKey(sequence)

	err := r.addToBloomFilter(sequence)
	if err != nil {
		return fmt.Errorf("failed to add to bloom filter: %w", err)
	}

	err = r.client.Set(ctx, key, InvalidValueMarker, r.invalidTTL).Err()
	if err != nil {
		return fmt.Errorf("failed to set invalid to Redis: %w", err)
	}

	return nil
}

func (r *RedisClient) Delete(sequence string) error {
	key := r.getKey(sequence)
	return r.client.Del(ctx, key).Err()
}

func (r *RedisClient) Clear() error {
	pipe := r.client.Pipeline()
	pipe.FlushDB(ctx)

	sizeBytes := BloomFilterBits / 8
	empty := make([]byte, sizeBytes)
	pipe.Set(ctx, BloomFilterKey, empty, 0)

	_, err := pipe.Exec(ctx)
	return err
}

func (r *RedisClient) GetBloomFilterStats() (float64, int64, error) {
	var count int64
	var zeroCount int64

	for i := int64(0); i < int64(BloomFilterBits); i += 8 {
		val, err := r.client.GetBit(ctx, BloomFilterKey, i).Result()
		if err != nil {
			return 0, 0, err
		}
		if val == 1 {
			count++
		} else {
			zeroCount++
		}
	}

	fillRatio := float64(count) / float64(BloomFilterBits)
	return fillRatio, count, nil
}

func (r *RedisClient) Close() error {
	return r.client.Close()
}

func (r *RedisClient) getKey(sequence string) string {
	return fmt.Sprintf("rna:%s", sequence)
}
