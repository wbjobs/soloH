package protocol

import (
	"encoding/binary"
	"fmt"
	"hash/crc32"
	"math"
	"math/rand"
	"strings"
)

type MessageGenerator struct {
	proto *ProtocolDescription
	rng   *rand.Rand
}

func NewMessageGenerator(proto *ProtocolDescription, seed int64) *MessageGenerator {
	return &MessageGenerator{
		proto: proto,
		rng:   rand.New(rand.NewSource(seed)),
	}
}

func (mg *MessageGenerator) Generate() ([]byte, error) {
	msg := make([]byte, 0, mg.proto.MaxMsgSize)
	var err error

	fieldValues := make(map[string][]byte)

	for i := range mg.proto.Header {
		f := &mg.proto.Header[i]
		var raw []byte
		raw, err = mg.generateFieldValue(f, fieldValues)
		if err != nil {
			return nil, fmt.Errorf("header field %s: %w", f.Name, err)
		}
		fieldValues[f.Name] = raw
		msg = append(msg, raw...)
	}

	for i := range mg.proto.Body {
		f := &mg.proto.Body[i]
		var raw []byte
		raw, err = mg.generateFieldValue(f, fieldValues)
		if err != nil {
			return nil, fmt.Errorf("body field %s: %w", f.Name, err)
		}
		fieldValues[f.Name] = raw
		msg = append(msg, raw...)
	}

	for i := range mg.proto.Tail {
		f := &mg.proto.Tail[i]
		var raw []byte
		if f.IsChecksum {
			raw, err = mg.calculateChecksum(f, msg, fieldValues)
			if err != nil {
				return nil, fmt.Errorf("tail checksum %s: %w", f.Name, err)
			}
		} else {
			raw, err = mg.generateFieldValue(f, fieldValues)
			if err != nil {
				return nil, fmt.Errorf("tail field %s: %w", f.Name, err)
			}
		}
		fieldValues[f.Name] = raw
		msg = append(msg, raw...)
	}

	return msg, nil
}

func (mg *MessageGenerator) generateFieldValue(f *Field, fieldValues map[string][]byte) ([]byte, error) {
	if f.Value != nil {
		return encodeValue(f, f.Value)
	}

	if f.IsVariable && f.LengthField != "" {
		if lenBytes, ok := fieldValues[f.LengthField]; ok {
			length := int(decodeUInt(lenBytes, f.GetByteOrder()))
			f.ByteLength = length
		}
	}

	if f.EnumValues != nil && len(f.EnumValues) > 0 {
		idx := mg.rng.Intn(len(f.EnumValues))
		return encodeValue(f, f.EnumValues[idx])
	}

	switch f.Type {
	case FieldTypeUInt8:
		return encodeValue(f, uint8(mg.randInt(f)))
	case FieldTypeUInt16:
		return encodeValue(f, uint16(mg.randInt(f)))
	case FieldTypeUInt32:
		return encodeValue(f, uint32(mg.randInt(f)))
	case FieldTypeUInt64:
		return encodeValue(f, uint64(mg.randInt(f)))
	case FieldTypeInt8:
		return encodeValue(f, int8(mg.randIntSigned(f)))
	case FieldTypeInt16:
		return encodeValue(f, int16(mg.randIntSigned(f)))
	case FieldTypeInt32:
		return encodeValue(f, int32(mg.randIntSigned(f)))
	case FieldTypeInt64:
		return encodeValue(f, int64(mg.randIntSigned(f)))
	case FieldTypeFloat32:
		return encodeValue(f, float32(mg.randFloat(f)))
	case FieldTypeFloat64:
		return encodeValue(f, mg.randFloat(f))
	case FieldTypeBytes:
		b := make([]byte, f.ByteLength)
		mg.rng.Read(b)
		return b, nil
	case FieldTypeString:
		s := mg.randomString(f.ByteLength)
		return []byte(s), nil
	default:
		return nil, fmt.Errorf("unsupported field type: %s", f.Type)
	}
}

func (mg *MessageGenerator) randInt(f *Field) int64 {
	min, max, _ := f.GetMinMax()
	return mg.rng.Int63n(int64(max-min+1)) + int64(min)
}

func (mg *MessageGenerator) randIntSigned(f *Field) int64 {
	min, max, _ := f.GetMinMax()
	range_ := int64(max - min + 1)
	return mg.rng.Int63n(range_) + int64(min)
}

func (mg *MessageGenerator) randFloat(f *Field) float64 {
	min, max, _ := f.GetMinMax()
	return min + mg.rng.Float64()*(max-min)
}

func (mg *MessageGenerator) randomString(length int) string {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	b := make([]byte, length)
	for i := range b {
		b[i] = charset[mg.rng.Intn(len(charset))]
	}
	return string(b)
}

func encodeValue(f *Field, v interface{}) ([]byte, error) {
	bo := f.GetByteOrder()
	buf := make([]byte, f.ByteLength)

	var uint64Val uint64
	var int64Val int64
	var float64Val float64
	var isNumeric bool

	switch val := v.(type) {
	case uint8:
		uint64Val = uint64(val)
		isNumeric = true
	case uint16:
		uint64Val = uint64(val)
		isNumeric = true
	case uint32:
		uint64Val = uint64(val)
		isNumeric = true
	case uint64:
		uint64Val = val
		isNumeric = true
	case int8:
		int64Val = int64(val)
		isNumeric = true
	case int16:
		int64Val = int64(val)
		isNumeric = true
	case int32:
		int64Val = int64(val)
		isNumeric = true
	case int64:
		int64Val = val
		isNumeric = true
	case int:
		int64Val = int64(val)
		isNumeric = true
	case float32:
		float64Val = float64(val)
		isNumeric = true
	case float64:
		float64Val = val
		isNumeric = true
	case string:
		copy(buf, []byte(val))
		return buf, nil
	case []byte:
		copy(buf, val)
		return buf, nil
	default:
		return nil, fmt.Errorf("unsupported value type: %T", v)
	}

	if isNumeric {
		switch f.Type {
		case FieldTypeUInt8:
			if vf, ok := v.(float64); ok {
				buf[0] = uint8(vf)
			} else {
				buf[0] = uint8(uint64Val)
			}
		case FieldTypeUInt16:
			if vf, ok := v.(float64); ok {
				bo.PutUint16(buf, uint16(vf))
			} else {
				bo.PutUint16(buf, uint16(uint64Val))
			}
		case FieldTypeUInt32:
			if vf, ok := v.(float64); ok {
				bo.PutUint32(buf, uint32(vf))
			} else {
				bo.PutUint32(buf, uint32(uint64Val))
			}
		case FieldTypeUInt64:
			if vf, ok := v.(float64); ok {
				bo.PutUint64(buf, uint64(vf))
			} else {
				bo.PutUint64(buf, uint64Val)
			}
		case FieldTypeInt8:
			if vf, ok := v.(float64); ok {
				buf[0] = byte(int8(vf))
			} else {
				buf[0] = byte(int8(int64Val))
			}
		case FieldTypeInt16:
			if vf, ok := v.(float64); ok {
				bo.PutUint16(buf, uint16(int16(vf)))
			} else {
				bo.PutUint16(buf, uint16(int16(int64Val)))
			}
		case FieldTypeInt32:
			if vf, ok := v.(float64); ok {
				bo.PutUint32(buf, uint32(int32(vf)))
			} else {
				bo.PutUint32(buf, uint32(int32(int64Val)))
			}
		case FieldTypeInt64:
			if vf, ok := v.(float64); ok {
				bo.PutUint64(buf, uint64(int64(vf)))
			} else {
				bo.PutUint64(buf, uint64(int64Val))
			}
		case FieldTypeFloat32:
			bo.PutUint32(buf, math.Float32bits(float32(float64Val)))
		case FieldTypeFloat64:
			bo.PutUint64(buf, math.Float64bits(float64Val))
		}
	}

	return buf, nil
}

func decodeUInt(b []byte, bo binary.ByteOrder) uint64 {
	switch len(b) {
	case 1:
		return uint64(b[0])
	case 2:
		return uint64(bo.Uint16(b))
	case 4:
		return uint64(bo.Uint32(b))
	case 8:
		return bo.Uint64(b)
	default:
		return 0
	}
}

func (mg *MessageGenerator) calculateChecksum(f *Field, msg []byte, fieldValues map[string][]byte) ([]byte, error) {
	var data []byte
	if len(f.ChecksumOf) > 0 {
		for _, fname := range f.ChecksumOf {
			if raw, ok := fieldValues[fname]; ok {
				data = append(data, raw...)
			}
		}
	} else {
		data = msg
	}

	var checksum []byte
	var err error

	switch f.ChecksumType {
	case ChecksumTypeCRC16:
		checksum = calcCRC16(data)
	case ChecksumTypeCRC32:
		checksum = calcCRC32(data)
	case ChecksumTypeXOR:
		checksum = calcXOR(data)
	case ChecksumTypeSum8:
		checksum = calcSum8(data)
	case ChecksumTypeSum16:
		checksum = calcSum16(data, f.GetByteOrder())
	case ChecksumTypeModbusRTU:
		checksum = calcModbusRTUCRC(data)
	default:
		err = fmt.Errorf("unsupported checksum type: %s", f.ChecksumType)
	}

	if err != nil {
		return nil, err
	}

	if len(checksum) > f.ByteLength {
		checksum = checksum[:f.ByteLength]
	} else if len(checksum) < f.ByteLength {
		padded := make([]byte, f.ByteLength)
		copy(padded[f.ByteLength-len(checksum):], checksum)
		checksum = padded
	}

	return checksum, nil
}

func calcCRC16(data []byte) []byte {
	crc := uint16(0xFFFF)
	for _, b := range data {
		crc ^= uint16(b)
		for i := 0; i < 8; i++ {
			if crc&0x0001 != 0 {
				crc = (crc >> 1) ^ 0xA001
			} else {
				crc >>= 1
			}
		}
	}
	buf := make([]byte, 2)
	binary.LittleEndian.PutUint16(buf, crc)
	return buf
}

func calcCRC32(data []byte) []byte {
	crc := crc32.ChecksumIEEE(data)
	buf := make([]byte, 4)
	binary.BigEndian.PutUint32(buf, crc)
	return buf
}

func calcXOR(data []byte) []byte {
	result := byte(0)
	for _, b := range data {
		result ^= b
	}
	return []byte{result}
}

func calcSum8(data []byte) []byte {
	sum := byte(0)
	for _, b := range data {
		sum += b
	}
	return []byte{sum}
}

func calcSum16(data []byte, bo binary.ByteOrder) []byte {
	var sum uint16
	for _, b := range data {
		sum += uint16(b)
	}
	buf := make([]byte, 2)
	bo.PutUint16(buf, sum)
	return buf
}

func calcModbusRTUCRC(data []byte) []byte {
	crc := uint16(0xFFFF)
	poly := uint16(0xA001)
	for _, b := range data {
		crc ^= uint16(b)
		for i := 0; i < 8; i++ {
			if crc&0x0001 != 0 {
				crc = (crc >> 1) ^ poly
			} else {
				crc >>= 1
			}
		}
	}
	buf := make([]byte, 2)
	buf[0] = byte(crc & 0xFF)
	buf[1] = byte(crc >> 8)
	return buf
}

func RecalculateChecksums(proto *ProtocolDescription, data []byte) ([]byte, error) {
	result := make([]byte, len(data))
	copy(result, data)

	parsedMsg, err := ParseMessage(proto, result)
	if err != nil {
		return recalculateChecksumsFallback(proto, result), nil
	}

	fieldOffsets := make(map[string][2]int)
	offset := 0

	processParsedFields := func(fields []ParsedField) {
		for _, pf := range fields {
			fieldOffsets[pf.Name] = [2]int{pf.Offset, pf.Offset + len(pf.RawValue)}
			offset = pf.Offset + len(pf.RawValue)
		}
	}

	processParsedFields(parsedMsg.Header)
	processParsedFields(parsedMsg.Body)

	tailChecksumFields := make([]ParsedField, 0)
	for _, pf := range parsedMsg.Tail {
		if pf.IsChecksum {
			tailChecksumFields = append(tailChecksumFields, pf)
		} else {
			fieldOffsets[pf.Name] = [2]int{pf.Offset, pf.Offset + len(pf.RawValue)}
			offset = pf.Offset + len(pf.RawValue)
		}
	}

	for _, pf := range tailChecksumFields {
		f := &pf.Field

		var checksumData []byte
		if len(f.ChecksumOf) > 0 {
			for _, fname := range f.ChecksumOf {
				if rng, ok := fieldOffsets[fname]; ok {
					start := rng[0]
					end := rng[1]
					if start >= len(result) {
						continue
					}
					if end > len(result) {
						end = len(result)
					}
					checksumData = append(checksumData, result[start:end]...)
				}
			}
		} else {
			if offset > len(result) {
				offset = len(result)
			}
			checksumData = result[:offset]
		}

		if len(checksumData) == 0 {
			checksumData = []byte{0}
		}

		var checksum []byte
		switch f.ChecksumType {
		case ChecksumTypeCRC16:
			checksum = calcCRC16(checksumData)
		case ChecksumTypeCRC32:
			checksum = calcCRC32(checksumData)
		case ChecksumTypeXOR:
			checksum = calcXOR(checksumData)
		case ChecksumTypeSum8:
			checksum = calcSum8(checksumData)
		case ChecksumTypeSum16:
			checksum = calcSum16(checksumData, f.GetByteOrder())
		case ChecksumTypeModbusRTU:
			checksum = calcModbusRTUCRC(checksumData)
		default:
			return nil, fmt.Errorf("unsupported checksum type: %s", f.ChecksumType)
		}

		if len(checksum) > f.ByteLength {
			checksum = checksum[:f.ByteLength]
		}

		if pf.Offset+f.ByteLength <= len(result) {
			copy(result[pf.Offset:pf.Offset+f.ByteLength], checksum)
		}
	}

	return result, nil
}

func recalculateChecksumsFallback(proto *ProtocolDescription, data []byte) []byte {
	result := make([]byte, len(data))
	copy(result, data)

	offset := 0
	fieldOffsets := make(map[string][2]int)

	calculateOffsets := func(fields []Field) {
		for _, f := range fields {
			if f.IsChecksum {
				continue
			}
			fieldLen := f.ByteLength
			if f.IsVariable || offset+fieldLen > len(result) {
				remaining := len(result) - offset
				if remaining <= 0 {
					break
				}
				fieldLen = remaining
			}
			fieldOffsets[f.Name] = [2]int{offset, offset + fieldLen}
			offset += fieldLen
		}
	}

	calculateOffsets(proto.Header)
	calculateOffsets(proto.Body)
	calculateOffsets(proto.Tail)

	for _, f := range proto.Tail {
		if !f.IsChecksum {
			continue
		}

		var checksumData []byte
		if len(f.ChecksumOf) > 0 {
			for _, fname := range f.ChecksumOf {
				if rng, ok := fieldOffsets[fname]; ok {
					start := rng[0]
					end := rng[1]
					if start >= len(result) {
						continue
					}
					if end > len(result) {
						end = len(result)
					}
					checksumData = append(checksumData, result[start:end]...)
				}
			}
		} else {
			cksumOffset := offset
			if cksumOffset > len(result) {
				cksumOffset = len(result)
			}
			checksumData = result[:cksumOffset]
		}

		if len(checksumData) == 0 {
			checksumData = []byte{0}
		}

		var checksum []byte
		switch f.ChecksumType {
		case ChecksumTypeCRC16:
			checksum = calcCRC16(checksumData)
		case ChecksumTypeCRC32:
			checksum = calcCRC32(checksumData)
		case ChecksumTypeXOR:
			checksum = calcXOR(checksumData)
		case ChecksumTypeSum8:
			checksum = calcSum8(checksumData)
		case ChecksumTypeSum16:
			checksum = calcSum16(checksumData, f.GetByteOrder())
		case ChecksumTypeModbusRTU:
			checksum = calcModbusRTUCRC(checksumData)
		default:
			checksum = make([]byte, f.ByteLength)
		}

		if len(checksum) > f.ByteLength {
			checksum = checksum[:f.ByteLength]
		}

		if offset+f.ByteLength <= len(result) {
			copy(result[offset:offset+f.ByteLength], checksum)
		}
		offset += f.ByteLength
	}

	return result
}

func ParseMessage(proto *ProtocolDescription, data []byte) (*ParsedMessage, error) {
	msg := &ParsedMessage{
		Protocol: proto,
		Raw:      data,
	}

	offset := 0

	parseFields := func(fields []Field) ([]ParsedField, error) {
		parsed := make([]ParsedField, 0, len(fields))
		for _, f := range fields {
			if offset+f.ByteLength > len(data) {
				if f.IsVariable {
					f.ByteLength = len(data) - offset
				} else {
					return nil, fmt.Errorf("insufficient data for field %s at offset %d", f.Name, offset)
				}
			}

			pf := ParsedField{
				Field:    f,
				RawValue: data[offset : offset+f.ByteLength],
				Offset:   offset,
			}
			parsed = append(parsed, pf)
			offset += f.ByteLength
		}
		return parsed, nil
	}

	var err error
	msg.Header, err = parseFields(proto.Header)
	if err != nil {
		return nil, err
	}
	msg.Body, err = parseFields(proto.Body)
	if err != nil {
		return nil, err
	}
	msg.Tail, err = parseFields(proto.Tail)
	if err != nil {
		return nil, err
	}

	return msg, nil
}

func (pf *ParsedField) String() string {
	switch pf.Type {
	case FieldTypeString:
		return fmt.Sprintf("%s: %q", pf.Name, string(pf.RawValue))
	default:
		return fmt.Sprintf("%s: 0x%x", pf.Name, pf.RawValue)
	}
}

func (pm *ParsedMessage) String() string {
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("Message (%d bytes):\n", len(pm.Raw)))
	sb.WriteString("  Header:\n")
	for _, f := range pm.Header {
		sb.WriteString(fmt.Sprintf("    %s\n", f.String()))
	}
	sb.WriteString("  Body:\n")
	for _, f := range pm.Body {
		sb.WriteString(fmt.Sprintf("    %s\n", f.String()))
	}
	sb.WriteString("  Tail:\n")
	for _, f := range pm.Tail {
		sb.WriteString(fmt.Sprintf("    %s\n", f.String()))
	}
	return sb.String()
}
