package protocol

import (
	"bytes"
	"encoding/binary"
	"testing"
)

func TestLoadProtocolDescription(t *testing.T) {
	proto, err := LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	if proto.Name != "ModbusLike" {
		t.Errorf("Expected name 'ModbusLike', got '%s'", proto.Name)
	}
	if proto.Version != "1.0" {
		t.Errorf("Expected version '1.0', got '%s'", proto.Version)
	}
	if proto.Endian != EndianBig {
		t.Errorf("Expected endian 'big', got '%s'", proto.Endian)
	}
	if len(proto.Header) != 4 {
		t.Errorf("Expected 4 header fields, got %d", len(proto.Header))
	}
	if len(proto.Body) != 3 {
		t.Errorf("Expected 3 body fields, got %d", len(proto.Body))
	}
	if len(proto.Tail) != 1 {
		t.Errorf("Expected 1 tail field, got %d", len(proto.Tail))
	}
}

func TestMessageGeneration(t *testing.T) {
	proto, err := LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	gen := NewMessageGenerator(proto, 12345)
	msg, err := gen.Generate()
	if err != nil {
		t.Fatalf("Failed to generate message: %v", err)
	}

	if len(msg) < proto.MinMsgSize {
		t.Errorf("Message too short: %d < %d", len(msg), proto.MinMsgSize)
	}
	if len(msg) > proto.MaxMsgSize {
		t.Errorf("Message too long: %d > %d", len(msg), proto.MaxMsgSize)
	}

	protocolID := binary.BigEndian.Uint16(msg[2:4])
	if protocolID != 0 {
		t.Errorf("Expected protocol_id 0, got %d", protocolID)
	}
}

func TestChecksumCalculation(t *testing.T) {
	data := []byte{0x01, 0x03, 0x00, 0x01, 0x00, 0x01}
	expectedCRC := []byte{0xD5, 0xCA}

	crc := calcModbusRTUCRC(data)
	if !bytes.Equal(crc, expectedCRC) {
		t.Errorf("Expected CRC 0x%x, got 0x%x", expectedCRC, crc)
	}
}

func TestChecksumRecalculation(t *testing.T) {
	proto, err := LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	gen := NewMessageGenerator(proto, 12345)
	msg, err := gen.Generate()
	if err != nil {
		t.Fatalf("Failed to generate message: %v", err)
	}

	msg[0] ^= 0xFF

	recalculated, err := RecalculateChecksums(proto, msg)
	if err != nil {
		t.Fatalf("Failed to recalculate checksums: %v", err)
	}

	if bytes.Equal(msg[len(msg)-2:], recalculated[len(recalculated)-2:]) {
		t.Error("Checksum should have changed after mutation")
	}
}

func TestFieldValidation(t *testing.T) {
	tests := []struct {
		name    string
		field   Field
		wantErr bool
	}{
		{
			name: "valid uint8 field",
			field: Field{
				Name: "test",
				Type: FieldTypeUInt8,
			},
			wantErr: false,
		},
		{
			name: "missing name",
			field: Field{
				Type: FieldTypeUInt8,
			},
			wantErr: true,
		},
		{
			name: "missing type",
			field: Field{
				Name: "test",
			},
			wantErr: true,
		},
		{
			name: "bytes without length",
			field: Field{
				Name: "test",
				Type: FieldTypeBytes,
			},
			wantErr: true,
		},
		{
			name: "variable bytes without length",
			field: Field{
				Name:       "test",
				Type:       FieldTypeBytes,
				IsVariable: true,
			},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateField(&tt.field, EndianBig)
			if (err != nil) != tt.wantErr {
				t.Errorf("validateField() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestGetMinMax(t *testing.T) {
	tests := []struct {
		name      string
		fieldType FieldType
		customMin interface{}
		customMax interface{}
		wantMin   float64
		wantMax   float64
	}{
		{
			name:      "uint8 default",
			fieldType: FieldTypeUInt8,
			wantMin:   0,
			wantMax:   255,
		},
		{
			name:      "int8 default",
			fieldType: FieldTypeInt8,
			wantMin:   -128,
			wantMax:   127,
		},
		{
			name:      "uint16 with custom range",
			fieldType: FieldTypeUInt16,
			customMin: float64(10),
			customMax: float64(100),
			wantMin:   10,
			wantMax:   100,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			f := &Field{
				Name: "test",
				Type: tt.fieldType,
				Min:  tt.customMin,
				Max:  tt.customMax,
			}
			min, max, _ := f.GetMinMax()
			if min != tt.wantMin {
				t.Errorf("Min = %v, want %v", min, tt.wantMin)
			}
			if max != tt.wantMax {
				t.Errorf("Max = %v, want %v", max, tt.wantMax)
			}
		})
	}
}

func TestParseMessage(t *testing.T) {
	proto, err := LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	gen := NewMessageGenerator(proto, 12345)
	msg, err := gen.Generate()
	if err != nil {
		t.Fatalf("Failed to generate message: %v", err)
	}

	parsed, err := ParseMessage(proto, msg)
	if err != nil {
		t.Fatalf("Failed to parse message: %v", err)
	}

	if len(parsed.Header) != len(proto.Header) {
		t.Errorf("Expected %d header fields, got %d", len(proto.Header), len(parsed.Header))
	}
	if len(parsed.Body) != len(proto.Body) {
		t.Errorf("Expected %d body fields, got %d", len(proto.Body), len(parsed.Body))
	}
	if len(parsed.Tail) != len(proto.Tail) {
		t.Errorf("Expected %d tail fields, got %d", len(proto.Tail), len(parsed.Tail))
	}

	if parsed.Header[1].Name != "protocol_id" {
		t.Errorf("Expected second header field to be 'protocol_id', got '%s'", parsed.Header[1].Name)
	}
}

func TestAllFields(t *testing.T) {
	proto, err := LoadProtocolDescription("../../examples/modbus_like.json")
	if err != nil {
		t.Fatalf("Failed to load protocol: %v", err)
	}

	fields := proto.AllFields()
	expectedCount := len(proto.Header) + len(proto.Body) + len(proto.Tail)
	if len(fields) != expectedCount {
		t.Errorf("Expected %d total fields, got %d", expectedCount, len(fields))
	}
}

func TestXORChecksum(t *testing.T) {
	data := []byte{0x01, 0x02, 0x03, 0x04}
	expected := byte(0x04)

	result := calcXOR(data)
	if result[0] != expected {
		t.Errorf("Expected XOR 0x%x, got 0x%x", expected, result[0])
	}
}

func TestSum8Checksum(t *testing.T) {
	data := []byte{0x01, 0x02, 0x03, 0x04}
	expected := byte(0x0A)

	result := calcSum8(data)
	if result[0] != expected {
		t.Errorf("Expected Sum8 0x%x, got 0x%x", expected, result[0])
	}
}

func TestCRC16Checksum(t *testing.T) {
	data := []byte{0x02, 0x07}
	expected := []byte{0x41, 0x12}

	result := calcCRC16(data)
	if !bytes.Equal(result, expected) {
		t.Errorf("Expected CRC16 0x%x, got 0x%x", expected, result)
	}
}

func TestEncodeValue(t *testing.T) {
	f := &Field{
		Name:       "test",
		Type:       FieldTypeUInt16,
		ByteLength: 2,
		Endian:     EndianBig,
	}

	result, err := encodeValue(f, uint16(0x1234))
	if err != nil {
		t.Fatalf("encodeValue failed: %v", err)
	}

	expected := []byte{0x12, 0x34}
	if !bytes.Equal(result, expected) {
		t.Errorf("Expected 0x%x, got 0x%x", expected, result)
	}
}
