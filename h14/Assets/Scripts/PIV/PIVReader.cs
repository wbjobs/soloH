using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace FlowVisualization.PIV
{
    public enum PIVFormat
    {
        Unknown,
        VC7,
        DAT,
        TECPLOT,
        CSV,
        ImagePair
    }

    public struct PIVVector
    {
        public Vector3 Position;
        public Vector3 Velocity;
        public float Correlation;
        public float SNR;
        public bool IsValid;
    }

    public class PIVData
    {
        public string FilePath;
        public PIVFormat Format;
        public int GridSizeX;
        public int GridSizeY;
        public int GridSizeZ;
        public float DeltaT;
        public float PixelSize;
        public float Magnification;
        public Vector3 MinBounds;
        public Vector3 MaxBounds;
        public List<PIVVector> Vectors;
        public double Timestamp;

        public PIVData()
        {
            Vectors = new List<PIVVector>();
        }
    }

    public class PIVReader
    {
        private readonly NumberFormatInfo _numberFormat = new NumberFormatInfo { NumberDecimalSeparator = "." };

        public PIVData ReadFile(string filePath)
        {
            if (!File.Exists(filePath))
            {
                throw new FileNotFoundException($"PIV file not found: {filePath}");
            }

            PIVFormat format = DetectFormat(filePath);
            PIVData data = new PIVData
            {
                FilePath = filePath,
                Format = format
            };

            switch (format)
            {
                case PIVFormat.VC7:
                    ReadVC7(data, filePath);
                    break;
                case PIVFormat.DAT:
                    ReadDAT(data, filePath);
                    break;
                case PIVFormat.TECPLOT:
                    ReadTecplot(data, filePath);
                    break;
                case PIVFormat.CSV:
                    ReadCSV(data, filePath);
                    break;
                default:
                    throw new NotSupportedException($"Unsupported PIV format: {format}");
            }

            CalculateBounds(data);
            return data;
        }

        public PIVFormat DetectFormat(string filePath)
        {
            string ext = Path.GetExtension(filePath).ToLower();
            
            switch (ext)
            {
                case ".vc7":
                    return PIVFormat.VC7;
                case ".dat":
                    return PIVFormat.DAT;
                case ".tec":
                case ".plt":
                    return PIVFormat.TECPLOT;
                case ".csv":
                    return PIVFormat.CSV;
                case ".tif":
                case ".tiff":
                case ".bmp":
                case ".png":
                    return PIVFormat.ImagePair;
                default:
                    using (var reader = new StreamReader(filePath))
                    {
                        string header = reader.ReadLine();
                        if (header != null)
                        {
                            if (header.StartsWith("TITLE") || header.StartsWith("VARIABLES"))
                                return PIVFormat.TECPLOT;
                            if (header.Contains(",") && (header.Contains("x") || header.Contains("X")))
                                return PIVFormat.CSV;
                        }
                    }
                    return PIVFormat.Unknown;
            }
        }

        private void ReadVC7(PIVData data, string filePath)
        {
            using (var stream = File.OpenRead(filePath))
            using (var reader = new BinaryReader(stream))
            {
                byte[] header = reader.ReadBytes(512);
                
                float version = reader.ReadSingle();
                int numVectors = reader.ReadInt32();
                data.GridSizeX = reader.ReadInt32();
                data.GridSizeY = reader.ReadInt32();
                data.GridSizeZ = Math.Max(1, reader.ReadInt32());
                data.DeltaT = reader.ReadSingle();
                data.PixelSize = reader.ReadSingle();
                data.Magnification = reader.ReadSingle();

                for (int i = 0; i < numVectors; i++)
                {
                    PIVVector vec = new PIVVector
                    {
                        Position = new Vector3(
                            reader.ReadSingle(),
                            reader.ReadSingle(),
                            reader.ReadSingle()
                        ),
                        Velocity = new Vector3(
                            reader.ReadSingle(),
                            reader.ReadSingle(),
                            reader.ReadSingle()
                        ),
                        Correlation = reader.ReadSingle(),
                        SNR = reader.ReadSingle(),
                        IsValid = reader.ReadByte() == 1
                    };
                    data.Vectors.Add(vec);
                }
            }
        }

        private void ReadDAT(PIVData data, string filePath)
        {
            string[] lines = File.ReadAllLines(filePath);
            int lineIndex = 0;

            while (lineIndex < lines.Length && (lines[lineIndex].StartsWith("#") || 
                   string.IsNullOrWhiteSpace(lines[lineIndex]) || 
                   lines[lineIndex].StartsWith("x") || 
                   lines[lineIndex].StartsWith("X")))
            {
                if (lines[lineIndex].StartsWith("#"))
                {
                    ParseDATHeader(data, lines[lineIndex]);
                }
                lineIndex++;
            }

            int expectedCount = (lines.Length - lineIndex);
            data.Vectors.Capacity = expectedCount;

            for (int i = lineIndex; i < lines.Length; i++)
            {
                if (string.IsNullOrWhiteSpace(lines[i])) continue;

                string[] parts = lines[i].Split(new[] { ' ', '\t', ',' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length < 4) continue;

                try
                {
                    PIVVector vec = new PIVVector
                    {
                        Position = new Vector3(
                            ParseFloat(parts[0]),
                            ParseFloat(parts[1]),
                            parts.Length > 5 ? ParseFloat(parts[2]) : 0f
                        ),
                        Velocity = new Vector3(
                            ParseFloat(parts[2]),
                            ParseFloat(parts[3]),
                            parts.Length > 6 ? ParseFloat(parts[4]) : 0f
                        ),
                        Correlation = parts.Length > 7 ? ParseFloat(parts[5]) : 1f,
                        SNR = parts.Length > 8 ? ParseFloat(parts[6]) : 1f,
                        IsValid = true
                    };
                    data.Vectors.Add(vec);
                }
                catch (FormatException)
                {
                    continue;
                }
            }

            int totalVectors = data.Vectors.Count;
            int sqrt = (int)Math.Sqrt(totalVectors);
            if (sqrt * sqrt == totalVectors)
            {
                data.GridSizeX = sqrt;
                data.GridSizeY = sqrt;
                data.GridSizeZ = 1;
            }
            else
            {
                HashSet<float> xSet = new HashSet<float>();
                HashSet<float> ySet = new HashSet<float>();
                foreach (var v in data.Vectors)
                {
                    xSet.Add(v.Position.x);
                    ySet.Add(v.Position.y);
                }
                data.GridSizeX = xSet.Count;
                data.GridSizeY = ySet.Count;
                data.GridSizeZ = 1;
            }
        }

        private void ParseDATHeader(PIVData data, string headerLine)
        {
            string lower = headerLine.ToLower();
            if (lower.Contains("dt") || lower.Contains("delta"))
            {
                string[] parts = headerLine.Split(new[] { ' ', '\t', '=' }, StringSplitOptions.RemoveEmptyEntries);
                for (int i = 0; i < parts.Length; i++)
                {
                    if ((parts[i] == "dt" || parts[i] == "delta_t" || parts[i] == "delta") && i + 1 < parts.Length)
                    {
                        float.TryParse(parts[i + 1], NumberStyles.Float, _numberFormat, out data.DeltaT);
                    }
                }
            }
        }

        private void ReadTecplot(PIVData data, string filePath)
        {
            string[] lines = File.ReadAllLines(filePath);
            int lineIndex = 0;
            List<string> variables = new List<string>();
            Dictionary<string, int> varIndices = new Dictionary<string, int>();

            while (lineIndex < lines.Length)
            {
                string line = lines[lineIndex].Trim();
                if (line.StartsWith("VARIABLES"))
                {
                    int eq = line.IndexOf('=');
                    if (eq >= 0)
                    {
                        string varsStr = line.Substring(eq + 1).Trim();
                        string[] vars = varsStr.Split(new[] { '"', ',' }, StringSplitOptions.RemoveEmptyEntries);
                        foreach (var v in vars)
                        {
                            if (!string.IsNullOrWhiteSpace(v))
                            {
                                variables.Add(v.Trim());
                            }
                        }
                    }
                }
                else if (line.StartsWith("ZONE"))
                {
                    string[] parts = line.Split(new[] { ',', '=' }, StringSplitOptions.RemoveEmptyEntries);
                    for (int i = 0; i < parts.Length; i++)
                    {
                        if (parts[i].Trim() == "I" && i + 1 < parts.Length)
                            int.TryParse(parts[i + 1].Trim(), out data.GridSizeX);
                        if (parts[i].Trim() == "J" && i + 1 < parts.Length)
                            int.TryParse(parts[i + 1].Trim(), out data.GridSizeY);
                        if (parts[i].Trim() == "K" && i + 1 < parts.Length)
                            int.TryParse(parts[i + 1].Trim(), out data.GridSizeZ);
                    }
                }
                else if (char.IsDigit(line[0]) || line[0] == '-' || line[0] == '.')
                {
                    break;
                }
                lineIndex++;
            }

            for (int i = 0; i < variables.Count; i++)
            {
                varIndices[variables[i].ToLower()] = i;
            }

            int xIdx = varIndices.ContainsKey("x") ? varIndices["x"] : 0;
            int yIdx = varIndices.ContainsKey("y") ? varIndices["y"] : 1;
            int zIdx = varIndices.ContainsKey("z") ? varIndices["z"] : -1;
            int uIdx = varIndices.ContainsKey("u") ? varIndices["u"] : (varIndices.ContainsKey("vx") ? varIndices["vx"] : 2);
            int vIdx = varIndices.ContainsKey("v") ? varIndices["v"] : (varIndices.ContainsKey("vy") ? varIndices["vy"] : 3);
            int wIdx = varIndices.ContainsKey("w") ? varIndices["w"] : (varIndices.ContainsKey("vz") ? varIndices["vz"] : -1);

            data.Vectors.Capacity = data.GridSizeX * data.GridSizeY * Math.Max(1, data.GridSizeZ);

            for (int i = lineIndex; i < lines.Length; i++)
            {
                if (string.IsNullOrWhiteSpace(lines[i])) continue;
                if (lines[i].StartsWith("ZONE")) continue;

                string[] parts = lines[i].Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length < 4) continue;

                try
                {
                    PIVVector vec = new PIVVector
                    {
                        Position = new Vector3(
                            ParseFloat(parts[xIdx]),
                            ParseFloat(parts[yIdx]),
                            zIdx >= 0 && zIdx < parts.Length ? ParseFloat(parts[zIdx]) : 0f
                        ),
                        Velocity = new Vector3(
                            ParseFloat(parts[uIdx]),
                            ParseFloat(parts[vIdx]),
                            wIdx >= 0 && wIdx < parts.Length ? ParseFloat(parts[wIdx]) : 0f
                        ),
                        Correlation = 1f,
                        SNR = 1f,
                        IsValid = true
                    };
                    data.Vectors.Add(vec);
                }
                catch (FormatException)
                {
                    continue;
                }
            }
        }

        private void ReadCSV(PIVData data, string filePath)
        {
            string[] lines = File.ReadAllLines(filePath);
            if (lines.Length < 2) return;

            string[] headers = lines[0].Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            Dictionary<string, int> colIndices = new Dictionary<string, int>();
            
            for (int i = 0; i < headers.Length; i++)
            {
                colIndices[headers[i].Trim().ToLower()] = i;
            }

            int xIdx = colIndices.ContainsKey("x") ? colIndices["x"] : 0;
            int yIdx = colIndices.ContainsKey("y") ? colIndices["y"] : 1;
            int zIdx = colIndices.ContainsKey("z") ? colIndices["z"] : -1;
            int uIdx = colIndices.ContainsKey("u") ? colIndices["u"] : (colIndices.ContainsKey("vx") ? colIndices["vx"] : 2);
            int vIdx = colIndices.ContainsKey("v") ? colIndices["v"] : (colIndices.ContainsKey("vy") ? colIndices["vy"] : 3);
            int wIdx = colIndices.ContainsKey("w") ? colIndices["w"] : (colIndices.ContainsKey("vz") ? colIndices["vz"] : -1);

            data.Vectors.Capacity = lines.Length - 1;

            for (int i = 1; i < lines.Length; i++)
            {
                if (string.IsNullOrWhiteSpace(lines[i])) continue;

                string[] parts = lines[i].Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length < 4) continue;

                try
                {
                    PIVVector vec = new PIVVector
                    {
                        Position = new Vector3(
                            ParseFloat(parts[xIdx]),
                            ParseFloat(parts[yIdx]),
                            zIdx >= 0 && zIdx < parts.Length ? ParseFloat(parts[zIdx]) : 0f
                        ),
                        Velocity = new Vector3(
                            ParseFloat(parts[uIdx]),
                            ParseFloat(parts[vIdx]),
                            wIdx >= 0 && wIdx < parts.Length ? ParseFloat(parts[wIdx]) : 0f
                        ),
                        Correlation = colIndices.ContainsKey("correlation") ? ParseFloat(parts[colIndices["correlation"]]) : 1f,
                        SNR = colIndices.ContainsKey("snr") ? ParseFloat(parts[colIndices["snr"]]) : 1f,
                        IsValid = true
                    };
                    data.Vectors.Add(vec);
                }
                catch (FormatException)
                {
                    continue;
                }
            }

            HashSet<float> xSet = new HashSet<float>();
            HashSet<float> ySet = new HashSet<float>();
            foreach (var v in data.Vectors)
            {
                xSet.Add(v.Position.x);
                ySet.Add(v.Position.y);
            }
            data.GridSizeX = xSet.Count;
            data.GridSizeY = ySet.Count;
            data.GridSizeZ = 1;
        }

        private float ParseFloat(string s)
        {
            return float.Parse(s.Trim(), NumberStyles.Float, _numberFormat);
        }

        private void CalculateBounds(PIVData data)
        {
            if (data.Vectors.Count == 0) return;

            Vector3 min = data.Vectors[0].Position;
            Vector3 max = data.Vectors[0].Position;

            foreach (var vec in data.Vectors)
            {
                min = Vector3.Min(min, vec.Position);
                max = Vector3.Max(max, vec.Position);
            }

            data.MinBounds = min;
            data.MaxBounds = max;
        }
    }
}
