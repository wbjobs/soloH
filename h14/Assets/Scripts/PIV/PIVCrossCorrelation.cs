using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;

namespace FlowVisualization.PIV
{
    public enum CorrelationMethod
    {
        FFT,
        Direct,
        MultiPass
    }

    public enum InterpolationMethod
    {
        Gaussian,
        Parabolic,
        Centroid
    }

    public class PIVCrossCorrelation
    {
        public CorrelationMethod Method = CorrelationMethod.MultiPass;
        public InterpolationMethod SubPixelMethod = InterpolationMethod.Gaussian;
        public int InterrogationWindowSize = 32;
        public int SearchWindowSize = 64;
        public int Overlap = 16;
        public int NumPasses = 3;
        public float CorrelationThreshold = 0.1f;
        public float SNThreshold = 1.5f;

        private struct CorrelationPeak
        {
            public int X;
            public int Y;
            public float Value;
            public float SubPixelX;
            public float SubPixelY;
        }

        public PIVData ProcessImagePair(Texture2D image1, Texture2D image2, float deltaT, float pixelSize, float magnification = 1.0f)
        {
            if (image1 == null || image2 == null)
                throw new ArgumentNullException("Images cannot be null");

            if (image1.width != image2.width || image1.height != image2.height)
                throw new ArgumentException("Images must have the same dimensions");

            float[,] img1 = TextureToGrayscale(image1);
            float[,] img2 = TextureToGrayscale(image2);

            PIVData data = new PIVData
            {
                Format = PIVFormat.ImagePair,
                DeltaT = deltaT,
                PixelSize = pixelSize,
                Magnification = magnification
            };

            int width = image1.width;
            int height = image1.height;

            int step = InterrogationWindowSize - Overlap;
            data.GridSizeX = (width - InterrogationWindowSize) / step + 1;
            data.GridSizeY = (height - InterrogationWindowSize) / step + 1;
            data.GridSizeZ = 1;

            int totalVectors = data.GridSizeX * data.GridSizeY;
            data.Vectors.Capacity = totalVectors;

            float[,] displacementFieldX = new float[data.GridSizeX, data.GridSizeY];
            float[,] displacementFieldY = new float[data.GridSizeX, data.GridSizeY];
            float[,] correlationField = new float[data.GridSizeX, data.GridSizeY];
            float[,] snrField = new float[data.GridSizeX, data.GridSizeY];
            bool[,] validField = new bool[data.GridSizeX, data.GridSizeY];

            int currentWindow = InterrogationWindowSize;
            int currentSearch = SearchWindowSize;

            for (int pass = 0; pass < NumPasses; pass++)
            {
                if (pass > 0)
                {
                    currentWindow = Math.Max(8, currentWindow / 2);
                    currentSearch = Math.Max(16, currentSearch / 2);
                    step = currentWindow - Math.Max(4, Overlap / 2);
                }

                Parallel.For(0, data.GridSizeY, y =>
                {
                    for (int x = 0; x < data.GridSizeX; x++)
                    {
                        int ix = x * step;
                        int iy = y * step;

                        float dispX = 0, dispY = 0;
                        float correlation = 0;
                        float snr = 0;
                        bool valid = false;

                        if (ix + currentWindow <= width && iy + currentWindow <= height)
                        {
                            float[,] window1 = GetWindow(img1, ix, iy, currentWindow, currentWindow);
                            
                            int searchX = Math.Max(0, ix - (currentSearch - currentWindow) / 2);
                            int searchY = Math.Max(0, iy - (currentSearch - currentWindow) / 2);
                            int searchW = Math.Min(currentSearch, width - searchX);
                            int searchH = Math.Min(currentSearch, height - searchY);
                            
                            float[,] window2 = GetWindow(img2, searchX, searchY, searchW, searchH);

                            if (pass > 0)
                            {
                                float prevDispX = displacementFieldX[x, y];
                                float prevDispY = displacementFieldY[x, y];
                                float[,] shiftedWindow2 = ShiftWindow(window2, -prevDispX, -prevDispY);
                                window2 = shiftedWindow2;
                            }

                            CorrelationPeak peak;
                            if (Method == CorrelationMethod.Direct)
                                peak = ComputeDirectCorrelation(window1, window2);
                            else
                                peak = ComputeFFTCorrelation(window1, window2);

                            dispX = peak.SubPixelX;
                            dispY = peak.SubPixelY;
                            correlation = peak.Value;

                            float secondPeak = FindSecondPeak(window1, window2, peak);
                            snr = secondPeak > 0 ? correlation / secondPeak : float.MaxValue;

                            valid = correlation > CorrelationThreshold && snr > SNThreshold &&
                                    Math.Abs(dispX) < currentSearch / 2 && Math.Abs(dispY) < currentSearch / 2;
                        }

                        displacementFieldX[x, y] = dispX;
                        displacementFieldY[x, y] = dispY;
                        correlationField[x, y] = correlation;
                        snrField[x, y] = snr;
                        validField[x, y] = valid;
                    }
                });
            }

            PostProcessDisplacementField(displacementFieldX, displacementFieldY, validField, data.GridSizeX, data.GridSizeY);

            float dx = (width * pixelSize / magnification) / data.GridSizeX;
            float dy = (height * pixelSize / magnification) / data.GridSizeY;

            for (int y = 0; y < data.GridSizeY; y++)
            {
                for (int x = 0; x < data.GridSizeX; x++)
                {
                    float posX = x * dx;
                    float posY = y * dy;
                    
                    float velX = (displacementFieldX[x, y] * pixelSize / magnification) / deltaT;
                    float velY = (displacementFieldY[x, y] * pixelSize / magnification) / deltaT;

                    data.Vectors.Add(new PIVVector
                    {
                        Position = new Vector3(posX, posY, 0),
                        Velocity = new Vector3(velX, velY, 0),
                        Correlation = correlationField[x, y],
                        SNR = snrField[x, y],
                        IsValid = validField[x, y]
                    });
                }
            }

            data.MinBounds = new Vector3(0, 0, 0);
            data.MaxBounds = new Vector3(width * pixelSize / magnification, height * pixelSize / magnification, 0);

            return data;
        }

        private float[,] TextureToGrayscale(Texture2D texture)
        {
            int width = texture.width;
            int height = texture.height;
            float[,] result = new float[width, height];

            Color32[] pixels = texture.GetPixels32();
            
            Parallel.For(0, height, y =>
            {
                for (int x = 0; x < width; x++)
                {
                    int idx = y * width + x;
                    Color32 c = pixels[idx];
                    result[x, y] = (c.r * 0.299f + c.g * 0.587f + c.b * 0.114f) / 255f;
                }
            });

            return result;
        }

        private float[,] GetWindow(float[,] image, int x, int y, int width, int height)
        {
            float[,] window = new float[width, height];
            int imgWidth = image.GetLength(0);
            int imgHeight = image.GetLength(1);

            for (int j = 0; j < height; j++)
            {
                for (int i = 0; i < width; i++)
                {
                    int xi = x + i;
                    int yj = y + j;
                    if (xi >= 0 && xi < imgWidth && yj >= 0 && yj < imgHeight)
                        window[i, j] = image[xi, yj];
                    else
                        window[i, j] = 0;
                }
            }

            ApplyWindowFunction(window);
            return window;
        }

        private void ApplyWindowFunction(float[,] window)
        {
            int width = window.GetLength(0);
            int height = window.GetLength(1);

            for (int j = 0; j < height; j++)
            {
                for (int i = 0; i < width; i++)
                {
                    float wx = 0.5f * (1 - Mathf.Cos(2 * Mathf.PI * i / (width - 1)));
                    float wy = 0.5f * (1 - Mathf.Cos(2 * Mathf.PI * j / (height - 1)));
                    window[i, j] *= wx * wy;
                }
            }
        }

        private CorrelationPeak ComputeDirectCorrelation(float[,] window1, float[,] window2)
        {
            int w1 = window1.GetLength(0);
            int h1 = window1.GetLength(1);
            int w2 = window2.GetLength(0);
            int h2 = window2.GetLength(1);

            int maxDx = w2 - w1;
            int maxDy = h2 - h1;

            float maxCorr = -float.MaxValue;
            int peakX = 0, peakY = 0;

            float mean1 = Mean(window1);
            float mean2 = Mean(window2);
            float var1 = Variance(window1, mean1);
            float var2 = Variance(window2, mean2);

            Parallel.For(0, maxDy + 1, dy =>
            {
                float localMax = -float.MaxValue;
                int localPeakX = 0;

                for (int dx = 0; dx <= maxDx; dx++)
                {
                    float corr = 0;
                    for (int j = 0; j < h1; j++)
                    {
                        for (int i = 0; i < w1; i++)
                        {
                            float a = window1[i, j] - mean1;
                            float b = window2[i + dx, j + dy] - mean2;
                            corr += a * b;
                        }
                    }
                    corr /= Mathf.Sqrt(var1 * var2);

                    if (corr > localMax)
                    {
                        localMax = corr;
                        localPeakX = dx;
                    }
                }

                lock (this)
                {
                    if (localMax > maxCorr)
                    {
                        maxCorr = localMax;
                        peakX = localPeakX;
                        peakY = dy;
                    }
                }
            });

            CorrelationPeak peak = new CorrelationPeak
            {
                X = peakX,
                Y = peakY,
                Value = maxCorr
            };

            ComputeSubPixelPeak(window1, window2, ref peak);
            return peak;
        }

        private CorrelationPeak ComputeFFTCorrelation(float[,] window1, float[,] window2)
        {
            int w1 = window1.GetLength(0);
            int h1 = window1.GetLength(1);
            int w2 = window2.GetLength(0);
            int h2 = window2.GetLength(1);

            int fftW = 1;
            while (fftW < w1 + w2 - 1) fftW <<= 1;
            int fftH = 1;
            while (fftH < h1 + h2 - 1) fftH <<= 1;

            Complex[,] fft1 = FFT2D(ToComplex(window1, fftW, fftH), false);
            Complex[,] fft2 = FFT2D(ToComplex(window2, fftW, fftH), false);

            Complex[,] corr = new Complex[fftW, fftH];
            for (int j = 0; j < fftH; j++)
            {
                for (int i = 0; i < fftW; i++)
                {
                    corr[i, j] = fft1[i, j] * Complex.Conjugate(fft2[i, j]);
                }
            }

            corr = FFT2D(corr, true);

            float maxCorr = -float.MaxValue;
            int peakX = 0, peakY = 0;
            int maxDx = w2 - w1;
            int maxDy = h2 - h1;

            for (int j = 0; j <= maxDy; j++)
            {
                for (int i = 0; i <= maxDx; i++)
                {
                    float c = corr[i, j].Magnitude;
                    if (c > maxCorr)
                    {
                        maxCorr = c;
                        peakX = i;
                        peakY = j;
                    }
                }
            }

            float maxVal = 1e-10f;
            for (int j = 0; j < fftH; j++)
                for (int i = 0; i < fftW; i++)
                    maxVal = Mathf.Max(maxVal, corr[i, j].Magnitude);
            maxCorr /= maxVal;

            CorrelationPeak peak = new CorrelationPeak
            {
                X = peakX,
                Y = peakY,
                Value = maxCorr
            };

            ComputeSubPixelPeak(window1, window2, ref peak);
            return peak;
        }

        private void ComputeSubPixelPeak(float[,] window1, float[,] window2, ref CorrelationPeak peak)
        {
            int w1 = window1.GetLength(0);
            int h1 = window1.GetLength(1);

            float[,] neighborhood = new float[3, 3];
            
            for (int dy = -1; dy <= 1; dy++)
            {
                for (int dx = -1; dx <= 1; dx++)
                {
                    int px = peak.X + dx;
                    int py = peak.Y + dy;
                    
                    if (px >= 0 && py >= 0 && px + w1 <= window2.GetLength(0) && py + h1 <= window2.GetLength(1))
                    {
                        neighborhood[dx + 1, dy + 1] = ComputeCorrelationAtOffset(window1, window2, px, py);
                    }
                    else
                    {
                        neighborhood[dx + 1, dy + 1] = -1;
                    }
                }
            }

            if (SubPixelMethod == InterpolationMethod.Gaussian)
            {
                GaussianPeak(neighborhood, out peak.SubPixelX, out peak.SubPixelY);
            }
            else if (SubPixelMethod == InterpolationMethod.Parabolic)
            {
                ParabolicPeak(neighborhood, out peak.SubPixelX, out peak.SubPixelY);
            }
            else
            {
                CentroidPeak(neighborhood, out peak.SubPixelX, out peak.SubPixelY);
            }

            peak.SubPixelX += peak.X - (window2.GetLength(0) - window1.GetLength(0)) / 2f;
            peak.SubPixelY += peak.Y - (window2.GetLength(1) - window1.GetLength(1)) / 2f;
        }

        private float ComputeCorrelationAtOffset(float[,] window1, float[,] window2, int dx, int dy)
        {
            int w = window1.GetLength(0);
            int h = window1.GetLength(1);
            float mean1 = Mean(window1);
            float mean2 = Mean(window2);

            float corr = 0;
            for (int j = 0; j < h; j++)
                for (int i = 0; i < w; i++)
                    corr += (window1[i, j] - mean1) * (window2[i + dx, j + dy] - mean2);
            
            return corr;
        }

        private void GaussianPeak(float[,] n, out float sx, out float sy)
        {
            float c00 = Mathf.Log(Mathf.Max(n[1, 1], 1e-10f));
            float c10 = Mathf.Log(Mathf.Max(n[2, 1], 1e-10f));
            float cm10 = Mathf.Log(Mathf.Max(n[0, 1], 1e-10f));
            float c01 = Mathf.Log(Mathf.Max(n[1, 2], 1e-10f));
            float c0m1 = Mathf.Log(Mathf.Max(n[1, 0], 1e-10f));

            sx = (cm10 - c10) / (2 * (cm10 - 2 * c00 + c10));
            sy = (c0m1 - c01) / (2 * (c0m1 - 2 * c00 + c01));

            sx = Mathf.Clamp(sx, -0.5f, 0.5f);
            sy = Mathf.Clamp(sy, -0.5f, 0.5f);
        }

        private void ParabolicPeak(float[,] n, out float sx, out float sy)
        {
            float c00 = n[1, 1];
            float c10 = n[2, 1];
            float cm10 = n[0, 1];
            float c01 = n[1, 2];
            float c0m1 = n[1, 0];

            sx = (cm10 - c10) / (2 * (cm10 - 2 * c00 + c10));
            sy = (c0m1 - c01) / (2 * (c0m1 - 2 * c00 + c01));

            sx = Mathf.Clamp(sx, -0.5f, 0.5f);
            sy = Mathf.Clamp(sy, -0.5f, 0.5f);
        }

        private void CentroidPeak(float[,] n, out float sx, out float sy)
        {
            float sum = 0, sumX = 0, sumY = 0;
            for (int dy = -1; dy <= 1; dy++)
            {
                for (int dx = -1; dx <= 1; dx++)
                {
                    float v = Mathf.Max(n[dx + 1, dy + 1], 0);
                    sum += v;
                    sumX += dx * v;
                    sumY += dy * v;
                }
            }

            sx = sum > 0 ? sumX / sum : 0;
            sy = sum > 0 ? sumY / sum : 0;
        }

        private float FindSecondPeak(float[,] window1, float[,] window2, CorrelationPeak mainPeak)
        {
            int w1 = window1.GetLength(0);
            int h1 = window1.GetLength(1);
            int w2 = window2.GetLength(0);
            int h2 = window2.GetLength(1);

            float maxCorr = -float.MaxValue;
            int exclusionRadius = 3;

            for (int dy = 0; dy <= h2 - h1; dy++)
            {
                for (int dx = 0; dx <= w2 - w1; dx++)
                {
                    if (Math.Abs(dx - mainPeak.X) < exclusionRadius && Math.Abs(dy - mainPeak.Y) < exclusionRadius)
                        continue;

                    float corr = ComputeCorrelationAtOffset(window1, window2, dx, dy);
                    if (corr > maxCorr) maxCorr = corr;
                }
            }

            return maxCorr;
        }

        private float[,] ShiftWindow(float[,] window, float dx, float dy)
        {
            int w = window.GetLength(0);
            int h = window.GetLength(1);
            float[,] result = new float[w, h];

            int idx = (int)Math.Floor(dx);
            int idy = (int)Math.Floor(dy);
            float fx = dx - idx;
            float fy = dy - idy;

            for (int j = 0; j < h; j++)
            {
                for (int i = 0; i < w; i++)
                {
                    int x0 = i - idx;
                    int y0 = j - idy;
                    int x1 = x0 + 1;
                    int y1 = y0 + 1;

                    float v00 = GetBounded(window, x0, y0);
                    float v10 = GetBounded(window, x1, y0);
                    float v01 = GetBounded(window, x0, y1);
                    float v11 = GetBounded(window, x1, y1);

                    result[i, j] = v00 * (1 - fx) * (1 - fy) +
                                   v10 * fx * (1 - fy) +
                                   v01 * (1 - fx) * fy +
                                   v11 * fx * fy;
                }
            }

            return result;
        }

        private float GetBounded(float[,] array, int x, int y)
        {
            int w = array.GetLength(0);
            int h = array.GetLength(1);
            x = Mathf.Clamp(x, 0, w - 1);
            y = Mathf.Clamp(y, 0, h - 1);
            return array[x, y];
        }

        private void PostProcessDisplacementField(float[,] dispX, float[,] dispY, bool[,] valid, int nx, int ny)
        {
            float[,] smoothedX = new float[nx, ny];
            float[,] smoothedY = new float[nx, ny];

            for (int y = 1; y < ny - 1; y++)
            {
                for (int x = 1; x < nx - 1; x++)
                {
                    if (!valid[x, y])
                    {
                        float sumX = 0, sumY = 0, count = 0;
                        for (int dy = -1; dy <= 1; dy++)
                        {
                            for (int dx = -1; dx <= 1; dx++)
                            {
                                if (valid[x + dx, y + dy])
                                {
                                    sumX += dispX[x + dx, y + dy];
                                    sumY += dispY[x + dx, y + dy];
                                    count++;
                                }
                            }
                        }
                        if (count > 0)
                        {
                            dispX[x, y] = sumX / count;
                            dispY[x, y] = sumY / count;
                            valid[x, y] = true;
                        }
                    }
                }
            }

            for (int pass = 0; pass < 2; pass++)
            {
                for (int y = 1; y < ny - 1; y++)
                {
                    for (int x = 1; x < nx - 1; x++)
                    {
                        float sumX = 0, sumY = 0, count = 0;
                        for (int dy = -1; dy <= 1; dy++)
                        {
                            for (int dx = -1; dx <= 1; dx++)
                            {
                                sumX += dispX[x + dx, y + dy];
                                sumY += dispY[x + dx, y + dy];
                                count++;
                            }
                        }
                        smoothedX[x, y] = sumX / count;
                        smoothedY[x, y] = sumY / count;
                    }
                }

                for (int y = 1; y < ny - 1; y++)
                {
                    for (int x = 1; x < nx - 1; x++)
                    {
                        dispX[x, y] = smoothedX[x, y];
                        dispY[x, y] = smoothedY[x, y];
                    }
                }
            }
        }

        private float Mean(float[,] array)
        {
            float sum = 0;
            int n = array.Length;
            for (int j = 0; j < array.GetLength(1); j++)
                for (int i = 0; i < array.GetLength(0); i++)
                    sum += array[i, j];
            return sum / n;
        }

        private float Variance(float[,] array, float mean)
        {
            float sum = 0;
            int n = array.Length;
            for (int j = 0; j < array.GetLength(1); j++)
                for (int i = 0; i < array.GetLength(0); i++)
                {
                    float d = array[i, j] - mean;
                    sum += d * d;
                }
            return sum / n;
        }

        private Complex[,] ToComplex(float[,] real, int padW, int padH)
        {
            Complex[,] result = new Complex[padW, padH];
            int w = real.GetLength(0);
            int h = real.GetLength(1);
            for (int j = 0; j < padH; j++)
                for (int i = 0; i < padW; i++)
                    result[i, j] = (i < w && j < h) ? new Complex(real[i, j], 0) : Complex.Zero;
            return result;
        }

        private Complex[,] FFT2D(Complex[,] data, bool inverse)
        {
            int w = data.GetLength(0);
            int h = data.GetLength(1);
            
            Complex[] row = new Complex[w];
            for (int y = 0; y < h; y++)
            {
                for (int x = 0; x < w; x++)
                    row[x] = data[x, y];
                row = FFT(row, inverse);
                for (int x = 0; x < w; x++)
                    data[x, y] = row[x];
            }

            Complex[] col = new Complex[h];
            for (int x = 0; x < w; x++)
            {
                for (int y = 0; y < h; y++)
                    col[y] = data[x, y];
                col = FFT(col, inverse);
                for (int y = 0; y < h; y++)
                    data[x, y] = col[y];
            }

            return data;
        }

        private Complex[] FFT(Complex[] data, bool inverse)
        {
            int n = data.Length;
            if (n <= 1) return data;

            Complex[] even = new Complex[n / 2];
            Complex[] odd = new Complex[n / 2];
            for (int i = 0; i < n / 2; i++)
            {
                even[i] = data[2 * i];
                odd[i] = data[2 * i + 1];
            }

            even = FFT(even, inverse);
            odd = FFT(odd, inverse);

            Complex[] result = new Complex[n];
            double angle = 2 * Math.PI / n * (inverse ? 1 : -1);
            for (int k = 0; k < n / 2; k++)
            {
                Complex t = Complex.FromPolarCoordinates(1, k * angle) * odd[k];
                result[k] = even[k] + t;
                result[k + n / 2] = even[k] - t;
            }

            if (inverse)
            {
                for (int i = 0; i < n; i++)
                    result[i] /= n;
            }

            return result;
        }

        private struct Complex
        {
            public float Real;
            public float Imaginary;

            public Complex(float real, float imaginary)
            {
                Real = real;
                Imaginary = imaginary;
            }

            public static Complex Zero => new Complex(0, 0);

            public float Magnitude => Mathf.Sqrt(Real * Real + Imaginary * Imaginary);

            public static Complex Conjugate(Complex c)
            {
                return new Complex(c.Real, -c.Imaginary);
            }

            public static Complex FromPolarCoordinates(float magnitude, double angle)
            {
                return new Complex(magnitude * (float)Math.Cos(angle), magnitude * (float)Math.Sin(angle));
            }

            public static Complex operator *(Complex a, Complex b)
            {
                return new Complex(
                    a.Real * b.Real - a.Imaginary * b.Imaginary,
                    a.Real * b.Imaginary + a.Imaginary * b.Real
                );
            }

            public static Complex operator +(Complex a, Complex b)
            {
                return new Complex(a.Real + b.Real, a.Imaginary + b.Imaginary);
            }

            public static Complex operator -(Complex a, Complex b)
            {
                return new Complex(a.Real - b.Real, a.Imaginary - b.Imaginary);
            }

            public static Complex operator /(Complex c, float f)
            {
                return new Complex(c.Real / f, c.Imaginary / f);
            }
        }
    }
}
