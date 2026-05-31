CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O2 -Iinclude
LDFLAGS ?=

BN_WITH_HDF5 ?= 0

ifeq ($(BN_WITH_HDF5), 1)
    CXXFLAGS += -DBN_WITH_HDF5
    LDFLAGS += -lhdf5_cpp -lhdf5
endif

SRCS = src/boolean_network.cpp src/main.cpp
OBJS = $(SRCS:.cpp=.o)
TARGET = bn_analyzer

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(OBJS) -o $(TARGET) $(LDFLAGS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)

test_simple: $(TARGET)
	./$(TARGET) -s 100 -b 500 examples/simple_network.txt

test_cycle: $(TARGET)
	./$(TARGET) -s 200 -b 1000 examples/cycle_network.txt

test_cellcycle: $(TARGET)
	./$(TARGET) -s 500 -b 2000 -p 1 -l 5000 -o landscape.txt examples/cell_cycle.txt

.PHONY: all clean test_simple test_cycle test_cellcycle
