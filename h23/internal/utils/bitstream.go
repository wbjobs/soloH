package utils

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"strings"
)

type BitSource interface {
	NextBit() (int, error)
	ReadBits(n int) ([]int, error)
	Len() int
	Reset() error
}

type FileBitSource struct {
	path     string
	file     *os.File
	reader   *bufio.Reader
	bits     []int
	bitIndex int
	totalLen int
}

type StringBitSource struct {
	data     string
	bitIndex int
}

type SliceBitSource struct {
	bits     []int
	bitIndex int
}

func NewFileBitSource(path string) (*FileBitSource, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}

	bs := &FileBitSource{
		path:   path,
		file:   f,
		reader: bufio.NewReader(f),
	}

	if err := bs.loadAll(); err != nil {
		f.Close()
		return nil, err
	}

	return bs, nil
}

func (bs *FileBitSource) loadAll() error {
	bs.bits = nil
	for {
		b, err := bs.reader.ReadByte()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
		for i := 7; i >= 0; i-- {
			bs.bits = append(bs.bits, (int(b)>>uint(i))&1)
		}
	}
	bs.totalLen = len(bs.bits)
	return nil
}

func (bs *FileBitSource) NextBit() (int, error) {
	if bs.bitIndex >= len(bs.bits) {
		return 0, io.EOF
	}
	bit := bs.bits[bs.bitIndex]
	bs.bitIndex++
	return bit, nil
}

func (bs *FileBitSource) ReadBits(n int) ([]int, error) {
	if bs.bitIndex+n > len(bs.bits) {
		return nil, fmt.Errorf("not enough bits: have %d, need %d", len(bs.bits)-bs.bitIndex, n)
	}
	bits := make([]int, n)
	copy(bits, bs.bits[bs.bitIndex:bs.bitIndex+n])
	bs.bitIndex += n
	return bits, nil
}

func (bs *FileBitSource) Len() int {
	return bs.totalLen
}

func (bs *FileBitSource) Reset() error {
	bs.bitIndex = 0
	return nil
}

func (bs *FileBitSource) Close() error {
	if bs.file != nil {
		return bs.file.Close()
	}
	return nil
}

func NewStringBitSource(data string) (*StringBitSource, error) {
	for _, c := range data {
		if c != '0' && c != '1' {
			return nil, fmt.Errorf("invalid character in bit string: %c", c)
		}
	}
	return &StringBitSource{data: data}, nil
}

func (bs *StringBitSource) NextBit() (int, error) {
	if bs.bitIndex >= len(bs.data) {
		return 0, io.EOF
	}
	bit := int(bs.data[bs.bitIndex] - '0')
	bs.bitIndex++
	return bit, nil
}

func (bs *StringBitSource) ReadBits(n int) ([]int, error) {
	if bs.bitIndex+n > len(bs.data) {
		return nil, fmt.Errorf("not enough bits: have %d, need %d", len(bs.data)-bs.bitIndex, n)
	}
	bits := make([]int, n)
	for i := 0; i < n; i++ {
		bits[i] = int(bs.data[bs.bitIndex+i] - '0')
	}
	bs.bitIndex += n
	return bits, nil
}

func (bs *StringBitSource) Len() int {
	return len(bs.data)
}

func (bs *StringBitSource) Reset() error {
	bs.bitIndex = 0
	return nil
}

func NewSliceBitSource(bits []int) *SliceBitSource {
	return &SliceBitSource{bits: bits}
}

func (bs *SliceBitSource) NextBit() (int, error) {
	if bs.bitIndex >= len(bs.bits) {
		return 0, io.EOF
	}
	bit := bs.bits[bs.bitIndex]
	bs.bitIndex++
	return bit, nil
}

func (bs *SliceBitSource) ReadBits(n int) ([]int, error) {
	if bs.bitIndex+n > len(bs.bits) {
		return nil, fmt.Errorf("not enough bits: have %d, need %d", len(bs.bits)-bs.bitIndex, n)
	}
	bits := make([]int, n)
	copy(bits, bs.bits[bs.bitIndex:bs.bitIndex+n])
	bs.bitIndex += n
	return bits, nil
}

func (bs *SliceBitSource) Len() int {
	return len(bs.bits)
}

func (bs *SliceBitSource) Reset() error {
	bs.bitIndex = 0
	return nil
}

func ReadAllBits(source BitSource) ([]int, error) {
	source.Reset()
	bits := make([]int, 0, source.Len())
	for {
		bit, err := source.NextBit()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		bits = append(bits, bit)
	}
	return bits, nil
}

func BitsToBytes(bits []int) []byte {
	bytes := make([]byte, (len(bits)+7)/8)
	for i, bit := range bits {
		byteIdx := i / 8
		bitIdx := 7 - (i % 8)
		if bit == 1 {
			bytes[byteIdx] |= 1 << uint(bitIdx)
		}
	}
	return bytes
}

func ParseBitString(s string) ([]int, error) {
	s = strings.TrimSpace(s)
	bits := make([]int, 0, len(s))
	for _, c := range s {
		if c == '0' {
			bits = append(bits, 0)
		} else if c == '1' {
			bits = append(bits, 1)
		} else if c == ' ' || c == '\t' || c == '\n' || c == '\r' {
			continue
		} else {
			return nil, fmt.Errorf("invalid character in bit string: %c", c)
		}
	}
	return bits, nil
}
