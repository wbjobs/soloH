package main

import (
	"log"

	"github.com/gin-gonic/gin"

	"rna-secondary-structure/api"
	"rna-secondary-structure/cache"
	"rna-secondary-structure/config"
	"rna-secondary-structure/db"
)

func main() {
	if err := config.Load(); err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	r := gin.Default()

	r.Use(func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	})

	var redisClient *cache.RedisClient
	var postgresClient *db.PostgresClient

	redisClient, err := cache.NewRedisClient()
	if err != nil {
		log.Printf("Warning: Redis connection failed: %v", err)
		log.Println("Continuing without Redis cache...")
	} else {
		log.Println("Redis connected successfully")
		defer redisClient.Close()
	}

	postgresClient, err = db.NewPostgresClient()
	if err != nil {
		log.Printf("Warning: PostgreSQL connection failed: %v", err)
		log.Println("Continuing without family constraints...")
	} else {
		log.Println("PostgreSQL connected successfully")
		defer postgresClient.Close()
	}

	handler := api.NewHandler(redisClient, postgresClient)
	api.SetupRoutes(r, handler)

	log.Printf("Server starting on port %s...", config.AppConfig.Port)
	log.Printf("API Endpoints:")
	log.Printf("  POST /api/v1/predict - Predict RNA secondary structure")
	log.Printf("  GET  /api/v1/families - List RNA families")
	log.Printf("  DELETE /api/v1/cache - Clear Redis cache")
	log.Printf("  GET  /health - Health check")

	if err := r.Run(":" + config.AppConfig.Port); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
