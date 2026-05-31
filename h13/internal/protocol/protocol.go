package protocol

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math"
	"os"
)

type FieldType string

const (
	FieldTypeUInt8   FieldType = "uint8"
	FieldTypeUInt16  FieldType = "uint16"
	FieldTypeUInt32  FieldType = "uint32"
	FieldTypeUInt64  FieldType = "uint64"
	FieldTypeInt8    FieldType = "int8"
	FieldTypeInt16   FieldType = "int16"
	FieldTypeInt32   FieldType = "int32"
	FieldTypeInt64   FieldType = "int64"
	FieldTypeFloat32 FieldType = "float32"
	FieldTypeFloat64 FieldType = "float64"
	FieldTypeBytes   FieldType = "bytes"
	FieldTypeString  FieldType = "string"
)

type Endian string

const (
	EndianLittle Endian = "little"
	EndianBig    Endian = "big"
)

type ChecksumType string

const (
	ChecksumTypeCRC16    ChecksumType = "crc16"
	ChecksumTypeCRC32    ChecksumType = "crc32"
	ChecksumTypeXOR      ChecksumType = "xor"
	ChecksumTypeSum8     ChecksumType = "sum8"
	ChecksumTypeSum16    ChecksumType = "sum16"
	ChecksumTypeModbusRTU ChecksumType = "modbus_rtu"
)

type Field struct {
	Name       string                 `json:"name"`
	Type       FieldType              `json:"type"`
	ByteLength int                    `json:"byte_length,omitempty"`
	Min        interface{}            `json:"min,omitempty"`
	Max        interface{}            `json:"max,omitempty"`
	Value      interface{}            `json:"value,omitempty"`
	EnumValues []interface{}          `json:"enum_values,omitempty"`
	Endian     Endian                 `json:"endian,omitempty"`
	IsChecksum bool                   `json:"is_checksum,omitempty"`
	ChecksumOf []string               `json:"checksum_of,omitempty"`
	ChecksumType ChecksumType         `json:"checksum_type,omitempty"`
	IsVariable bool                   `json:"is_variable,omitempty"`
	LengthField string                `json:"length_field,omitempty"`
	Mutable    *bool                  `json:"mutable,omitempty"`
}

type ProtocolDescription struct {
	Name        string   `json:"name"`
	Version     string   `json:"version"`
	Endian      Endian   `json:"endian"`
	Header      []Field  `json:"header"`
	Body        []Field  `json:"body"`
	Tail        []Field  `json:"tail"`
	MinMsgSize  int      `json:"min_msg_size"`
	MaxMsgSize  int      `json:"max_msg_size"`
}

type ParsedField struct {
	Field
	RawValue []byte
	Offset   int
}

type ParsedMessage struct {
	Protocol *ProtocolDescription
	Header   []ParsedField
	Body     []ParsedField
	Tail     []ParsedField
	Raw      []byte
}

func LoadProtocolDescription(path string) (*ProtocolDescription, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read protocol file: %w", err)
	}

	return LoadProtocolDescriptionFromData(data)
}

func LoadProtocolDescriptionFromData(data []byte) (*ProtocolDescription, error) {
	var pd ProtocolDescription
	if err := json.Unmarshal(data, &pd); err != nil {
		return nil, fmt.Errorf("failed to parse protocol JSON: %w", err)
	}

	if err := pd.Validate(); err != nil {
		return nil, fmt.Errorf("invalid protocol description: %w", err)
	}

	return &pd, nil
}

func (pd *ProtocolDescription) Validate() error {
	if pd.Name == "" {
		return fmt.Errorf("protocol name is required")
	}
	if pd.Endian == "" {
		pd.Endian = EndianBig
	}

	for i, f := range pd.Header {
		if err := validateField(&pd.Header[i], pd.Endian); err != nil {
			return fmt.Errorf("header field %d (%s): %w", i, f.Name, err)
		}
	}
	for i, f := range pd.Body {
		if err := validateField(&pd.Body[i], pd.Endian); err != nil {
			return fmt.Errorf("body field %d (%s): %w", i, f.Name, err)
		}
	}
	for i, f := range pd.Tail {
		if err := validateField(&pd.Tail[i], pd.Endian); err != nil {
			return fmt.Errorf("tail field %d (%s): %w", i, f.Name, err)
		}
	}

	if pd.MinMsgSize == 0 {
		pd.MinMsgSize = pd.calculateMinSize()
	}
	if pd.MaxMsgSize == 0 {
		pd.MaxMsgSize = pd.calculateMaxSize()
	}

	return nil
}

func validateField(f *Field, defaultEndian Endian) error {
	if f.Name == "" {
		return fmt.Errorf("field name is required")
	}
	if f.Type == "" {
		return fmt.Errorf("field type is required")
	}
	if f.Endian == "" {
		f.Endian = defaultEndian
	}
	if f.Mutable == nil {
		t := true
		f.Mutable = &t
	}

	switch f.Type {
	case FieldTypeBytes, FieldTypeString:
		if f.ByteLength == 0 && !f.IsVariable {
			return fmt.Errorf("byte_length required for bytes/string type or set is_variable=true")
		}
	case FieldTypeUInt8, FieldTypeInt8:
		f.ByteLength = 1
	case FieldTypeUInt16, FieldTypeInt16:
		f.ByteLength = 2
	case FieldTypeUInt32, FieldTypeInt32, FieldTypeFloat32:
		f.ByteLength = 4
	case FieldTypeUInt64, FieldTypeInt64, FieldTypeFloat64:
		f.ByteLength = 8
	}

	return nil
}

func (pd *ProtocolDescription) calculateMinSize() int {
	size := 0
	for _, f := range pd.Header {
		if !f.IsVariable {
			size += f.ByteLength
		}
	}
	for _, f := range pd.Body {
		if !f.IsVariable {
			size += f.ByteLength
		}
	}
	for _, f := range pd.Tail {
		if !f.IsVariable {
			size += f.ByteLength
		}
	}
	return size
}

func (pd *ProtocolDescription) calculateMaxSize() int {
	size := 0
	for _, f := range pd.Header {
		if f.IsVariable {
			if max, ok := f.Max.(float64); ok {
				size += int(max)
			} else {
				size += 256
			}
		} else {
			size += f.ByteLength
		}
	}
	for _, f := range pd.Body {
		if f.IsVariable {
			if max, ok := f.Max.(float64); ok {
				size += int(max)
			} else {
				size += 1024
			}
		} else {
			size += f.ByteLength
		}
	}
	for _, f := range pd.Tail {
		if f.IsVariable {
			if max, ok := f.Max.(float64); ok {
				size += int(max)
			} else {
				size += 256
			}
		} else {
			size += f.ByteLength
		}
	}
	return size
}

func (pd *ProtocolDescription) AllFields() []*Field {
	fields := make([]*Field, 0, len(pd.Header)+len(pd.Body)+len(pd.Tail))
	for i := range pd.Header {
		fields = append(fields, &pd.Header[i])
	}
	for i := range pd.Body {
		fields = append(fields, &pd.Body[i])
	}
	for i := range pd.Tail {
		fields = append(fields, &pd.Tail[i])
	}
	return fields
}

func (f *Field) GetByteOrder() binary.ByteOrder {
	if f.Endian == EndianLittle {
		return binary.LittleEndian
	}
	return binary.BigEndian
}

func (f *Field) IsMutable() bool {
	if f.Mutable == nil {
		return true
	}
	return *f.Mutable
}

func (f *Field) GetMinMax() (float64, float64, bool) {
	var min, max float64
	hasRange := false

	switch f.Type {
	case FieldTypeUInt8:
		min, max = 0, math.MaxUint8
	case FieldTypeUInt16:
		min, max = 0, math.MaxUint16
	case FieldTypeUInt32:
		min, max = 0, math.MaxUint32
	case FieldTypeUInt64:
		min, max = 0, math.MaxFloat64
	case FieldTypeInt8:
		min, max = math.MinInt8, math.MaxInt8
	case FieldTypeInt16:
		min, max = math.MinInt16, math.MaxInt16
	case FieldTypeInt32:
		min, max = math.MinInt32, math.MaxInt32
	case FieldTypeInt64:
		min, max = math.MinInt64, math.MaxInt64
	case FieldTypeFloat32, FieldTypeFloat64:
		min, max = -math.MaxFloat64, math.MaxFloat64
	default:
		return 0, 0, false
	}

	if f.Min != nil {
		if v, ok := f.Min.(float64); ok {
			min = v
			hasRange = true
		}
	}
	if f.Max != nil {
		if v, ok := f.Max.(float64); ok {
			max = v
			hasRange = true
		}
	}

	return min, max, hasRange
}
