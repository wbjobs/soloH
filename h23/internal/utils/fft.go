package utils

import (
	"math"
)

type complex128s struct {
	r, i float64
}

func FFT(x []float64) []complex128s {
	n := len(x)
	if n == 0 {
		return nil
	}

	n2 := nextPowerOf2(n)
	data := make([]complex128s, n2)
	for i := 0; i < n; i++ {
		data[i].r = x[i]
		data[i].i = 0
	}
	for i := n; i < n2; i++ {
		data[i].r = 0
		data[i].i = 0
	}

	fftIterative(data)

	if n2 > n {
		return data[:n]
	}
	return data
}

func fftIterative(data []complex128s) {
	n := len(data)
	j := 0
	for i := 1; i < n; i++ {
		bit := n >> 1
		for ; j&bit != 0; bit >>= 1 {
			j &= ^bit
		}
		j |= bit

		if i < j {
			data[i], data[j] = data[j], data[i]
		}
	}

	for len := 2; len <= n; len <<= 1 {
		halfLen := len >> 1
		ang := 2 * math.Pi / float64(len)
		wr := math.Cos(ang)
		wi := -math.Sin(ang)

		for i := 0; i < n; i += len {
			cos := 1.0
			sin := 0.0
			for j := 0; j < halfLen; j++ {
				idx := i + j
				idx2 := idx + halfLen
				tr := cos*data[idx2].r - sin*data[idx2].i
				ti := cos*data[idx2].i + sin*data[idx2].r

				data[idx2].r = data[idx].r - tr
				data[idx2].i = data[idx].i - ti

				data[idx].r += tr
				data[idx].i += ti

				cos, sin = cos*wr - sin*wi, cos*wi + sin*wr
			}
		}
	}
}

func nextPowerOf2(n int) int {
	p := 1
	for p < n {
		p <<= 1
	}
	return p
}
