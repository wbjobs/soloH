CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Wpedantic
LDFLAGS  ?= 
INCLUDES = -I./include

SRCDIR   = src
OBJDIR   = build
BINDIR   = $(OBJDIR)

SOURCES  = $(wildcard $(SRCDIR)/*.cpp)
OBJECTS  = $(SOURCES:$(SRCDIR)/%.cpp=$(OBJDIR)/%.o)
TARGET   = $(BINDIR)/bb84_simulator

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(OBJECTS) | $(BINDIR)
	@echo "Linking $@..."
	@$(CXX) $(CXXFLAGS) $(OBJECTS) -o $@ $(LDFLAGS)
	@echo "Build complete! Executable: $@"

$(OBJDIR)/%.o: $(SRCDIR)/%.cpp | $(OBJDIR)
	@echo "Compiling $<..."
	@$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJDIR):
	@mkdir -p $(OBJDIR)

$(BINDIR):
	@mkdir -p $(BINDIR)

run: $(TARGET)
	@echo "Running BB84 simulator with default parameters..."
	@./$(TARGET)

clean:
	@echo "Cleaning build files..."
	@rm -rf $(OBJDIR)
	@echo "Clean complete."
