using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;
using LanderSim.Terrain;

namespace LanderSim.PathPlanning
{
    public class RRTNode
    {
        public Vector3d position;
        public RRTNode parent;
        public double cost;

        public RRTNode(Vector3d pos, RRTNode parent = null)
        {
            position = pos;
            this.parent = parent;
            cost = parent != null ? parent.cost + Vector3d.Distance(parent.position, pos) : 0;
        }
    }

    public class RRTPathfinder
    {
        private Grid3D grid;
        private TerrainGenerator terrainGenerator;
        private Bounds bounds;

        public double stepSize = 3.0;
        public double goalBias = 0.1;
        public int maxIterations = 5000;
        public double connectionRadius = 5.0;
        public double safetyMargin = 1.5;

        public RRTPathfinder(Grid3D grid, TerrainGenerator terrainGenerator = null)
        {
            this.grid = grid;
            this.terrainGenerator = terrainGenerator;

            Vector3 min = new Vector3(
                (float)grid.origin.x,
                (float)grid.origin.y,
                (float)grid.origin.z
            );
            Vector3 max = new Vector3(
                (float)(grid.origin.x + grid.sizeX * grid.cellSize),
                (float)(grid.origin.y + grid.sizeY * grid.cellSize),
                (float)(grid.origin.z + grid.sizeZ * grid.cellSize)
            );
            bounds = new Bounds((min + max) * 0.5f, max - min);
        }

        public List<Vector3d> FindPath(Vector3d startPos, Vector3d goalPos)
        {
            if (!IsValidPosition(startPos))
            {
                startPos = AdjustPosition(startPos);
                if (!IsValidPosition(startPos))
                {
                    Debug.LogWarning("Start position is invalid");
                    return null;
                }
            }

            if (!IsValidPosition(goalPos))
            {
                goalPos = AdjustPosition(goalPos);
                if (!IsValidPosition(goalPos))
                {
                    Debug.LogWarning("Goal position is invalid");
                    return null;
                }
            }

            List<RRTNode> tree = new List<RRTNode> { new RRTNode(startPos) };
            System.Random random = new System.Random();

            for (int i = 0; i < maxIterations; i++)
            {
                Vector3d randomPos = GenerateRandomPoint(goalPos, random);
                RRTNode nearestNode = FindNearestNode(tree, randomPos);
                Vector3d newPos = Steer(nearestNode.position, randomPos);

                if (IsValidPosition(newPos) &&
                    IsCollisionFree(nearestNode.position, newPos))
                {
                    RRTNode newNode = new RRTNode(newPos, nearestNode);
                    tree.Add(newNode);

                    if (Vector3d.Distance(newPos, goalPos) < stepSize &&
                        IsCollisionFree(newPos, goalPos))
                    {
                        RRTNode goalNode = new RRTNode(goalPos, newNode);
                        tree.Add(goalNode);
                        return ReconstructPath(goalNode);
                    }
                }
            }

            Debug.LogWarning("RRT failed to find path");
            return null;
        }

        public List<Vector3d> FindPathRRTStar(Vector3d startPos, Vector3d goalPos)
        {
            if (!IsValidPosition(startPos) || !IsValidPosition(goalPos))
            {
                Debug.LogWarning("Start or goal position invalid");
                return null;
            }

            List<RRTNode> tree = new List<RRTNode> { new RRTNode(startPos) };
            System.Random random = new System.Random();
            RRTNode bestGoalNode = null;
            double bestCost = double.MaxValue;

            for (int i = 0; i < maxIterations; i++)
            {
                Vector3d randomPos = GenerateRandomPoint(goalPos, random);
                RRTNode nearestNode = FindNearestNode(tree, randomPos);
                Vector3d newPos = Steer(nearestNode.position, randomPos);

                if (!IsValidPosition(newPos) ||
                    !IsCollisionFree(nearestNode.position, newPos))
                {
                    continue;
                }

                List<RRTNode> neighbors = FindNearbyNodes(tree, newPos, connectionRadius);

                RRTNode bestParent = nearestNode;
                double bestCostToNew = nearestNode.cost +
                    Vector3d.Distance(nearestNode.position, newPos);

                foreach (RRTNode neighbor in neighbors)
                {
                    if (IsCollisionFree(neighbor.position, newPos))
                    {
                        double potentialCost = neighbor.cost +
                            Vector3d.Distance(neighbor.position, newPos);
                        if (potentialCost < bestCostToNew)
                        {
                            bestParent = neighbor;
                            bestCostToNew = potentialCost;
                        }
                    }
                }

                RRTNode newNode = new RRTNode(newPos, bestParent);
                newNode.cost = bestCostToNew;
                tree.Add(newNode);

                foreach (RRTNode neighbor in neighbors)
                {
                    if (neighbor != bestParent &&
                        IsCollisionFree(newNode.position, neighbor.position))
                    {
                        double potentialCost = newNode.cost +
                            Vector3d.Distance(newNode.position, neighbor.position);
                        if (potentialCost < neighbor.cost)
                        {
                            neighbor.parent = newNode;
                            neighbor.cost = potentialCost;
                        }
                    }
                }

                if (Vector3d.Distance(newPos, goalPos) < stepSize * 2 &&
                    IsCollisionFree(newPos, goalPos))
                {
                    double goalCost = newNode.cost + Vector3d.Distance(newPos, goalPos);
                    if (goalCost < bestCost)
                    {
                        bestGoalNode = new RRTNode(goalPos, newNode);
                        bestGoalNode.cost = goalCost;
                        bestCost = goalCost;
                    }
                }
            }

            if (bestGoalNode != null)
            {
                return ReconstructPath(bestGoalNode);
            }

            Debug.LogWarning("RRT* failed to find path");
            return null;
        }

        private Vector3d GenerateRandomPoint(Vector3d goalPos, System.Random random)
        {
            if (random.NextDouble() < goalBias)
            {
                return goalPos + new Vector3d(
                    (random.NextDouble() - 0.5) * stepSize,
                    (random.NextDouble() - 0.5) * stepSize,
                    (random.NextDouble() - 0.5) * stepSize
                );
            }

            return new Vector3d(
                bounds.min.x + random.NextDouble() * bounds.size.x,
                bounds.min.y + random.NextDouble() * bounds.size.y,
                bounds.min.z + random.NextDouble() * bounds.size.z
            );
        }

        private RRTNode FindNearestNode(List<RRTNode> tree, Vector3d point)
        {
            RRTNode nearest = tree[0];
            double minDist = Vector3d.Distance(nearest.position, point);

            for (int i = 1; i < tree.Count; i++)
            {
                double dist = Vector3d.Distance(tree[i].position, point);
                if (dist < minDist)
                {
                    minDist = dist;
                    nearest = tree[i];
                }
            }

            return nearest;
        }

        private List<RRTNode> FindNearbyNodes(List<RRTNode> tree,
                                              Vector3d point, double radius)
        {
            List<RRTNode> neighbors = new List<RRTNode>();
            double radiusSq = radius * radius;

            foreach (RRTNode node in tree)
            {
                double dx = node.position.x - point.x;
                double dy = node.position.y - point.y;
                double dz = node.position.z - point.z;

                if (dx * dx + dy * dy + dz * dz <= radiusSq)
                {
                    neighbors.Add(node);
                }
            }

            return neighbors;
        }

        private Vector3d Steer(Vector3d from, Vector3d to)
        {
            Vector3d direction = to - from;
            double dist = direction.magnitude;

            if (dist <= stepSize)
            {
                return to;
            }

            return from + direction.normalized * stepSize;
        }

        private bool IsValidPosition(Vector3d pos)
        {
            if (!bounds.Contains(pos.ToVector3()))
            {
                return false;
            }

            if (!grid.IsWalkable(pos))
            {
                return false;
            }

            GridCell cell = grid.GetCell(pos);
            if (cell != null && cell.minDistanceToObstacle < safetyMargin)
            {
                return false;
            }

            return true;
        }

        private bool IsCollisionFree(Vector3d from, Vector3d to)
        {
            double dist = Vector3d.Distance(from, to);
            int steps = Math.Max(2, (int)(dist / (grid.cellSize * 0.5)));

            for (int i = 0; i <= steps; i++)
            {
                double t = (double)i / steps;
                Vector3d point = Vector3d.Lerp(from, to, t);

                if (!IsValidPosition(point))
                {
                    return false;
                }

                if (terrainGenerator != null &&
                    terrainGenerator.CheckCollision(point, safetyMargin))
                {
                    return false;
                }
            }

            return true;
        }

        private Vector3d AdjustPosition(Vector3d pos)
        {
            Vector3d bestPos = pos;
            double bestDist = double.MaxValue;

            for (int dx = -2; dx <= 2; dx++)
            {
                for (int dy = -2; dy <= 2; dy++)
                {
                    for (int dz = -2; dz <= 2; dz++)
                    {
                        Vector3d testPos = pos + new Vector3d(
                            dx * grid.cellSize,
                            dy * grid.cellSize,
                            dz * grid.cellSize
                        );

                        if (IsValidPosition(testPos))
                        {
                            double dist = Vector3d.Distance(pos, testPos);
                            if (dist < bestDist)
                            {
                                bestDist = dist;
                                bestPos = testPos;
                            }
                        }
                    }
                }
            }

            return bestPos;
        }

        private List<Vector3d> ReconstructPath(RRTNode goalNode)
        {
            List<Vector3d> path = new List<Vector3d>();
            RRTNode current = goalNode;

            while (current != null)
            {
                path.Add(current.position);
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
                    if (IsCollisionFree(path[i], path[j]))
                    {
                        farthest = j;
                        break;
                    }
                }

                if (farthest > i + 1)
                {
                    int segments = (int)(Vector3d.Distance(path[i], path[farthest]) / stepSize);
                    for (int s = 1; s < segments; s++)
                    {
                        double t = (double)s / segments;
                        smoothed.Add(Vector3d.Lerp(path[i], path[farthest], t));
                    }
                }

                smoothed.Add(path[farthest]);
                i = farthest;
            }

            return smoothed;
        }
    }
}
