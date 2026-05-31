package mutator

import (
	"encoding/binary"
	"fmt"
	"math"
	"math/rand"

	"tcp-fuzzer/internal/protocol"
)

type MutationStrategy string

const (
	StrategyBitFlip      MutationStrategy = "bit_flip"
	StrategyBitFlipByte MutationStrategy = "bit_flip_byte"
	StrategyBitFlipWord MutationStrategy = "bit_flip_word"
	StrategyBitFlipDword MutationStrategy = "bit_flip_dword"
	StrategyArithmetic   MutationStrategy = "arithmetic"
	StrategyBoundary     MutationStrategy = "boundary"
	StrategyRandom       MutationStrategy = "random"
	StrategyBlockInsert  MutationStrategy = "block_insert"
	StrategyBlockDelete  MutationStrategy = "block_delete"
	StrategyBlockDuplicate MutationStrategy = "block_duplicate"
	StrategyKnownValue   MutationStrategy = "known_value"
)

type Mutator struct {
	proto *protocol.ProtocolDescription
	rng   *rand.Rand
}

type MutationResult struct {
	Data     []byte
	Strategy MutationStrategy
	Field    string
	Position int
}

func NewMutator(proto *protocol.ProtocolDescription, seed int64) *Mutator {
	return &Mutator{
		proto: proto,
		rng:   rand.New(rand.NewSource(seed)),
	}
}

func (m *Mutator) Mutate(data []byte) (*MutationResult, error) {
	if len(data) == 0 {
		return nil, fmt.Errorf("cannot mutate empty data")
	}

	strategies := m.selectStrategies(data)
	strategy := strategies[m.rng.Intn(len(strategies))]

	var result *MutationResult
	var err error

	switch strategy {
	case StrategyBitFlip:
		result, err = m.mutateBitFlip(data, 1)
	case StrategyBitFlipByte:
		result, err = m.mutateBitFlip(data, 8)
	case StrategyBitFlipWord:
		result, err = m.mutateBitFlipWord(data)
	case StrategyBitFlipDword:
		result, err = m.mutateBitFlipDword(data)
	case StrategyArithmetic:
		result, err = m.mutateArithmetic(data)
	case StrategyBoundary:
		result, err = m.mutateBoundary(data)
	case StrategyRandom:
		result, err = m.mutateRandom(data)
	case StrategyBlockInsert:
		result, err = m.mutateBlockInsert(data)
	case StrategyBlockDelete:
		result, err = m.mutateBlockDelete(data)
	case StrategyBlockDuplicate:
		result, err = m.mutateBlockDuplicate(data)
	case StrategyKnownValue:
		result, err = m.mutateKnownValue(data)
	default:
		result, err = m.mutateBitFlip(data, 1)
	}

	if err != nil {
		return nil, err
	}

	if result.Data, err = protocol.RecalculateChecksums(m.proto, result.Data); err != nil {
		return nil, fmt.Errorf("failed to recalculate checksums: %w", err)
	}

	return result, nil
}

func (m *Mutator) selectStrategies(data []byte) []MutationStrategy {
	strategies := []MutationStrategy{
		StrategyBitFlip,
		StrategyArithmetic,
		StrategyBoundary,
		StrategyRandom,
	}

	if len(data) >= 2 {
		strategies = append(strategies, StrategyBitFlipByte, StrategyBitFlipWord)
	}
	if len(data) >= 4 {
		strategies = append(strategies, StrategyBitFlipDword)
	}
	if len(data) > 0 {
		strategies = append(strategies, StrategyBlockInsert, StrategyBlockDelete, StrategyBlockDuplicate)
	}

	return strategies
}

func (m *Mutator) mutateBitFlip(data []byte, bits int) (*MutationResult, error) {
	result := make([]byte, len(data))
	copy(result, data)

	bytePos := m.rng.Intn(len(data))
	bitPos := m.rng.Intn(8)

	for i := 0; i < bits && bytePos*8+bitPos+i < len(data)*8; i++ {
		bp := bytePos + (bitPos+i)/8
		bi := (bitPos + i) % 8
		result[bp] ^= 1 << bi
	}

	return &MutationResult{
		Data:     result,
		Strategy: StrategyBitFlip,
		Position: bytePos,
	}, nil
}

func (m *Mutator) mutateBitFlipWord(data []byte) (*MutationResult, error) {
	result := make([]byte, len(data))
	copy(result, data)

	if len(data) < 2 {
		return m.mutateBitFlip(data, 8)
	}

	pos := m.rng.Intn(len(data) - 1)
	mask := uint16(1 << m.rng.Intn(16))
	bo := m.proto.Endian

	var word uint16
	if bo == protocol.EndianLittle {
		word = binary.LittleEndian.Uint16(result[pos:])
	} else {
		word = binary.BigEndian.Uint16(result[pos:])
	}
	word ^= mask

	if bo == protocol.EndianLittle {
		binary.LittleEndian.PutUint16(result[pos:], word)
	} else {
		binary.BigEndian.PutUint16(result[pos:], word)
	}

	return &MutationResult{
		Data:     result,
		Strategy: StrategyBitFlipWord,
		Position: pos,
	}, nil
}

func (m *Mutator) mutateBitFlipDword(data []byte) (*MutationResult, error) {
	result := make([]byte, len(data))
	copy(result, data)

	if len(data) < 4 {
		return m.mutateBitFlipWord(data)
	}

	pos := m.rng.Intn(len(data) - 3)
	mask := uint32(1 << m.rng.Intn(32))
	bo := m.proto.Endian

	var dword uint32
	if bo == protocol.EndianLittle {
		dword = binary.LittleEndian.Uint32(result[pos:])
	} else {
		dword = binary.BigEndian.Uint32(result[pos:])
	}
	dword ^= mask

	if bo == protocol.EndianLittle {
		binary.LittleEndian.PutUint32(result[pos:], dword)
	} else {
		binary.BigEndian.PutUint32(result[pos:], dword)
	}

	return &MutationResult{
		Data:     result,
		Strategy: StrategyBitFlipDword,
		Position: pos,
	}, nil
}

func (m *Mutator) mutateArithmetic(data []byte) (*MutationResult, error) {
	result := make([]byte, len(data))
	copy(result, data)

	fields := m.proto.AllFields()
	mutableFields := make([]*protocol.Field, 0, len(fields))
	for _, f := range fields {
		if f.IsMutable() && !f.IsChecksum && !f.IsVariable {
			mutableFields = append(mutableFields, f)
		}
	}

	if len(mutableFields) == 0 {
		return m.mutateBitFlip(data, 1)
	}

	field := mutableFields[m.rng.Intn(len(mutableFields))]
	offset := m.getFieldOffset(field)

	if offset < 0 || offset+field.ByteLength > len(data) {
		return m.mutateBitFlip(data, 1)
	}

	delta := m.rng.Intn(8) - 4
	if delta == 0 {
		delta = 1
	}

	bo := field.GetByteOrder()
	switch field.Type {
	case protocol.FieldTypeUInt8:
		val := uint8(int(data[offset]) + delta)
		result[offset] = val
	case protocol.FieldTypeUInt16:
		val := uint16(int(bo.Uint16(data[offset:])) + delta)
		bo.PutUint16(result[offset:], val)
	case protocol.FieldTypeUInt32:
		val := uint32(int64(bo.Uint32(data[offset:])) + int64(delta))
		bo.PutUint32(result[offset:], val)
	case protocol.FieldTypeInt8:
		val := int8(int(data[offset]) + delta)
		result[offset] = byte(val)
	case protocol.FieldTypeInt16:
		val := int16(int(int16(bo.Uint16(data[offset:]))) + delta)
		bo.PutUint16(result[offset:], uint16(val))
	case protocol.FieldTypeInt32:
		val := int32(int64(int32(bo.Uint32(data[offset:]))) + int64(delta))
		bo.PutUint32(result[offset:], uint32(val))
	default:
		return m.mutateBitFlip(data, 1)
	}

	return &MutationResult{
		Data:     result,
		Strategy: StrategyArithmetic,
		Field:    field.Name,
		Position: offset,
	}, nil
}

func (m *Mutator) mutateBoundary(data []byte) (*MutationResult, error) {
	result := make([]byte, len(data))
	copy(result, data)

	fields := m.proto.AllFields()
	mutableFields := make([]*protocol.Field, 0, len(fields))
	for _, f := range fields {
		if f.IsMutable() && !f.IsChecksum && !f.IsVariable {
			mutableFields = append(mutableFields, f)
		}
	}

	if len(mutableFields) == 0 {
		return m.mutateBitFlip(data, 1)
	}

	field := mutableFields[m.rng.Intn(len(mutableFields))]
	offset := m.getFieldOffset(field)
	bo := field.GetByteOrder()

	boundaryValues := m.getBoundaryValues(field)
	val := boundaryValues[m.rng.Intn(len(boundaryValues))]

	switch field.Type {
	case protocol.FieldTypeUInt8:
		result[offset] = uint8(val)
	case protocol.FieldTypeUInt16:
		bo.PutUint16(result[offset:], uint16(val))
	case protocol.FieldTypeUInt32:
		bo.PutUint32(result[offset:], uint32(val))
	case protocol.FieldTypeUInt64:
		bo.PutUint64(result[offset:], uint64(val))
	case protocol.FieldTypeInt8:
		result[offset] = byte(int8(val))
	case protocol.FieldTypeInt16:
		bo.PutUint16(result[offset:], uint16(int16(val)))
	case protocol.FieldTypeInt32:
		bo.PutUint32(result[offset:], uint32(int32(val)))
	case protocol.FieldTypeInt64:
		bo.PutUint64(result[offset:], uint64(int64(val)))
	default:
		return m.mutateBitFlip(data, 1)
	}

	return &MutationResult{
		Data:     result,
		Strategy: StrategyBoundary,
		Field:    field.Name,
		Position: offset,
	}, nil
}

func (m *Mutator) getBoundaryValues(f *protocol.Field) []int64 {
	min, max, hasRange := f.GetMinMax()
	values := make([]int64, 0)

	if hasRange {
		values = append(values, int64(min), int64(max))
		if min < 0 {
			values = append(values, int64(min)+1, int64(min)-1)
		}
		if max > 0 {
			values = append(values, int64(max)-1, int64(max)+1)
		}
	}

	values = append(values, 0, 1, -1)

	switch f.Type {
	case protocol.FieldTypeUInt8:
		values = append(values, math.MaxUint8-1, math.MaxUint8)
	case protocol.FieldTypeUInt16:
		values = append(values, math.MaxUint16-1, math.MaxUint16)
	case protocol.FieldTypeUInt32:
		values = append(values, math.MaxUint32-1, math.MaxUint32)
	case protocol.FieldTypeInt8:
		values = append(values, math.MinInt8, math.MaxInt8)
	case protocol.FieldTypeInt16:
		values = append(values, math.MinInt16, math.MaxInt16)
	case protocol.FieldTypeInt32:
		values = append(values, math.MinInt32, math.MaxInt32)
	}

	return values
}

func (m *Mutator) mutateRandom(data []byte) (*MutationResult, error) {
	result := make([]byte, len(data))
	copy(result, data)

	pos := m.rng.Intn(len(data))
	result[pos] = byte(m.rng.Intn(256))

	return &MutationResult{
		Data:     result,
		Strategy: StrategyRandom,
		Position: pos,
	}, nil
}

func (m *Mutator) mutateBlockInsert(data []byte) (*MutationResult, error) {
	if len(data) >= m.proto.MaxMsgSize {
		return m.mutateBitFlip(data, 1)
	}

	insertPos := m.rng.Intn(len(data) + 1)
	blockSize := m.rng.Intn(min(32, m.proto.MaxMsgSize-len(data))) + 1

	result := make([]byte, 0, len(data)+blockSize)
	result = append(result, data[:insertPos]...)

	block := make([]byte, blockSize)
	m.rng.Read(block)
	result = append(result, block...)
	result = append(result, data[insertPos:]...)

	return &MutationResult{
		Data:     result,
		Strategy: StrategyBlockInsert,
		Position: insertPos,
	}, nil
}

func (m *Mutator) mutateBlockDelete(data []byte) (*MutationResult, error) {
	if len(data) <= m.proto.MinMsgSize {
		return m.mutateBitFlip(data, 1)
	}

	deletePos := m.rng.Intn(len(data))
	maxDelete := len(data) - m.proto.MinMsgSize
	if maxDelete <= 0 {
		maxDelete = 1
	}
	deleteSize := m.rng.Intn(min(16, maxDelete)) + 1
	if deletePos+deleteSize > len(data) {
		deleteSize = len(data) - deletePos
	}

	result := make([]byte, 0, len(data)-deleteSize)
	result = append(result, data[:deletePos]...)
	result = append(result, data[deletePos+deleteSize:]...)

	return &MutationResult{
		Data:     result,
		Strategy: StrategyBlockDelete,
		Position: deletePos,
	}, nil
}

func (m *Mutator) mutateBlockDuplicate(data []byte) (*MutationResult, error) {
	if len(data) >= m.proto.MaxMsgSize {
		return m.mutateBitFlip(data, 1)
	}

	srcPos := m.rng.Intn(len(data))
	maxCopy := min(32, len(data)-srcPos, m.proto.MaxMsgSize-len(data))
	if maxCopy <= 0 {
		return m.mutateBitFlip(data, 1)
	}
	copySize := m.rng.Intn(maxCopy) + 1

	dstPos := m.rng.Intn(len(data) + 1)

	result := make([]byte, 0, len(data)+copySize)
	result = append(result, data[:dstPos]...)
	result = append(result, data[srcPos:srcPos+copySize]...)
	result = append(result, data[dstPos:]...)

	return &MutationResult{
		Data:     result,
		Strategy: StrategyBlockDuplicate,
		Position: dstPos,
	}, nil
}

func (m *Mutator) mutateKnownValue(data []byte) (*MutationResult, error) {
	result := make([]byte, len(data))
	copy(result, data)

	knownValues := [][]byte{
		{0x00, 0x00, 0x00, 0x00},
		{0xff, 0xff, 0xff, 0xff},
		{0x00, 0x00, 0x00, 0x80},
		{0xff, 0xff, 0xff, 0x7f},
		{0x00, 0x00, 0x80, 0x00},
		{0x01, 0x00, 0x00, 0x00},
		{0xfe, 0xff, 0xff, 0xff},
		{0x00, 0x01, 0x00, 0x00},
	}

	val := knownValues[m.rng.Intn(len(knownValues))]
	pos := m.rng.Intn(len(data))

	for i := 0; i < len(val) && pos+i < len(result); i++ {
		result[pos+i] = val[i]
	}

	return &MutationResult{
		Data:     result,
		Strategy: StrategyKnownValue,
		Position: pos,
	}, nil
}

func (m *Mutator) getFieldOffset(field *protocol.Field) int {
	offset := 0
	for _, f := range m.proto.Header {
		if f.Name == field.Name {
			return offset
		}
		offset += f.ByteLength
	}
	for _, f := range m.proto.Body {
		if f.Name == field.Name {
			return offset
		}
		offset += f.ByteLength
	}
	for _, f := range m.proto.Tail {
		if f.Name == field.Name {
			return offset
		}
		offset += f.ByteLength
	}
	return -1
}

func (m *Mutator) MutateMultiple(data []byte, count int) ([]*MutationResult, error) {
	results := make([]*MutationResult, 0, count)
	current := make([]byte, len(data))
	copy(current, data)

	for i := 0; i < count; i++ {
		result, err := m.Mutate(current)
		if err != nil {
			return nil, err
		}
		results = append(results, result)
		current = result.Data
	}

	return results, nil
}

func min(a, b int, rest ...int) int {
	m := a
	if b < m {
		m = b
	}
	for _, v := range rest {
		if v < m {
			m = v
		}
	}
	return m
}
