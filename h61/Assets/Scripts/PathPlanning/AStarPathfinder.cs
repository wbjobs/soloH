using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;
using LanderSim.Terrain;

namespace LanderSim.PathPlanning
{
    public class AStarPathfinder
    {
        private class AStarNode : IComparable<AStarNode>
        {
            public GridCell cell;
            public AStarNode parent;
            public double gCost;
            public double hCost;
            public double fCost => gCost + hCost;

            public AStarNode(GridCell cell, AStarNode parent, double gCost, double hCost)
            {
                this.cell = cell;
                this.parent = parent;
                this.gCost = gCost;
                this.hCost = hCost;
            }

            public int CompareTo(AStarNode other)
            {
                int compare = fCost.CompareTo(other.fCost);
                if (compare == 0)
                {
                    compare = hCost.CompareTo(other.hCost);
                }
                return compare;
            }
        }

        private Grid3D grid;
        private TerrainGenerator terrainGenerator;

        public double fuelCostWeight = 1.0;
        public double attitudeCostWeight = 0.5;
        public double safetyDistance = 2.0;

        public int maxIterations = 100000;

        public AStarPathfinder(Grid3D grid, TerrainGenerator terrainGenerator = null)
        {
            this.grid = grid;
            this.terrainGenerator = terrainGenerator;
        }

        public List<Vector3d> FindPath(Vector3d startPos, Vector3d endPos)
        {
            GridCell startCell = grid.GetCell(startPos);
            GridCell endCell = grid.GetCell(endPos);

            if (startCell == null || endCell == null)
            {
                Debug.LogWarning("Start or end position out of bounds");
                return null;
            }

            if (!grid.IsWalkable(startCell.x, startCell.y, startCell.z))
            {
                Vector3d adjustedPos = AdjustPositionToFree(startPos);
                startCell = grid.GetCell(adjustedPos);
                if (startCell == null || !grid.IsWalkable(startCell.x, startCell.y, startCell.z))
                {
                    Debug.LogWarning("Start position is not walkable");
                    return null;
                }
            }

            if (!grid.IsWalkable(endCell.x, endCell.y, endCell.z))
            {
                Vector3d adjustedPos = AdjustPositionToFree(endPos);
                endCell = grid.GetCell(adjustedPos);
                if (endCell == null || !grid.IsWalkable(endCell.x, endCell.y, endCell.z))
                {
                    Debug.LogWarning("End position is not walkable");
                    return null;
                }
            }

            return FindPath(startCell, endCell);
        }

        public List<Vector3d> FindPath(GridCell startCell, GridCell endCell)
        {
            grid.ResetVisited();

            PriorityQueue<AStarNode> openSet = new PriorityQueue<AStarNode>();
            HashSet<GridCell> closedSet = new HashSet<GridCell>();
            Dictionary<GridCell, AStarNode> nodeLookup = new Dictionary<GridCell, AStarNode>();

            AStarNode startNode = new AStarNode(startCell, null, 0,
                grid.GetHeuristic(startCell, endCell));
            openSet.Enqueue(startNode);
            nodeLookup[startCell] = startNode;

            int iterations = 0;

            while (openSet.Count > 0 && iterations < maxIterations)
            {
                iterations++;
                AStarNode current = openSet.Dequeue();

                if (current.cell == endCell)
                {
                    return ReconstructPath(current);
                }

                closedSet.Add(current.cell);

                foreach (GridCell neighbor in grid.GetNeighbors(current.cell))
                {
                    if (closedSet.Contains(neighbor)) continue;

                    double distance = grid.GetDistance(current.cell, neighbor);
                    double moveCost = CalculateMoveCost(current.cell, neighbor, distance);
                    double newGCost = current.gCost + moveCost;

                    AStarNode neighborNode;
                    if (!nodeLookup.TryGetValue(neighbor, out neighborNode))
                    {
                        neighborNode = new AStarNode(neighbor, current, newGCost,
                            grid.GetHeuristic(neighbor, endCell));
                        nodeLookup[neighbor] = neighborNode;
                        openSet.Enqueue(neighborNode);
                    }
                    else if (newGCost < neighborNode.gCost)
                    {
                        neighborNode.gCost = newGCost;
                        neighborNode.parent = current;
                        openSet.UpdatePriority(neighborNode);
                    }
                }
            }

            Debug.LogWarning($"A* failed to find path after {iterations} iterations");
            return null;
        }

        private double CalculateMoveCost(GridCell from, GridCell to, double distance)
        {
            double baseCost = distance * to.cost;

            double heightDiff = to.worldPosition.y - from.worldPosition.y;
            double altitudeCost = 0;
            if (heightDiff > 0)
            {
                altitudeCost = heightDiff * fuelCostWeight * 2.0;
            }
            else if (heightDiff < 0)
            {
                altitudeCost = -heightDiff * fuelCostWeight * 0.5;
            }

            double terrainHeight = to.terrainHeight;
            double clearance = to.worldPosition.y - terrainHeight;
            double safetyCost = 0;
            if (clearance < 5.0)
            {
                safetyCost = (5.0 - clearance) * 2.0;
            }

            double obstacleDistCost = 0;
            if (to.minDistanceToObstacle < safetyDistance)
            {
                obstacleDistCost = (safetyDistance - to.minDistanceToObstacle) * 5.0;
            }

            return baseCost + altitudeCost + safetyCost + obstacleDistCost;
        }

        private Vector3d AdjustPositionToFree(Vector3d position)
        {
            Vector3d adjusted = position;
            double maxSearchRadius = 10.0;
            double stepSize = 1.0;

            for (double r = stepSize; r <= maxSearchRadius; r += stepSize)
            {
                for (int theta = 0; theta < 360; theta += 30)
                {
                    for (int phi = -30; phi <= 30; phi += 30)
                    {
                        double radTheta = theta * Math.PI / 180.0;
                        double radPhi = phi * Math.PI / 180.0;
                        Vector3d offset = new Vector3d(
                            r * Math.Cos(radPhi) * Math.Cos(radTheta),
                            r * Math.Sin(radPhi),
                            r * Math.Cos(radPhi) * Math.Sin(radTheta)
                        );

                        Vector3d testPos = position + offset;
                        if (grid.IsWalkable(testPos))
                        {
                            return testPos;
                        }
                    }
                }
            }

            return position;
        }

        private List<Vector3d> ReconstructPath(AStarNode endNode)
        {
            List<Vector3d> path = new List<Vector3d>();
            AStarNode current = endNode;

            while (current != null)
            {
                path.Add(current.cell.worldPosition);
                current = current.parent;
            }

            path.Reverse();
            return SmoothPath(path);
        }

        private List<Vector3d> SmoothPath(List<Vector3d> path)
        {
            if (path.Count < 3) return path;

            List<Vector3d> smoothed = new List<Vector3d> { path[0] };

            int i = 0;
            while (i < path.Count - 1)
            {
                int farthest = i + 1;

                for (int j = path.Count - 1; j > i; j--)
                {
                    if (IsLineOfSight(path[i], path[j]))
                    {
                        farthest = j;
                        break;
                    }
                }

                if (farthest == i + 1)
                {
                    farthest = Math.Min(i + 2, path.Count - 1);
                }

                Vector3d midPoint = Vector3d.Lerp(path[i], path[farthest], 0.5);
                smoothed.Add(midPoint);
                smoothed.Add(path[farthest]);

                i = farthest;
            }

            return smoothed;
        }

        private bool IsLineOfSight(Vector3d from, Vector3d to)
        {
            double dist = Vector3d.Distance(from, to);
            int steps = (int)(dist / (grid.cellSize * 0.5));

            for (int i = 0; i <= steps; i++)
            {
                double t = (double)i / steps;
                Vector3d point = Vector3d.Lerp(from, to, t);

                if (!grid.IsWalkable(point))
                {
                    return false;
                }

                if (terrainGenerator != null && terrainGenerator.CheckCollision(point, 1.0))
                {
                    return false;
                }
            }

            return true;
        }

        public List<Vector3d> OptimizePathForFuel(List<Vector3d> path,
                                                  double maxVerticalSpeed = 5.0,
                                                  double maxHorizontalSpeed = 10.0)
        {
            if (path.Count < 2) return path;

            List<Vector3d> optimized = new List<Vector3d> { path[0] };
            Vector3d currentVel = Vector3d.zero;

            for (int i = 1; i < path.Count; i++)
            {
                Vector3d target = path[i];
                Vector3d current = optimized[optimized.Count - 1];
                Vector3d delta = target - current;

                double desiredSpeed = Math.Min(maxHorizontalSpeed,
                    Math.Sqrt(delta.x * delta.x + delta.z * delta.z));

                Vector3d direction = delta.normalized;
                Vector3d desiredVel = new Vector3d(
                    direction.x * desiredSpeed,
                    Math.Sign(delta.y) * Math.Min(Math.Abs(delta.y), maxVerticalSpeed),
                    direction.z * desiredSpeed
                );

                double dt = 1.0;
                Vector3d newVel = currentVel + (desiredVel - currentVel) * 0.5;
                Vector3d newPos = current + newVel * dt;

                if (grid.IsWalkable(newPos))
                {
                    optimized.Add(newPos);
                    currentVel = newVel;
                }
                else
                {
                    optimized.Add(target);
                    currentVel = Vector3d.zero;
                }
            }

            return optimized;
        }
    }

    public class PriorityQueue<T> where T : IComparable<T>
    {
        private List<T> items;

        public int Count => items.Count;

        public PriorityQueue()
        {
            items = new List<T>();
        }

        public void Enqueue(T item)
        {
            items.Add(item);
            int childIndex = items.Count - 1;

            while (childIndex > 0)
            {
                int parentIndex = (childIndex - 1) / 2;

                if (items[childIndex].CompareTo(items[parentIndex]) >= 0)
                    break;

                T tmp = items[childIndex];
                items[childIndex] = items[parentIndex];
                items[parentIndex] = tmp;

                childIndex = parentIndex;
            }
        }

        public T Dequeue()
        {
            int lastIndex = items.Count - 1;
            T frontItem = items[0];
            items[0] = items[lastIndex];
            items.RemoveAt(lastIndex);

            lastIndex--;
            int parentIndex = 0;

            while (true)
            {
                int leftChildIndex = parentIndex * 2 + 1;
                int rightChildIndex = parentIndex * 2 + 2;

                if (leftChildIndex > lastIndex)
                    break;

                int minChildIndex = leftChildIndex;

                if (rightChildIndex <= lastIndex &&
                    items[rightChildIndex].CompareTo(items[leftChildIndex]) < 0)
                {
                    minChildIndex = rightChildIndex;
                }

                if (items[parentIndex].CompareTo(items[minChildIndex]) <= 0)
                    break;

                T tmp = items[parentIndex];
                items[parentIndex] = items[minChildIndex];
                items[minChildIndex] = tmp;

                parentIndex = minChildIndex;
            }

            return frontItem;
        }

        public T Peek()
        {
            return items[0];
        }

        public bool Contains(T item)
        {
            return items.Contains(item);
        }

        public void UpdatePriority(T item)
        {
            int index = items.IndexOf(item);
            if (index >= 0)
            {
                items.RemoveAt(index);
                Enqueue(item);
            }
        }

        public void Clear()
        {
            items.Clear();
        }
    }
}
