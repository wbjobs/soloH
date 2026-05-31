package utils

import (
	"math"
)

const (
	epsilon = 1e-12
)

func erf(x float64) float64 {
	return math.Erf(x)
}

func erfc(x float64) float64 {
	return math.Erfc(x)
}

func igamc(a, x float64) float64 {
	if x < 0 || a <= 0 {
		return 1.0
	}
	if x == 0 {
		return 1.0
	}
	if x < a+1 {
		return 1.0 - igamSeries(a, x)
	}
	return igamCF(a, x)
}

func igam(a, x float64) float64 {
	if x < 0 || a <= 0 {
		return 0.0
	}
	if x == 0 {
		return 0.0
	}
	if x < a+1 {
		return igamSeries(a, x)
	}
	return 1.0 - igamCF(a, x)
}

func igamSeries(a, x float64) float64 {
	ap := a
	total := 1.0 / a
	term := total
	for i := 0; i < 100; i++ {
		ap++
		term *= x / ap
		total += term
		if math.Abs(term) < math.Abs(total)*epsilon {
			break
		}
	}
	return total * math.Exp(-x + a*math.Log(x) - lgamma(a))
}

func igamCF(a, x float64) float64 {
	const itmax := 100
	eps := epsilon
	fpmin := 1e-300
	b := x + 1.0 - a
	c := 1.0 / fpmin
	d := 1.0 / b
	h := d
	for i := 1; i <= itmax; i++ {
		an := float64(-i) * (float64(i) - a)
		b += 2.0
		d = an*d + b
		if math.Abs(d) < fpmin {
			d = fpmin
		}
		c = b + an/c
		if math.Abs(c) < fpmin {
			c = fpmin
		}
		d = 1.0 / d
		delta := d * c
		h *= delta
		if math.Abs(delta-1.0) <= eps {
			break
		}
	}
	return h * math.Exp(-x + a*math.Log(x) - lgamma(a))
}

func lgamma(x float64) float64 {
	return math.Lgamma(x)
}

func gamma(x float64) float64 {
	return math.Gamma(x)
}

func normsf(z float64) float64 {
	return 0.5 * erfc(z / math.Sqrt(2))
}

func chi2PValue(chi2 float64, df int) float64 {
	if df <= 0 {
		return 1.0
	}
	return igamc(float64(df)/2.0, chi2/2.0)
}

func gammaPValue(a, x float64) float64 {
	return igamc(a, x)
}

func poissonPValue(x, lambda float64) float64 {
	if lambda <= 0 {
		return 1.0
	}
	return igamc(x, lambda)
}
