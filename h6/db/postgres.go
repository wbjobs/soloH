package db

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"regexp"

	_ "github.com/lib/pq"

	"rna-secondary-structure/config"
	"rna-secondary-structure/models"
)

type PostgresClient struct {
	db *sql.DB
}

func NewPostgresClient() (*PostgresClient, error) {
	cfg := config.AppConfig

	connStr := fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
		cfg.PostgresHost, cfg.PostgresPort, cfg.PostgresUser,
		cfg.PostgresPassword, cfg.PostgresDB, cfg.PostgresSSLMode,
	)

	db, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to open PostgreSQL connection: %w", err)
	}

	err = db.Ping()
	if err != nil {
		return nil, fmt.Errorf("failed to connect to PostgreSQL: %w", err)
	}

	client := &PostgresClient{db: db}
	err = client.initSchema()
	if err != nil {
		return nil, fmt.Errorf("failed to initialize schema: %w", err)
	}

	err = client.seedFamilies()
	if err != nil {
		return nil, fmt.Errorf("failed to seed families: %w", err)
	}

	return client, nil
}

func (p *PostgresClient) initSchema() error {
	createTable := `
	CREATE TABLE IF NOT EXISTS rna_families (
		id SERIAL PRIMARY KEY,
		name VARCHAR(100) NOT NULL UNIQUE,
		pattern VARCHAR(500) NOT NULL,
		must_pair JSONB,
		must_unpair JSONB,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	)`

	_, err := p.db.Exec(createTable)
	return err
}

func (p *PostgresClient) seedFamilies() error {
	var count int
	err := p.db.QueryRow("SELECT COUNT(*) FROM rna_families").Scan(&count)
	if err != nil {
		return err
	}

	if count > 0 {
		return nil
	}

	families := []struct {
		name       string
		pattern    string
		mustPair   [][2]int
		mustUnpair []int
	}{
		{
			name:    "tRNA-like",
			pattern: "AUGC[AUGC]{30,60}AUGC",
			mustPair: [][2]int{{0, 3}, {4, 7}},
			mustUnpair: []int{1, 2, 5, 6},
		},
		{
			name:    "Stem-loop",
			pattern: "[GC]{4,}[AUGC]{3,}[GC]{4,}",
			mustPair: [][2]int{},
			mustUnpair: []int{},
		},
		{
			name:    "miRNA",
			pattern: "[AUGC]{21,23}",
			mustPair: [][2]int{},
			mustUnpair: []int{},
		},
	}

	for _, f := range families {
		mustPairJSON, _ := json.Marshal(f.mustPair)
		mustUnpairJSON, _ := json.Marshal(f.mustUnpair)

		_, err := p.db.Exec(
			`INSERT INTO rna_families (name, pattern, must_pair, must_unpair)
			 VALUES ($1, $2, $3, $4)
			 ON CONFLICT (name) DO NOTHING`,
			f.name, f.pattern, mustPairJSON, mustUnpairJSON,
		)
		if err != nil {
			return err
		}
	}

	return nil
}

func (p *PostgresClient) FindFamilyConstraint(sequence string) (*models.FamilyConstraint, error) {
	rows, err := p.db.Query(`
		SELECT name, pattern, must_pair, must_unpair
		FROM rna_families
	`)
	if err != nil {
		return nil, fmt.Errorf("failed to query families: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var name, pattern string
		var mustPairJSON, mustUnpairJSON sql.NullString

		err := rows.Scan(&name, &pattern, &mustPairJSON, &mustUnpairJSON)
		if err != nil {
			return nil, fmt.Errorf("failed to scan row: %w", err)
		}

		matched, _ := regexp.MatchString(pattern, sequence)
		if matched {
			var mustPair [][2]int
			var mustUnpair []int

			if mustPairJSON.Valid {
				json.Unmarshal([]byte(mustPairJSON.String), &mustPair)
			}
			if mustUnpairJSON.Valid {
				json.Unmarshal([]byte(mustUnpairJSON.String), &mustUnpair)
			}

			return &models.FamilyConstraint{
				FamilyName: name,
				MustPair:   mustPair,
				MustUnpair: mustUnpair,
			}, nil
		}
	}

	return nil, nil
}

func (p *PostgresClient) GetAllFamilies() ([]models.RNAFamily, error) {
	rows, err := p.db.Query(`
		SELECT id, name, pattern, must_pair, must_unpair, created_at
		FROM rna_families
		ORDER BY name
	`)
	if err != nil {
		return nil, fmt.Errorf("failed to query families: %w", err)
	}
	defer rows.Close()

	var families []models.RNAFamily
	for rows.Next() {
		var f models.RNAFamily
		var createdAt sql.NullTime

		err := rows.Scan(&f.ID, &f.Name, &f.Pattern, &f.MustPairJSON, &f.MustUnpairJSON, &createdAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan row: %w", err)
		}

		if createdAt.Valid {
			f.CreatedAt = createdAt.Time.Format("2006-01-02 15:04:05")
		}

		families = append(families, f)
	}

	return families, nil
}

func (p *PostgresClient) Close() error {
	return p.db.Close()
}
