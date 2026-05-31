package mutator

import (
	"bytes"
	"testing"

	"tcp-fuzzer/internal/protocol"
)

func TestNewMutator(t *testing.T) {
	proto, err := protocol.LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	m := NewMutator(proto, 12345)
	if m == nil {
		t.Fatal("NewMutator returned nil")
	}
}

func TestBitFlipMutation(t *testing.T) {
	proto, err := protocol.LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	m := NewMutator(proto, 12345)

	gen := protocol.NewMessageGenerator(proto, 12345)
	original, err := gen.Generate()
	if err != nil {
		t.Fatalf("Failed to generate message: %v", err)
	}

	result, err := m.mutateBitFlip(original, 1)
	if err != nil {
		t.Fatalf("Bit flip mutation failed: %v", err)
	}

	if len(result.Data) != len(original) {
		t.Errorf("Bit flip should not change length: got %d, want %d", len(result.Data), len(original))
	}

	if bytes.Equal(result.Data, original) {
		t.Error("Bit flip should have changed at least one bit")
	}

	if result.Strategy != StrategyBitFlip {
		t.Errorf("Expected strategy %s, got %s", StrategyBitFlip, result.Strategy)
	}
}

func TestArithmeticMutation(t *testing.T) {
	proto, err := protocol.LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	m := NewMutator(proto, 12345)

	gen := protocol.NewMessageGenerator(proto, 12345)
	original, err := gen.Generate()
	if err != nil {
		t.Fatalf("Failed to generate message: %v", err)
	}

	result, err := m.mutateArithmetic(original)
	if err != nil {
		t.Fatalf("Arithmetic mutation failed: %v", err)
	}

	if result.Strategy != StrategyArithmetic {
		t.Errorf("Expected strategy %s, got %s", StrategyArithmetic, result.Strategy)
	}
}

func TestBoundaryMutation(t *testing.T) {
	proto, err := protocol.LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	m := NewMutator(proto, 12345)

	gen := protocol.NewMessageGenerator(proto, 12345)
	original, err := gen.Generate()
	if err != nil {
		t.Fatalf("Failed to generate message: %v", err)
	}

	result, err := m.mutateBoundary(original)
	if err != nil {
		t.Fatalf("Boundary mutation failed: %v", err)
	}

	if result.Strategy != StrategyBoundary {
		t.Errorf("Expected strategy %s, got %s", StrategyBoundary, result.Strategy)
	}
}

func TestBlockInsertMutation(t *testing.T) {
	proto, err := protocol.LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	m := NewMutator(proto, 12345)

	gen := protocol.NewMessageGenerator(proto, 12345)
	original, err := gen.Generate()
	if err != nil {
		t.Fatalf("Failed to generate message: %v", err)
	}

	result, err := m.mutateBlockInsert(original)
	if err != nil {
		t.Fatalf("Block insert mutation failed: %v", err)
	}

	if len(result.Data) <= len(original) {
		t.Errorf("Block insert should increase length: got %d, want > %d", len(result.Data), len(original))
	}

	if result.Strategy != StrategyBlockInsert {
		t.Errorf("Expected strategy %s, got %s", StrategyBlockInsert, result.Strategy)
	}
}

func TestBlockDeleteMutation(t *testing.T) {
	proto, err := protocol.LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	m := NewMutator(proto, 12345)

	gen := protocol.NewMessageGenerator(proto, 12345)
	original, err := gen.Generate()
	if err != nil {
		t.Fatalf("Failed to generate message: %v", err)
	}

	result, err := m.mutateBlockDelete(original)
	if err != nil {
		t.Fatalf("Block delete mutation failed: %v", err)
	}

	if len(result.Data) >= len(original) {
		t.Errorf("Block delete should decrease length: got %d, want < %d", len(result.Data), len(original))
	}

	if result.Strategy != StrategyBlockDelete {
		t.Errorf("Expected strategy %s, got %s", StrategyBlockDelete, result.Strategy)
	}
}

func TestBlockDuplicateMutation(t *testing.T) {
	proto, err := protocol.LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	m := NewMutator(proto, 12345)

	gen := protocol.NewMessageGenerator(proto, 12345)
	original, err := gen.Generate()
	if err != nil {
		t.Fatalf("Failed to generate message: %v", err)
	}

	result, err := m.mutateBlockDuplicate(original)
	if err != nil {
		t.Fatalf("Block duplicate mutation failed: %v", err)
	}

	if len(result.Data) <= len(original) {
		t.Errorf("Block duplicate should increase length: got %d, want > %d", len(result.Data), len(original))
	}

	if result.Strategy != StrategyBlockDuplicate {
		t.Errorf("Expected strategy %s, got %s", StrategyBlockDuplicate, result.Strategy)
	}
}

func TestMutate(t *testing.T) {
	proto, err := protocol.LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	m := NewMutator(proto, 12345)

	gen := protocol.NewMessageGenerator(proto, 12345)
	original, err := gen.Generate()
	if err != nil {
		t.Fatalf("Failed to generate message: %v", err)
	}

	for i := 0; i < 100; i++ {
		result, err := m.Mutate(original)
		if err != nil {
			t.Fatalf("Mutation %d failed: %v", i, err)
		}

		if result.Strategy == "" {
			t.Errorf("Mutation %d: strategy is empty", i)
		}

		if len(result.Data) < proto.MinMsgSize {
			t.Errorf("Mutation %d: result too short: %d < %d", i, len(result.Data), proto.MinMsgSize)
		}
		if len(result.Data) > proto.MaxMsgSize {
			t.Errorf("Mutation %d: result too long: %d > %d", i, len(result.Data), proto.MaxMsgSize)
		}
	}
}

func TestMutateMultiple(t *testing.T) {
	proto, err := protocol.LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	m := NewMutator(proto, 12345)

	gen := protocol.NewMessageGenerator(proto, 12345)
	original, err := gen.Generate()
	if err != nil {
		t.Fatalf("Failed to generate message: %v", err)
	}

	count := 10
	results, err := m.MutateMultiple(original, count)
	if err != nil {
		t.Fatalf("MutateMultiple failed: %v", err)
	}

	if len(results) != count {
		t.Errorf("Expected %d results, got %d", count, len(results))
	}

	for i, r := range results {
		if r == nil {
			t.Errorf("Result %d is nil", i)
		}
	}
}

func TestGetBoundaryValues(t *testing.T) {
	proto, err := protocol.LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	m := NewMutator(proto, 12345)

	tests := []struct {
		name      string
		fieldType protocol.FieldType
		min       interface{}
		max       interface{}
	}{
		{
			name:      "uint8 field",
			fieldType: protocol.FieldTypeUInt8,
			min:       float64(0),
			max:       float64(100),
		},
		{
			name:      "uint16 field",
			fieldType: protocol.FieldTypeUInt16,
			min:       float64(0),
			max:       float64(1000),
		},
		{
			name:      "int32 field",
			fieldType: protocol.FieldTypeInt32,
			min:       float64(-1000),
			max:       float64(1000),
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			f := &protocol.Field{
				Name: "test",
				Type: tt.fieldType,
				Min:  tt.min,
				Max:  tt.max,
			}
			values := m.getBoundaryValues(f)
			if len(values) == 0 {
				t.Error("Expected non-empty boundary values")
			}
		})
	}
}

func TestMinFunction(t *testing.T) {
	tests := []struct {
		name string
		a    int
		b    int
		rest []int
		want int
	}{
		{"simple", 1, 2, nil, 1},
		{"with rest", 5, 3, []int{4, 2, 6}, 2},
		{"negative", -1, -5, []int{-3}, -5},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := min(tt.a, tt.b, tt.rest...)
			if got != tt.want {
				t.Errorf("min() = %d, want %d", got, tt.want)
			}
		})
	}
}
