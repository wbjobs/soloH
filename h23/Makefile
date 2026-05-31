BINARY_NAME=randomness-tester

.PHONY: all build test clean run fmt

all: build

build:
	go build -o $(BINARY_NAME).exe ./cmd/randomness-tester

test:
	go test -v ./internal/tests ./internal/utils ./internal/config ./internal/report ./internal/rng

test-coverage:
	go test -cover ./...

fmt:
	go fmt ./...

clean:
	rm -f $(BINARY_NAME).exe
	rm -f *.json *.txt

run: build
	./$(BINARY_NAME).exe -list-tests

install: build
	copy $(BINARY_NAME).exe "$(USERPROFILE)\go\bin\"
