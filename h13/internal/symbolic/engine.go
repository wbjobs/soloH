package symbolic

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math/rand"
	"sync"
	"time"

	"tcp-fuzzer/internal/protocol"
)

type ExprType int

const (
	ExprConst ExprType = iota
	ExprVar
	ExprAdd
	ExprSub
	ExprXor
	ExprAnd
	ExprOr
	ExprNot
	ExprRol
	ExprRor
	ExprConcat
	ExprExtract
)

type Expr struct {
	Type     ExprType
	ConstVal uint64
	BitWidth int
	Children []*Expr
	VarName  string
}

type ChecksumConstraint struct {
	TargetField   string
	SourceFields  []string
	ChecksumType  protocol.ChecksumType
	Offset        int
	ByteLength    int
	Expression    *Expr
}

type SymbolicPacket struct {
	Fields      map[string]*Expr
	Constraints []*ChecksumConstraint
	RawLength   int
	ByteOrder   protocol.Endian
}

type SolverResult struct {
	FieldValues map[string][]byte
	FullPacket  []byte
	Solved      bool
}

type Engine struct {
	proto     *protocol.ProtocolDescription
	rng       *rand.Rand
	cache     map[string]*SolverResult
	cacheLock sync.RWMutex
	maxCache  int
}

type EngineConfig struct {
	Proto     *protocol.ProtocolDescription
	BaseSeed  int64
	MaxCache  int
}

func NewEngine(cfg EngineConfig) *Engine {
	if cfg.BaseSeed == 0 {
		cfg.BaseSeed = time.Now().UnixNano()
	}
	if cfg.MaxCache <= 0 {
		cfg.MaxCache = 10000
	}

	return &Engine{
		proto:    cfg.Proto,
		rng:      rand.New(rand.NewSource(cfg.BaseSeed)),
		cache:    make(map[string]*SolverResult),
		maxCache: cfg.MaxCache,
	}
}

func (e *Engine) BuildSymbolicPacket(initialValues map[string][]byte) (*SymbolicPacket, error) {
	sp := &SymbolicPacket{
		Fields:      make(map[string]*Expr),
		Constraints: make([]*ChecksumConstraint, 0),
		ByteOrder:   e.proto.Endian,
	}

	offset := 0

	processFields := func(fields []protocol.Field) error {
		for _, f := range fields {
			fieldName := f.Name

			if f.IsChecksum {
				constraint := &ChecksumConstraint{
					TargetField:  fieldName,
					SourceFields: make([]string, 0),
					ChecksumType: f.ChecksumType,
					Offset:       offset,
					ByteLength:   f.ByteLength,
				}

				if len(f.ChecksumOf) > 0 {
					constraint.SourceFields = append(constraint.SourceFields, f.ChecksumOf...)
				} else {
					for name := range sp.Fields {
						constraint.SourceFields = append(constraint.SourceFields, name)
					}
				}

				sp.Fields[fieldName] = &Expr{
					Type:     ExprVar,
					VarName:  fieldName,
					BitWidth: f.ByteLength * 8,
				}
				sp.Constraints = append(sp.Constraints, constraint)
			} else {
				var expr *Expr
				if val, ok := initialValues[fieldName]; ok && val != nil {
					expr = bytesToConstExpr(val, f.ByteLength, sp.ByteOrder)
				} else {
					expr = &Expr{
						Type:     ExprVar,
						VarName:  fieldName,
						BitWidth: f.ByteLength * 8,
					}
				}
				sp.Fields[fieldName] = expr
			}

			if f.IsVariable {
				offset += f.ByteLength
			} else {
				offset += f.ByteLength
			}
		}
		return nil
	}

	if err := processFields(e.proto.Header); err != nil {
		return nil, err
	}
	if err := processFields(e.proto.Body); err != nil {
		return nil, err
	}
	if err := processFields(e.proto.Tail); err != nil {
		return nil, err
	}

	sp.RawLength = offset
	return sp, nil
}

func (e *Engine) Solve(packet *SymbolicPacket, concreteData []byte) (*SolverResult, error) {
	cacheKey := e.computeCacheKey(concreteData)

	e.cacheLock.RLock()
	if cached, ok := e.cache[cacheKey]; ok {
		e.cacheLock.RUnlock()
		return cached, nil
	}
	e.cacheLock.RUnlock()

	result := &SolverResult{
		FieldValues: make(map[string][]byte),
		Solved:      false,
	}

	parsed, err := protocol.ParseMessage(e.proto, concreteData)
	if err != nil {
		return e.solveFallback(packet, concreteData), nil
	}

	for _, pf := range parsed.Header {
		if !pf.Field.IsChecksum {
			result.FieldValues[pf.Name] = make([]byte, len(pf.RawValue))
			copy(result.FieldValues[pf.Name], pf.RawValue)
		}
	}
	for _, pf := range parsed.Body {
		if !pf.Field.IsChecksum {
			result.FieldValues[pf.Name] = make([]byte, len(pf.RawValue))
			copy(result.FieldValues[pf.Name], pf.RawValue)
		}
	}
	for _, pf := range parsed.Tail {
		if !pf.Field.IsChecksum {
			result.FieldValues[pf.Name] = make([]byte, len(pf.RawValue))
			copy(result.FieldValues[pf.Name], pf.RawValue)
		}
	}

	solvedPacket := make([]byte, len(concreteData))
	copy(solvedPacket, concreteData)

	fieldOffsets := make(map[string][2]int)
	currOffset := 0

	collectOffsets := func(pfs []protocol.ParsedField) {
		for _, pf := range pfs {
			if !pf.Field.IsChecksum {
				fieldOffsets[pf.Name] = [2]int{pf.Offset, pf.Offset + len(pf.RawValue)}
			}
			currOffset = pf.Offset + len(pf.RawValue)
		}
	}
	collectOffsets(parsed.Header)
	collectOffsets(parsed.Body)

	for _, pf := range parsed.Tail {
		if pf.Field.IsChecksum {
			var checksumData []byte
			if len(pf.Field.ChecksumOf) > 0 {
				for _, fname := range pf.Field.ChecksumOf {
					if rng, ok := fieldOffsets[fname]; ok {
						start, end := rng[0], rng[1]
						if start < len(solvedPacket) && end <= len(solvedPacket) {
							checksumData = append(checksumData, solvedPacket[start:end]...)
						}
					}
				}
			} else {
				if currOffset <= len(solvedPacket) {
					checksumData = solvedPacket[:currOffset]
				} else {
					checksumData = solvedPacket
				}
			}

			if len(checksumData) == 0 {
				checksumData = []byte{0}
			}

			var checksum []byte
			switch pf.Field.ChecksumType {
			case protocol.ChecksumTypeCRC16:
				checksum = e.solveCRC16(checksumData)
			case protocol.ChecksumTypeCRC32:
				checksum = e.solveCRC32(checksumData)
			case protocol.ChecksumTypeXOR:
				checksum = e.solveXOR(checksumData, pf.Field.ByteLength)
			case protocol.ChecksumTypeSum8:
				checksum = e.solveSum8(checksumData)
			case protocol.ChecksumTypeSum16:
				checksum = e.solveSum16(checksumData, pf.Field.Endian)
			case protocol.ChecksumTypeModbusRTU:
				checksum = e.solveModbusRTUCRC(checksumData)
			default:
				checksum = make([]byte, pf.Field.ByteLength)
			}

			if len(checksum) > pf.Field.ByteLength {
				checksum = checksum[:pf.Field.ByteLength]
			}

			result.FieldValues[pf.Name] = make([]byte, len(checksum))
			copy(result.FieldValues[pf.Name], checksum)

			if pf.Offset+pf.Field.ByteLength <= len(solvedPacket) {
				copy(solvedPacket[pf.Offset:pf.Offset+pf.Field.ByteLength], checksum)
			}
		} else {
			fieldOffsets[pf.Name] = [2]int{pf.Offset, pf.Offset + len(pf.RawValue)}
			currOffset = pf.Offset + len(pf.RawValue)
		}
	}

	result.FullPacket = solvedPacket
	result.Solved = true

	e.addToCache(cacheKey, result)
	return result, nil
}

func (e *Engine) solveFallback(packet *SymbolicPacket, concreteData []byte) *SolverResult {
	result := &SolverResult{
		FieldValues: make(map[string][]byte),
		FullPacket:  make([]byte, len(concreteData)),
		Solved:      true,
	}
	copy(result.FullPacket, concreteData)

	recalculated, err := protocol.RecalculateChecksums(e.proto, concreteData)
	if err == nil {
		result.FullPacket = recalculated
	}

	return result
}

func (e *Engine) solveCRC16(data []byte) []byte {
	crc := uint16(0xFFFF)
	poly := uint16(0xA001)

	for _, b := range data {
		crc ^= uint16(b)
		for i := 0; i < 8; i++ {
			if crc&1 != 0 {
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

func (e *Engine) solveCRC32(data []byte) []byte {
	crc := uint32(0xFFFFFFFF)
	for _, b := range data {
		crc ^= uint32(b)
		for i := 0; i < 8; i++ {
			if crc&1 != 0 {
				crc = (crc >> 1) ^ 0xEDB88320
			} else {
				crc >>= 1
			}
		}
	}
	crc ^= 0xFFFFFFFF

	buf := make([]byte, 4)
	buf[0] = byte(crc)
	buf[1] = byte(crc >> 8)
	buf[2] = byte(crc >> 16)
	buf[3] = byte(crc >> 24)
	return buf
}

func (e *Engine) solveXOR(data []byte, length int) []byte {
	result := make([]byte, length)
	for i := 0; i < len(data); i++ {
		result[i%length] ^= data[i]
	}
	return result
}

func (e *Engine) solveSum8(data []byte) []byte {
	var sum uint8
	for _, b := range data {
		sum += b
	}
	return []byte{sum}
}

func (e *Engine) solveSum16(data []byte, bo protocol.Endian) []byte {
	var sum uint16
	for _, b := range data {
		sum += uint16(b)
	}
	buf := make([]byte, 2)
	if bo == protocol.EndianLittle {
		buf[0] = byte(sum)
		buf[1] = byte(sum >> 8)
	} else {
		buf[0] = byte(sum >> 8)
		buf[1] = byte(sum)
	}
	return buf
}

func (e *Engine) solveModbusRTUCRC(data []byte) []byte {
	crc := uint16(0xFFFF)
	for _, b := range data {
		crc ^= uint16(b)
		for i := 0; i < 8; i++ {
			if (crc & 0x0001) != 0 {
				crc = (crc >> 1) ^ 0xA001
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

func (e *Engine) Evaluate(expr *Expr, values map[string]uint64) (uint64, error) {
	switch expr.Type {
	case ExprConst:
		return expr.ConstVal, nil
	case ExprVar:
		if val, ok := values[expr.VarName]; ok {
			return val, nil
		}
		return 0, fmt.Errorf("undefined variable: %s", expr.VarName)
	case ExprAdd:
		left, err := e.Evaluate(expr.Children[0], values)
		if err != nil {
			return 0, err
		}
		right, err := e.Evaluate(expr.Children[1], values)
		if err != nil {
			return 0, err
		}
		return (left + right) & mask(expr.BitWidth), nil
	case ExprSub:
		left, err := e.Evaluate(expr.Children[0], values)
		if err != nil {
			return 0, err
		}
		right, err := e.Evaluate(expr.Children[1], values)
		if err != nil {
			return 0, err
		}
		return (left - right) & mask(expr.BitWidth), nil
	case ExprXor:
		left, err := e.Evaluate(expr.Children[0], values)
		if err != nil {
			return 0, err
		}
		right, err := e.Evaluate(expr.Children[1], values)
		if err != nil {
			return 0, err
		}
		return left ^ right, nil
	case ExprAnd:
		left, err := e.Evaluate(expr.Children[0], values)
		if err != nil {
			return 0, err
		}
		right, err := e.Evaluate(expr.Children[1], values)
		if err != nil {
			return 0, err
		}
		return left & right, nil
	case ExprOr:
		left, err := e.Evaluate(expr.Children[0], values)
		if err != nil {
			return 0, err
		}
		right, err := e.Evaluate(expr.Children[1], values)
		if err != nil {
			return 0, err
		}
		return left | right, nil
	default:
		return 0, fmt.Errorf("unsupported expression type: %d", expr.Type)
	}
}

func (e *Engine) Simplify(expr *Expr) *Expr {
	if len(expr.Children) == 0 {
		return expr
	}

	simplified := make([]*Expr, len(expr.Children))
	allConst := true
	for i, child := range expr.Children {
		simplified[i] = e.Simplify(child)
		if simplified[i].Type != ExprConst {
			allConst = false
		}
	}

	if allConst {
		values := make(map[string]uint64)
		result, err := e.Evaluate(expr, values)
		if err == nil {
			return &Expr{
				Type:     ExprConst,
				ConstVal: result,
				BitWidth: expr.BitWidth,
			}
		}
	}

	return &Expr{
		Type:     expr.Type,
		BitWidth: expr.BitWidth,
		Children: simplified,
		VarName:  expr.VarName,
	}
}

func (e *Engine) computeCacheKey(data []byte) string {
	hash := sha256.Sum256(data)
	return hex.EncodeToString(hash[:16])
}

func (e *Engine) addToCache(key string, result *SolverResult) {
	e.cacheLock.Lock()
	defer e.cacheLock.Unlock()

	if len(e.cache) >= e.maxCache {
		for k := range e.cache {
			delete(e.cache, k)
			break
		}
	}
	e.cache[key] = result
}

func (e *Engine) ClearCache() {
	e.cacheLock.Lock()
	defer e.cacheLock.Unlock()
	e.cache = make(map[string]*SolverResult)
}

func mask(bitWidth int) uint64 {
	if bitWidth >= 64 {
		return ^uint64(0)
	}
	return (uint64(1) << bitWidth) - 1
}

func bytesToConstExpr(data []byte, byteLength int, bo protocol.Endian) *Expr {
	buf := make([]byte, byteLength)
	copy(buf, data)

	var val uint64
	if bo == protocol.EndianLittle {
		for i := byteLength - 1; i >= 0; i-- {
			val = (val << 8) | uint64(buf[i])
		}
	} else {
		for i := 0; i < byteLength; i++ {
			val = (val << 8) | uint64(buf[i])
		}
	}

	return &Expr{
		Type:     ExprConst,
		ConstVal: val,
		BitWidth: byteLength * 8,
	}
}
