using System;
using System.IO;
using System.Text;
using UnityEngine;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.Geometry
{
    public class CadExporter
    {
        public bool ExportSTL(UnityEngine.Mesh mesh, string filePath, bool binary = true)
        {
            if (mesh == null) return false;

            try
            {
                if (binary)
                {
                    ExportSTLBinary(mesh, filePath);
                }
                else
                {
                    ExportSTLAscii(mesh, filePath);
                }
                return true;
            }
            catch (Exception e)
            {
                Debug.LogError($"STL export failed: {e.Message}");
                return false;
            }
        }

        private void ExportSTLAscii(UnityEngine.Mesh mesh, string filePath)
        {
            StringBuilder sb = new StringBuilder();
            sb.AppendLine($"solid {mesh.name}");

            Vector3[] vertices = mesh.vertices;
            int[] triangles = mesh.triangles;

            for (int i = 0; i < triangles.Length; i += 3)
            {
                Vector3 v0 = vertices[triangles[i]];
                Vector3 v1 = vertices[triangles[i + 1]];
                Vector3 v2 = vertices[triangles[i + 2]];

                Vector3 normal = Vector3.Cross(v1 - v0, v2 - v0).normalized;

                sb.AppendLine($"  facet normal {normal.x:e6} {normal.y:e6} {normal.z:e6}");
                sb.AppendLine("    outer loop");
                sb.AppendLine($"      vertex {v0.x:e6} {v0.y:e6} {v0.z:e6}");
                sb.AppendLine($"      vertex {v1.x:e6} {v1.y:e6} {v1.z:e6}");
                sb.AppendLine($"      vertex {v2.x:e6} {v2.y:e6} {v2.z:e6}");
                sb.AppendLine("    endloop");
                sb.AppendLine("  endfacet");
            }

            sb.AppendLine($"endsolid {mesh.name}");
            File.WriteAllText(filePath, sb.ToString());
        }

        private void ExportSTLBinary(UnityEngine.Mesh mesh, string filePath)
        {
            using (BinaryWriter writer = new BinaryWriter(File.Open(filePath, FileMode.Create)))
            {
                byte[] header = new byte[80];
                Encoding.ASCII.GetBytes($"Exported from SoleFrictionSim - {mesh.name}").CopyTo(header, 0);
                writer.Write(header);

                int[] triangles = mesh.triangles;
                Vector3[] vertices = mesh.vertices;

                uint numFaces = (uint)(triangles.Length / 3);
                writer.Write(numFaces);

                for (int i = 0; i < triangles.Length; i += 3)
                {
                    Vector3 v0 = vertices[triangles[i]];
                    Vector3 v1 = vertices[triangles[i + 1]];
                    Vector3 v2 = vertices[triangles[i + 2]];

                    Vector3 normal = Vector3.Cross(v1 - v0, v2 - v0).normalized;

                    writer.Write(normal.x);
                    writer.Write(normal.y);
                    writer.Write(normal.z);

                    writer.Write(v0.x);
                    writer.Write(v0.y);
                    writer.Write(v0.z);

                    writer.Write(v1.x);
                    writer.Write(v1.y);
                    writer.Write(v1.z);

                    writer.Write(v2.x);
                    writer.Write(v2.y);
                    writer.Write(v2.z);

                    ushort attributeByteCount = 0;
                    writer.Write(attributeByteCount);
                }
            }
        }

        public bool ExportHeightFieldSTL(float[,] heightField, string filePath,
            float widthMeters = 0.1f, float lengthMeters = 0.28f, float baseHeight = 0.005f, bool binary = true)
        {
            if (heightField == null) return false;

            Mesh mesh = HeightFieldToMesh(heightField, widthMeters, lengthMeters, baseHeight);
            return ExportSTL(mesh, filePath, binary);
        }

        public bool ExportDXF2D(float[,] heightField, string filePath,
            float widthMeters = 0.1f, float lengthMeters = 0.28f, int numContours = 10)
        {
            if (heightField == null) return false;

            try
            {
                int n = heightField.GetLength(0);
                int m = heightField.GetLength(1);

                float minH = float.MaxValue, maxH = float.MinValue;
                for (int i = 0; i < n; i++)
                    for (int j = 0; j < m; j++)
                    {
                        if (heightField[i, j] < minH) minH = heightField[i, j];
                        if (heightField[i, j] > maxH) maxH = heightField[i, j];
                    }

                StringBuilder sb = new StringBuilder();
                sb.AppendLine("0");
                sb.AppendLine("SECTION");
                sb.AppendLine("2");
                sb.AppendLine("HEADER");
                sb.AppendLine("9");
                sb.AppendLine("$ACADVER");
                sb.AppendLine("1");
                sb.AppendLine("AC1009");
                sb.AppendLine("9");
                sb.AppendLine("$INSUNITS");
                sb.AppendLine("70");
                sb.AppendLine("4");
                sb.AppendLine("0");
                sb.AppendLine("ENDSEC");
                sb.AppendLine("0");
                sb.AppendLine("SECTION");
                sb.AppendLine("2");
                sb.AppendLine("TABLES");
                sb.AppendLine("0");
                sb.AppendLine("TABLE");
                sb.AppendLine("2");
                sb.AppendLine("LAYER");
                sb.AppendLine("70");
                sb.AppendLine("7");

                for (int l = 0; l < numContours; l++)
                {
                    sb.AppendLine("0");
                    sb.AppendLine("LAYER");
                    sb.AppendLine("2");
                    sb.AppendLine($"CONTOUR_{l}");
                    sb.AppendLine("70");
                    sb.AppendLine("64");
                    sb.AppendLine("62");
                    sb.AppendLine($"{l + 1}");
                    sb.AppendLine("6");
                    sb.AppendLine("CONTINUOUS");
                }

                sb.AppendLine("0");
                sb.AppendLine("ENDTAB");
                sb.AppendLine("0");
                sb.AppendLine("ENDSEC");
                sb.AppendLine("0");
                sb.AppendLine("SECTION");
                sb.AppendLine("2");
                sb.AppendLine("ENTITIES");

                for (int l = 0; l < numContours; l++)
                {
                    float contourLevel = minH + (float)l / (numContours - 1) * (maxH - minH);
                    var contours = ExtractContours(heightField, contourLevel);

                    foreach (var contour in contours)
                    {
                        for (int p = 0; p < contour.Count - 1; p++)
                        {
                            sb.AppendLine("0");
                            sb.AppendLine("LINE");
                            sb.AppendLine("8");
                            sb.AppendLine($"CONTOUR_{l}");
                            sb.AppendLine("10");
                            sb.AppendLine($"{contour[p].x * widthMeters:0.0000}");
                            sb.AppendLine("20");
                            sb.AppendLine($"{contour[p].y * lengthMeters:0.0000}");
                            sb.AppendLine("11");
                            sb.AppendLine($"{contour[p + 1].x * widthMeters:0.0000}");
                            sb.AppendLine("21");
                            sb.AppendLine($"{contour[p + 1].y * lengthMeters:0.0000}");
                        }
                    }
                }

                sb.AppendLine("0");
                sb.AppendLine("ENDSEC");
                sb.AppendLine("0");
                sb.AppendLine("EOF");

                File.WriteAllText(filePath, sb.ToString());
                return true;
            }
            catch (Exception e)
            {
                Debug.LogError($"DXF export failed: {e.Message}");
                return false;
            }
        }

        public bool ExportOBJ(UnityEngine.Mesh mesh, string filePath)
        {
            if (mesh == null) return false;

            try
            {
                StringBuilder sb = new StringBuilder();
                sb.AppendLine($"# Exported from SoleFrictionSim");
                sb.AppendLine($"o {mesh.name}");

                Vector3[] vertices = mesh.vertices;
                Vector3[] normals = mesh.normals;
                Vector2[] uv = mesh.uv;
                int[] triangles = mesh.triangles;

                foreach (var v in vertices)
                {
                    sb.AppendLine($"v {v.x:0.000000} {v.y:0.000000} {v.z:0.000000}");
                }

                if (uv != null && uv.Length > 0)
                {
                    foreach (var t in uv)
                    {
                        sb.AppendLine($"vt {t.x:0.000000} {t.y:0.000000}");
                    }
                }

                if (normals != null && normals.Length > 0)
                {
                    foreach (var n in normals)
                    {
                        sb.AppendLine($"vn {n.x:0.000000} {n.y:0.000000} {n.z:0.000000}");
                    }
                }

                for (int i = 0; i < triangles.Length; i += 3)
                {
                    int i0 = triangles[i] + 1;
                    int i1 = triangles[i + 1] + 1;
                    int i2 = triangles[i + 2] + 1;

                    if (normals != null && normals.Length > 0 && uv != null && uv.Length > 0)
                    {
                        sb.AppendLine($"f {i0}/{i0}/{i0} {i1}/{i1}/{i1} {i2}/{i2}/{i2}");
                    }
                    else if (normals != null && normals.Length > 0)
                    {
                        sb.AppendLine($"f {i0}//{i0} {i1}//{i1} {i2}//{i2}");
                    }
                    else
                    {
                        sb.AppendLine($"f {i0} {i1} {i2}");
                    }
                }

                File.WriteAllText(filePath, sb.ToString());
                return true;
            }
            catch (Exception e)
            {
                Debug.LogError($"OBJ export failed: {e.Message}");
                return false;
            }
        }

        public bool ExportContactDataCSV(ContactResult result, string filePath)
        {
            if (result?.contactPressure == null) return false;

            try
            {
                StringBuilder sb = new StringBuilder();

                sb.AppendLine("# Sole Friction Simulation - Contact Data Export");
                sb.AppendLine($"# Export Date: {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
                sb.AppendLine($"# Resolution: {result.Resolution}x{result.Resolution}");
                sb.AppendLine($"# Max Pressure: {result.maxContactPressure:0.000} Pa");
                sb.AppendLine($"# Average Pressure: {result.averagePressure:0.000} Pa");
                sb.AppendLine($"# Contact Area Ratio: {result.contactAreaRatio:0.0000}");
                sb.AppendLine($"# Max Temperature: {result.maxTemperature:0.000} °C");
                sb.AppendLine($"# Max Wear Depth: {result.maxWearDepth * 1000:0.000} mm");
                sb.AppendLine($"# Predicted Life: {result.predictedLifeKm:0.000} km");
                sb.AppendLine();

                sb.AppendLine("=== Friction Curve ===");
                sb.AppendLine("Velocity(m/s),FrictionCoefficient");
                if (result.slipVelocities != null && result.frictionCoefficients != null)
                {
                    for (int i = 0; i < result.slipVelocities.Length; i++)
                    {
                        sb.AppendLine($"{result.slipVelocities[i]:0.000000},{result.frictionCoefficients[i]:0.000000}");
                    }
                }

                sb.AppendLine();
                sb.AppendLine("=== Contact Pressure Map (Pa) ===");
                int n = result.contactPressure.GetLength(0);
                int m = result.contactPressure.GetLength(1);

                sb.Append("Y/X,");
                for (int j = 0; j < m; j++)
                {
                    sb.Append($"{(float)j / m:0.000},");
                }
                sb.AppendLine();

                for (int i = 0; i < n; i++)
                {
                    sb.Append($"{(float)i / n:0.000},");
                    for (int j = 0; j < m; j++)
                    {
                        sb.Append($"{result.contactPressure[i, j]:0.000},");
                    }
                    sb.AppendLine();
                }

                if (result.temperatureField != null)
                {
                    sb.AppendLine();
                    sb.AppendLine("=== Temperature Field (°C) ===");
                    sb.Append("Y/X,");
                    for (int j = 0; j < m; j++)
                    {
                        sb.Append($"{(float)j / m:0.000},");
                    }
                    sb.AppendLine();

                    for (int i = 0; i < n; i++)
                    {
                        sb.Append($"{(float)i / n:0.000},");
                        for (int j = 0; j < m; j++)
                        {
                            sb.Append($"{result.temperatureField[i, j]:0.000},");
                        }
                        sb.AppendLine();
                    }
                }

                if (result.wearDepth != null)
                {
                    sb.AppendLine();
                    sb.AppendLine("=== Wear Depth (mm) ===");
                    sb.Append("Y/X,");
                    for (int j = 0; j < m; j++)
                    {
                        sb.Append($"{(float)j / m:0.000},");
                    }
                    sb.AppendLine();

                    for (int i = 0; i < n; i++)
                    {
                        sb.Append($"{(float)i / n:0.000},");
                        for (int j = 0; j < m; j++)
                        {
                            sb.Append($"{result.wearDepth[i, j] * 1000:0.000000},");
                        }
                        sb.AppendLine();
                    }
                }

                File.WriteAllText(filePath, sb.ToString());
                return true;
            }
            catch (Exception e)
            {
                Debug.LogError($"CSV export failed: {e.Message}");
                return false;
            }
        }

        private Mesh HeightFieldToMesh(float[,] heightField, float width, float length, float baseHeight)
        {
            int n = heightField.GetLength(0);
            int m = heightField.GetLength(1);

            Vector3[] vertices = new Vector3[(n + 1) * (m + 1) * 2];
            int[] triangles = new int[n * m * 6 * 2 + (n + m) * 6];

            int vertexIdx = 0;
            int triIdx = 0;

            for (int i = 0; i <= n; i++)
            {
                for (int j = 0; j <= m; j++)
                {
                    float x = (float)j / m * width - width / 2f;
                    float z = (float)i / n * length - length / 2f;
                    float h = baseHeight + heightField[Mathf.Min(i, n - 1), Mathf.Min(j, m - 1)];

                    vertices[vertexIdx++] = new Vector3(x, h, z);
                }
            }

            for (int i = 0; i <= n; i++)
            {
                for (int j = 0; j <= m; j++)
                {
                    float x = (float)j / m * width - width / 2f;
                    float z = (float)i / n * length - length / 2f;
                    vertices[vertexIdx++] = new Vector3(x, 0, z);
                }
            }

            int stride = m + 1;
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < m; j++)
                {
                    int a = i * stride + j;
                    int b = a + 1;
                    int c = a + stride;
                    int d = c + 1;

                    triangles[triIdx++] = a;
                    triangles[triIdx++] = c;
                    triangles[triIdx++] = b;
                    triangles[triIdx++] = b;
                    triangles[triIdx++] = c;
                    triangles[triIdx++] = d;

                    int a2 = a + (n + 1) * stride;
                    int b2 = b + (n + 1) * stride;
                    int c2 = c + (n + 1) * stride;
                    int d2 = d + (n + 1) * stride;

                    triangles[triIdx++] = a2;
                    triangles[triIdx++] = b2;
                    triangles[triIdx++] = c2;
                    triangles[triIdx++] = b2;
                    triangles[triIdx++] = d2;
                    triangles[triIdx++] = c2;
                }
            }

            Mesh mesh = new Mesh();
            mesh.name = "SolePattern_Export";
            mesh.vertices = vertices;
            mesh.triangles = triangles;
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();

            return mesh;
        }

        private System.Collections.Generic.List<System.Collections.Generic.List<Vector2>> ExtractContours(
            float[,] data, float threshold)
        {
            int n = data.GetLength(0);
            int m = data.GetLength(1);
            var contours = new System.Collections.Generic.List<System.Collections.Generic.List<Vector2>>();

            bool[,] visited = new bool[n, m];

            for (int i = 0; i < n - 1; i++)
            {
                for (int j = 0; j < m - 1; j++)
                {
                    if (visited[i, j]) continue;

                    if (data[i, j] >= threshold && data[i + 1, j] < threshold ||
                        data[i, j] < threshold && data[i + 1, j] >= threshold ||
                        data[i, j] >= threshold && data[i, j + 1] < threshold ||
                        data[i, j] < threshold && data[i, j + 1] >= threshold)
                    {
                        var contour = TraceContour(data, threshold, i, j, visited);
                        if (contour != null && contour.Count > 2)
                        {
                            contours.Add(contour);
                        }
                    }
                }
            }

            return contours;
        }

        private System.Collections.Generic.List<Vector2> TraceContour(
            float[,] data, float threshold, int startI, int startJ, bool[,] visited)
        {
            int n = data.GetLength(0);
            int m = data.GetLength(1);
            var contour = new System.Collections.Generic.List<Vector2>();

            int i = startI;
            int j = startJ;

            while (i >= 0 && i < n && j >= 0 && j < m && !visited[i, j])
            {
                visited[i, j] = true;

                float h = data[i, j];
                float hRight = j < m - 1 ? data[i, j + 1] : h;
                float hDown = i < n - 1 ? data[i + 1, j] : h;

                if (h >= threshold && hRight < threshold)
                {
                    float t = (threshold - h) / (hRight - h);
                    contour.Add(new Vector2((float)(j + t) / m, (float)i / n));
                }
                if (h < threshold && hRight >= threshold)
                {
                    float t = (threshold - h) / (hRight - h);
                    contour.Add(new Vector2((float)(j + t) / m, (float)i / n));
                }
                if (h >= threshold && hDown < threshold)
                {
                    float t = (threshold - h) / (hDown - h);
                    contour.Add(new Vector2((float)j / m, (float)(i + t) / n));
                }
                if (h < threshold && hDown >= threshold)
                {
                    float t = (threshold - h) / (hDown - h);
                    contour.Add(new Vector2((float)j / m, (float)(i + t) / n));
                }

                bool foundNext = false;
                int[] di = { 0, 1, 0, -1 };
                int[] dj = { 1, 0, -1, 0 };

                for (int d = 0; d < 4; d++)
                {
                    int ni = i + di[d];
                    int nj = j + dj[d];

                    if (ni >= 0 && ni < n && nj >= 0 && nj < m && !visited[ni, nj])
                    {
                        float nh = data[ni, nj];
                        if ((h >= threshold && nh < threshold) || (h < threshold && nh >= threshold))
                        {
                            i = ni;
                            j = nj;
                            foundNext = true;
                            break;
                        }
                    }
                }

                if (!foundNext) break;
            }

            return contour;
        }

        public bool ExportWornPatternSTL(float[,] originalHeight, float[,] wearDepth,
            string filePath, float widthMeters = 0.1f, float lengthMeters = 0.28f,
            float baseHeight = 0.005f, bool binary = true)
        {
            if (originalHeight == null || wearDepth == null) return false;

            int n = originalHeight.GetLength(0);
            int m = originalHeight.GetLength(1);

            float[,] wornHeight = new float[n, m];
            for (int i = 0; i < n; i++)
                for (int j = 0; j < m; j++)
                    wornHeight[i, j] = Mathf.Max(0f, originalHeight[i, j] - wearDepth[i, j]);

            return ExportHeightFieldSTL(wornHeight, filePath, widthMeters, lengthMeters, baseHeight, binary);
        }
    }
}
