using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;
using LanderSim.Terrain;

namespace LanderSim.PathPlanning
{
    public enum CellType
    {
        Free,
        Obstacle,
        Terrain,
        Danger
    }

    [Serializable]
    public class GridCell
    {
        public int x;
        public int y;
        public int z;
        public Vector3d worldPosition;
        public CellType type;
        public double cost;
        public bool visited;
        public double terrainHeight;
        public double minDistanceToObstacle;

        public GridCell(int x, int y, int z, Vector3d worldPos)
        {
            this.x = x;
            this.y = y;
            this.z = z;
            worldPosition = worldPos;
            type = CellType.Free;
            cost = 1.0;
            visited = false;
            terrainHeight = 0;
            minDistanceToObstacle = double.MaxValue;
        }

        public override string ToString()
        {
            return $"Cell({x}, {y}, {z}) Type={type} Cost={cost:F2}";
        }
    }

    [Serializable]
    public class DynamicObstacle
    {
        public string name;
        public Vector3d center;
        public Vector3d velocity;
        public Vector3d size;
        public double intensity;
        public double lifetime;
        public double age;
        public bool isActive;

        public DynamicObstacle(string name, Vector3d center, Vector3d size,
                              Vector3d velocity = default(Vector3d),
                              double intensity = 1.0, double lifetime = 30.0)
        {
            this.name = name;
            this.center = center;
            this.size = size;
            this.velocity = velocity;
            this.intensity = intensity;
            this.lifetime = lifetime;
            this.age = 0;
            this.isActive = true;
        }

        public void Update(double dt)
        {
            if (!isActive) return;
            center += velocity * dt;
            age += dt;
            if (age >= lifetime)
            {
                isActive = false;
            }
        }

        public bool Contains(Vector3d point)
        {
            if (!isActive) return false;
            Vector3d delta = point - center;
            delta = new Vector3d(
                Math.Abs(delta.x) / size.x,
                Math.Abs(delta.y) / size.y,
                Math.Abs(delta.z) / size.z
            );
            return delta.x <= 1.0 && delta.y <= 1.0 && delta.z <= 1.0;
        }

        public double GetDistance(Vector3d point)
        {
            if (!isActive) return double.MaxValue;
            Vector3d delta = point - center;
            Vector3d closest = new Vector3d(
                Math.Max(-size.x, Math.Min(size.x, delta.x)),
                Math.Max(-size.y, Math.Min(size.y, delta.y)),
                Math.Max(-size.z, Math.Min(size.z, delta.z))
            );
            return (delta - closest).magnitude;
        }
    }

    public class Grid3D
    {
        public int sizeX;
        public int sizeY;
        public int sizeZ;
        public float cellSize;
        public Vector3d origin;
        public GridCell[,,] cells;

        private TerrainData terrainData;
        private TerrainGenerator terrainGenerator;

        private List<DynamicObstacle> dynamicObstacles = new List<DynamicObstacle>();
        private CellType[,] originalCellTypes;
        private double[,] originalCellCosts;

        public Grid3D(int sizeX, int sizeY, int sizeZ, float cellSize,
                     Vector3d origin, TerrainData terrainData,
                     TerrainGenerator terrainGenerator = null)
        {
            this.sizeX = sizeX;
            this.sizeY = sizeY;
            this.sizeZ = sizeZ;
            this.cellSize = cellSize;
            this.origin = origin;
            this.terrainData = terrainData;
            this.terrainGenerator = terrainGenerator;

            InitializeGrid();
        }

        private void InitializeGrid()
        {
            cells = new GridCell[sizeX, sizeY, sizeZ];

            for (int x = 0; x < sizeX; x++)
            {
                for (int y = 0; y < sizeY; y++)
                {
                    for (int z = 0; z < sizeZ; z++)
                    {
                        Vector3d worldPos = new Vector3d(
                            origin.x + x * cellSize + cellSize * 0.5,
                            origin.y + y * cellSize + cellSize * 0.5,
                            origin.z + z * cellSize + cellSize * 0.5
                        );

                        cells[x, y, z] = new GridCell(x, y, z, worldPos);
                    }
                }
            }

            UpdateCellTypes();
            CalculateObstacleDistances();
        }

        public void UpdateCellTypes()
        {
            if (terrainData == null) return;

            for (int x = 0; x < sizeX; x++)
            {
                for (int z = 0; z < sizeZ; z++)
                {
                    Vector3d worldPos = cells[x, 0, z].worldPosition;

                    if (!terrainData.IsInBounds((float)worldPos.x, (float)worldPos.z))
                    {
                        for (int y = 0; y < sizeY; y++)
                        {
                            cells[x, y, z].type = CellType.Obstacle;
                        }
                        continue;
                    }

                    float terrainHeight = terrainData.GetHeight((float)worldPos.x, (float)worldPos.z);

                    for (int y = 0; y < sizeY; y++)
                    {
                        GridCell cell = cells[x, y, z];
                        cell.terrainHeight = terrainHeight;

                        if (cell.worldPosition.y <= terrainHeight)
                        {
                            cell.type = CellType.Terrain;
                        }
                        else
                        {
                            cell.type = CellType.Free;
                        }
                    }
                }
            }

            if (terrainGenerator != null)
            {
                MarkObstacleCells();
            }
        }

        private void MarkObstacleCells()
        {
            if (terrainGenerator == null || terrainGenerator.Rocks == null) return;

            foreach (var rock in terrainGenerator.Rocks)
            {
                Vector3d rockCenter = Vector3d.FromVector3(rock.center);
                Vector3d rockSize = Vector3d.FromVector3(rock.size);

                int minX = Math.Max(0, (int)((rockCenter.x - rockSize.x - origin.x) / cellSize));
                int maxX = Math.Min(sizeX - 1, (int)((rockCenter.x + rockSize.x - origin.x) / cellSize));
                int minY = Math.Max(0, (int)((rockCenter.y - rockSize.y - origin.y) / cellSize));
                int maxY = Math.Min(sizeY - 1, (int)((rockCenter.y + rockSize.y - origin.y) / cellSize));
                int minZ = Math.Max(0, (int)((rockCenter.z - rockSize.z - origin.z) / cellSize));
                int maxZ = Math.Min(sizeZ - 1, (int)((rockCenter.z + rockSize.z - origin.z) / cellSize));

                for (int x = minX; x <= maxX; x++)
                {
                    for (int y = minY; y <= maxY; y++)
                    {
                        for (int z = minZ; z <= maxZ; z++)
                        {
                            GridCell cell = cells[x, y, z];
                            if (rock.collisionEllipsoid.Contains(cell.worldPosition))
                            {
                                cell.type = CellType.Obstacle;
                            }
                        }
                    }
                }
            }
        }

        private void CalculateObstacleDistances()
        {
            Queue<GridCell> queue = new Queue<GridCell>();

            for (int x = 0; x < sizeX; x++)
            {
                for (int y = 0; y < sizeY; y++)
                {
                    for (int z = 0; z < sizeZ; z++)
                    {
                        GridCell cell = cells[x, y, z];
                        if (cell.type == CellType.Obstacle || cell.type == CellType.Terrain)
                        {
                            cell.minDistanceToObstacle = 0;
                            queue.Enqueue(cell);
                        }
                        else
                        {
                            cell.minDistanceToObstacle = double.MaxValue;
                        }
                    }
                }
            }

            int[] dx = { -1, 1, 0, 0, 0, 0 };
            int[] dy = { 0, 0, -1, 1, 0, 0 };
            int[] dz = { 0, 0, 0, 0, -1, 1 };

            while (queue.Count > 0)
            {
                GridCell current = queue.Dequeue();

                for (int i = 0; i < 6; i++)
                {
                    int nx = current.x + dx[i];
                    int ny = current.y + dy[i];
                    int nz = current.z + dz[i];

                    if (IsInBounds(nx, ny, nz))
                    {
                        GridCell neighbor = cells[nx, ny, nz];
                        double newDist = current.minDistanceToObstacle + cellSize;

                        if (newDist < neighbor.minDistanceToObstacle)
                        {
                            neighbor.minDistanceToObstacle = newDist;
                            queue.Enqueue(neighbor);
                        }
                    }
                }
            }

            for (int x = 0; x < sizeX; x++)
            {
                for (int y = 0; y < sizeY; y++)
                {
                    for (int z = 0; z < sizeZ; z++)
                    {
                        GridCell cell = cells[x, y, z];
                        if (cell.type == CellType.Free && cell.minDistanceToObstacle < 3.0)
                        {
                            cell.type = CellType.Danger;
                            cell.cost = 2.0 + (3.0 - cell.minDistanceToObstacle) * 2.0;
                        }
                    }
                }
            }
        }

        public GridCell GetCell(int x, int y, int z)
        {
            if (!IsInBounds(x, y, z)) return null;
            return cells[x, y, z];
        }

        public GridCell GetCell(Vector3d worldPosition)
        {
            int x = (int)((worldPosition.x - origin.x) / cellSize);
            int y = (int)((worldPosition.y - origin.y) / cellSize);
            int z = (int)((worldPosition.z - origin.z) / cellSize);
            return GetCell(x, y, z);
        }

        public bool IsInBounds(int x, int y, int z)
        {
            return x >= 0 && x < sizeX &&
                   y >= 0 && y < sizeY &&
                   z >= 0 && z < sizeZ;
        }

        public bool IsWalkable(int x, int y, int z)
        {
            GridCell cell = GetCell(x, y, z);
            return cell != null && cell.type != CellType.Obstacle && cell.type != CellType.Terrain;
        }

        public bool IsWalkable(Vector3d worldPosition)
        {
            GridCell cell = GetCell(worldPosition);
            return cell != null && cell.type != CellType.Obstacle && cell.type != CellType.Terrain;
        }

        public List<GridCell> GetNeighbors(GridCell cell, bool includeDiagonals = true)
        {
            List<GridCell> neighbors = new List<GridCell>();

            int[] dx, dy, dz;

            if (includeDiagonals)
            {
                int count = 0;
                dx = new int[26];
                dy = new int[26];
                dz = new int[26];

                for (int i = -1; i <= 1; i++)
                {
                    for (int j = -1; j <= 1; j++)
                    {
                        for (int k = -1; k <= 1; k++)
                        {
                            if (i == 0 && j == 0 && k == 0) continue;
                            dx[count] = i;
                            dy[count] = j;
                            dz[count] = k;
                            count++;
                        }
                    }
                }
            }
            else
            {
                dx = new int[] { -1, 1, 0, 0, 0, 0 };
                dy = new int[] { 0, 0, -1, 1, 0, 0 };
                dz = new int[] { 0, 0, 0, 0, -1, 1 };
            }

            for (int i = 0; i < dx.Length; i++)
            {
                int nx = cell.x + dx[i];
                int ny = cell.y + dy[i];
                int nz = cell.z + dz[i];

                if (IsInBounds(nx, ny, nz) && IsWalkable(nx, ny, nz))
                {
                    neighbors.Add(cells[nx, ny, nz]);
                }
            }

            return neighbors;
        }

        public double GetDistance(GridCell a, GridCell b)
        {
            double dx = a.worldPosition.x - b.worldPosition.x;
            double dy = a.worldPosition.y - b.worldPosition.y;
            double dz = a.worldPosition.z - b.worldPosition.z;
            return Math.Sqrt(dx * dx + dy * dy + dz * dz);
        }

        public double GetHeuristic(GridCell a, GridCell b)
        {
            double dx = Math.Abs(a.worldPosition.x - b.worldPosition.x);
            double dy = Math.Abs(a.worldPosition.y - b.worldPosition.y);
            double dz = Math.Abs(a.worldPosition.z - b.worldPosition.z);

            double min = Math.Min(dx, Math.Min(dy, dz));
            double max = Math.Max(dx, Math.Max(dy, dz));
            double mid = dx + dy + dz - min - max;

            return (Math.Sqrt(3) - Math.Sqrt(2)) * min +
                   (Math.Sqrt(2) - 1) * mid +
                   1.0 * max;
        }

        public void ResetVisited()
        {
            for (int x = 0; x < sizeX; x++)
            {
                for (int y = 0; y < sizeY; y++)
                {
                    for (int z = 0; z < sizeZ; z++)
                    {
                        cells[x, y, z].visited = false;
                    }
                }
            }
        }

        public int GetTotalCells()
        {
            return sizeX * sizeY * sizeZ;
        }

        public int GetWalkableCells()
        {
            int count = 0;
            for (int x = 0; x < sizeX; x++)
            {
                for (int y = 0; y < sizeY; y++)
                {
                    for (int z = 0; z < sizeZ; z++)
                    {
                        if (IsWalkable(x, y, z)) count++;
                    }
                }
            }
            return count;
        }

        public void AddDynamicObstacle(DynamicObstacle obstacle)
        {
            dynamicObstacles.Add(obstacle);
            SaveOriginalCellStates();
        }

        public void ClearDynamicObstacles()
        {
            dynamicObstacles.Clear();
            RestoreOriginalCellStates();
        }

        public List<DynamicObstacle> GetDynamicObstacles()
        {
            return dynamicObstacles;
        }

        private void SaveOriginalCellStates()
        {
            if (originalCellTypes == null)
            {
                originalCellTypes = new CellType[sizeX, sizeZ];
                originalCellCosts = new double[sizeX, sizeZ];
            }

            for (int x = 0; x < sizeX; x++)
            {
                for (int z = 0; z < sizeZ; z++)
                {
                    originalCellTypes[x, z] = cells[x, 0, z].type;
                    originalCellCosts[x, z] = cells[x, 0, z].cost;
                }
            }
        }

        private void RestoreOriginalCellStates()
        {
            if (originalCellTypes == null) return;

            for (int x = 0; x < sizeX; x++)
            {
                for (int z = 0; z < sizeZ; z++)
                {
                    for (int y = 0; y < sizeY; y++)
                    {
                        cells[x, y, z].type = originalCellTypes[x, z];
                        cells[x, y, z].cost = originalCellCosts[x, z];
                    }
                }
            }
        }

        public void UpdateDynamicObstacles(double dt)
        {
            RestoreOriginalCellStates();

            foreach (var obstacle in dynamicObstacles)
            {
                obstacle.Update(dt);
            }

            dynamicObstacles.RemoveAll(o => !o.isActive);

            foreach (var obstacle in dynamicObstacles)
            {
                if (!obstacle.isActive) continue;

                int minX = Math.Max(0, (int)((obstacle.center.x - obstacle.size.x - origin.x) / cellSize));
                int maxX = Math.Min(sizeX - 1, (int)((obstacle.center.x + obstacle.size.x - origin.x) / cellSize));
                int minY = Math.Max(0, (int)((obstacle.center.y - obstacle.size.y - origin.y) / cellSize));
                int maxY = Math.Min(sizeY - 1, (int)((obstacle.center.y + obstacle.size.y - origin.y) / cellSize));
                int minZ = Math.Max(0, (int)((obstacle.center.z - obstacle.size.z - origin.z) / cellSize));
                int maxZ = Math.Min(sizeZ - 1, (int)((obstacle.center.z + obstacle.size.z - origin.z) / cellSize));

                for (int x = minX; x <= maxX; x++)
                {
                    for (int y = minY; y <= maxY; y++)
                    {
                        for (int z = minZ; z <= maxZ; z++)
                        {
                            GridCell cell = cells[x, y, z];
                            if (cell.type == CellType.Free || cell.type == CellType.Danger)
                            {
                                double dist = obstacle.GetDistance(cell.worldPosition);
                                if (dist < 1.0)
                                {
                                    cell.type = CellType.Obstacle;
                                    cell.cost = 1000.0;
                                }
                                else if (dist < 5.0)
                                {
                                    cell.type = CellType.Danger;
                                    cell.cost = 2.0 + (5.0 - dist) * 5.0;
                                }
                            }
                        }
                    }
                }
            }
        }

        public bool IsPathBlocked(List<Vector3d> path, int startIndex = 0, double checkAhead = 20.0)
        {
            if (dynamicObstacles.Count == 0) return false;

            double accumulatedDist = 0;
            for (int i = startIndex; i < path.Count - 1; i++)
            {
                if (accumulatedDist > checkAhead) break;

                Vector3d point = path[i];
                foreach (var obstacle in dynamicObstacles)
                {
                    if (obstacle.Contains(point))
                    {
                        return true;
                    }
                    double dist = obstacle.GetDistance(point);
                    if (dist < 2.0)
                    {
                        return true;
                    }
                }

                if (i > startIndex)
                {
                    accumulatedDist += Vector3d.Distance(path[i - 1], path[i]);
                }
            }

            return false;
        }

        public List<Vector3d> GetAvoidanceWaypoint(Vector3d currentPos, Vector3d targetPos)
        {
            List<Vector3d> waypoints = new List<Vector3d>();

            Vector3d toTarget = targetPos - currentPos;
            double distToTarget = toTarget.magnitude;

            if (distToTarget < 1e-6) return waypoints;

            Vector3d up = Vector3d.up;
            Vector3d right = Vector3d.Cross(toTarget.normalized, up).normalized;
            if (right.sqrMagnitude < 1e-6)
            {
                right = Vector3d.right;
            }

            double climbAltitude = Math.Min(50.0, distToTarget * 0.3);
            double lateralOffset = Math.Min(20.0, distToTarget * 0.2);

            Vector3d climbPoint = currentPos + Vector3d.up * climbAltitude;
            Vector3d offsetPoint1 = climbPoint + right * lateralOffset;
            Vector3d offsetPoint2 = climbPoint - right * lateralOffset;
            Vector3d finalApproach = targetPos + Vector3d.up * 10.0;

            if (!IsWalkable(climbPoint)) climbPoint = currentPos;
            if (!IsWalkable(offsetPoint1)) offsetPoint1 = climbPoint;
            if (!IsWalkable(offsetPoint2)) offsetPoint2 = climbPoint;
            if (!IsWalkable(finalApproach)) finalApproach = targetPos;

            double dist1 = double.MaxValue, dist2 = double.MaxValue;
            foreach (var obstacle in dynamicObstacles)
            {
                dist1 = Math.Min(dist1, obstacle.GetDistance(offsetPoint1));
                dist2 = Math.Min(dist2, obstacle.GetDistance(offsetPoint2));
            }

            waypoints.Add(climbPoint);
            waypoints.Add(dist1 >= dist2 ? offsetPoint1 : offsetPoint2);
            waypoints.Add(finalApproach);
            waypoints.Add(targetPos);

            return waypoints;
        }
    }
}
