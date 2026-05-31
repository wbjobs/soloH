import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List, Tuple, Optional


def square_distance(src: torch.Tensor, dst: torch.Tensor) -> torch.Tensor:
    B, N, _ = src.shape
    _, M, _ = dst.shape
    dist = -2 * torch.matmul(src, dst.permute(0, 2, 1))
    dist += torch.sum(src ** 2, -1).view(B, N, 1)
    dist += torch.sum(dst ** 2, -1).view(B, 1, M)
    return dist


def index_points(points: torch.Tensor, idx: torch.Tensor) -> torch.Tensor:
    device = points.device
    B = points.shape[0]
    view_shape = list(idx.shape)
    view_shape[1:] = [1] * (len(view_shape) - 1)
    repeat_shape = list(idx.shape)
    repeat_shape[0] = 1
    batch_indices = torch.arange(B, dtype=torch.long).to(device).view(view_shape).repeat(repeat_shape)
    new_points = points[batch_indices, idx, :]
    return new_points


def farthest_point_sample(xyz: torch.Tensor, npoint: int) -> torch.Tensor:
    device = xyz.device
    B, N, C = xyz.shape
    centroids = torch.zeros(B, npoint, dtype=torch.long).to(device)
    distance = torch.ones(B, N).to(device) * 1e10
    farthest = torch.randint(0, N, (B,), dtype=torch.long).to(device)
    batch_indices = torch.arange(B, dtype=torch.long).to(device)
    for i in range(npoint):
        centroids[:, i] = farthest
        centroid = xyz[batch_indices, farthest, :].view(B, 1, 3)
        dist = torch.sum((xyz - centroid) ** 2, -1)
        mask = dist < distance
        distance[mask] = dist[mask]
        farthest = torch.max(distance, -1)[1]
    return centroids


def query_ball_point(radius: float, nsample: int, xyz: torch.Tensor,
                     new_xyz: torch.Tensor) -> torch.Tensor:
    device = xyz.device
    B, N, C = xyz.shape
    _, S, _ = new_xyz.shape
    group_idx = torch.arange(N, dtype=torch.long).to(device).view(1, 1, N).repeat([B, S, 1])
    sqrdists = square_distance(new_xyz, xyz)
    group_idx[sqrdists > radius ** 2] = N
    group_idx = group_idx.sort(dim=-1)[0][:, :, :nsample]
    group_first = group_idx[:, :, 0].view(B, S, 1).repeat([1, 1, nsample])
    mask = group_idx == N
    group_idx[mask] = group_first[mask]
    return group_idx


def sample_and_group(npoint: int, radius: float, nsample: int, xyz: torch.Tensor,
                     points: torch.Tensor, returnfps: bool = False) -> Tuple:
    B, N, C = xyz.shape
    S = npoint
    fps_idx = farthest_point_sample(xyz, npoint)
    new_xyz = index_points(xyz, fps_idx)
    idx = query_ball_point(radius, nsample, xyz, new_xyz)
    grouped_xyz = index_points(xyz, idx)
    grouped_xyz_norm = grouped_xyz - new_xyz.view(B, S, 1, C)

    if points is not None:
        grouped_points = index_points(points, idx)
        new_points = torch.cat([grouped_xyz_norm, grouped_points], dim=-1)
    else:
        new_points = grouped_xyz_norm
    if returnfps:
        return new_xyz, new_points, grouped_xyz, fps_idx
    else:
        return new_xyz, new_points


def sample_and_group_all(xyz: torch.Tensor, points: torch.Tensor) -> Tuple:
    device = xyz.device
    B, N, C = xyz.shape
    new_xyz = torch.zeros(B, 1, C).to(device)
    grouped_xyz = xyz.view(B, 1, N, C)
    if points is not None:
        new_points = torch.cat([grouped_xyz, points.view(B, 1, N, -1)], dim=-1)
    else:
        new_points = grouped_xyz
    return new_xyz, new_points


class PointNetSetAbstraction(nn.Module):
    def __init__(self, npoint: int, radius: float, nsample: int, in_channel: int,
                 mlp: List[int], group_all: bool = False):
        super(PointNetSetAbstraction, self).__init__()
        self.npoint = npoint
        self.radius = radius
        self.nsample = nsample
        self.mlp_convs = nn.ModuleList()
        self.mlp_bns = nn.ModuleList()
        last_channel = in_channel
        for out_channel in mlp:
            self.mlp_convs.append(nn.Conv2d(last_channel, out_channel, 1))
            self.mlp_bns.append(nn.BatchNorm2d(out_channel))
            last_channel = out_channel
        self.group_all = group_all

    def forward(self, xyz: torch.Tensor, points: Optional[torch.Tensor]) -> Tuple[torch.Tensor, torch.Tensor]:
        xyz = xyz.permute(0, 2, 1)
        if points is not None:
            points = points.permute(0, 2, 1)

        if self.group_all:
            new_xyz, new_points = sample_and_group_all(xyz, points)
        else:
            new_xyz, new_points = sample_and_group(self.npoint, self.radius, self.nsample, xyz, points)

        new_points = new_points.permute(0, 3, 2, 1)
        for i, conv in enumerate(self.mlp_convs):
            bn = self.mlp_bns[i]
            new_points = F.relu(bn(conv(new_points)))

        new_points = torch.max(new_points, 2)[0]
        new_xyz = new_xyz.permute(0, 2, 1)
        return new_xyz, new_points


class PointNetSetAbstractionMsg(nn.Module):
    def __init__(self, npoint: int, radius_list: List[float], nsample_list: List[int],
                 in_channel: int, mlp_list: List[List[int]]):
        super(PointNetSetAbstractionMsg, self).__init__()
        self.npoint = npoint
        self.radius_list = radius_list
        self.nsample_list = nsample_list
        self.conv_blocks = nn.ModuleList()
        self.bn_blocks = nn.ModuleList()
        for i in range(len(mlp_list)):
            convs = nn.ModuleList()
            bns = nn.ModuleList()
            last_channel = in_channel + 3
            for out_channel in mlp_list[i]:
                convs.append(nn.Conv2d(last_channel, out_channel, 1))
                bns.append(nn.BatchNorm2d(out_channel))
                last_channel = out_channel
            self.conv_blocks.append(convs)
            self.bn_blocks.append(bns)

    def forward(self, xyz: torch.Tensor, points: Optional[torch.Tensor]) -> Tuple[torch.Tensor, torch.Tensor]:
        xyz = xyz.permute(0, 2, 1)
        if points is not None:
            points = points.permute(0, 2, 1)

        B, N, C = xyz.shape
        S = self.npoint
        new_xyz = index_points(xyz, farthest_point_sample(xyz, S))
        new_points_list = []
        for i, radius in enumerate(self.radius_list):
            K = self.nsample_list[i]
            group_idx = query_ball_point(radius, K, xyz, new_xyz)
            grouped_xyz = index_points(xyz, group_idx)
            grouped_xyz -= new_xyz.view(B, S, 1, C)
            if points is not None:
                grouped_points = index_points(points, group_idx)
                grouped_points = torch.cat([grouped_points, grouped_xyz], dim=-1)
            else:
                grouped_points = grouped_xyz

            grouped_points = grouped_points.permute(0, 3, 2, 1)
            for j in range(len(self.conv_blocks[i])):
                conv = self.conv_blocks[i][j]
                bn = self.bn_blocks[i][j]
                grouped_points = F.relu(bn(conv(grouped_points)))
            new_points = torch.max(grouped_points, 2)[0]
            new_points_list.append(new_points)

        new_xyz = new_xyz.permute(0, 2, 1)
        new_points_concat = torch.cat(new_points_list, dim=1)
        return new_xyz, new_points_concat


class PointNetFeaturePropagation(nn.Module):
    def __init__(self, in_channel: int, mlp: List[int]):
        super(PointNetFeaturePropagation, self).__init__()
        self.mlp_convs = nn.ModuleList()
        self.mlp_bns = nn.ModuleList()
        last_channel = in_channel
        for out_channel in mlp:
            self.mlp_convs.append(nn.Conv1d(last_channel, out_channel, 1))
            self.mlp_bns.append(nn.BatchNorm1d(out_channel))
            last_channel = out_channel

    def forward(self, xyz1: torch.Tensor, xyz2: torch.Tensor,
                points1: Optional[torch.Tensor], points2: torch.Tensor) -> torch.Tensor:
        xyz1 = xyz1.permute(0, 2, 1)
        xyz2 = xyz2.permute(0, 2, 1)

        points2 = points2.permute(0, 2, 1)
        B, N, C = xyz1.shape
        _, S, _ = xyz2.shape

        if S == 1:
            interpolated_points = points2.repeat(1, N, 1)
        else:
            dists = square_distance(xyz1, xyz2)
            dists, idx = dists.sort(dim=-1)
            dists, idx = dists[:, :, :3], idx[:, :, :3]
            dist_recip = 1.0 / (dists + 1e-8)
            norm = torch.sum(dist_recip, dim=2, keepdim=True)
            weight = dist_recip / norm
            interpolated_points = torch.sum(index_points(points2, idx) * weight.view(B, N, 3, 1), dim=2)

        if points1 is not None:
            points1 = points1.permute(0, 2, 1)
            new_points = torch.cat([points1, interpolated_points], dim=-1)
        else:
            new_points = interpolated_points

        new_points = new_points.permute(0, 2, 1)
        for i, conv in enumerate(self.mlp_convs):
            bn = self.mlp_bns[i]
            new_points = F.relu(bn(conv(new_points)))
        return new_points


class PointNet2SemSeg(nn.Module):
    def __init__(self, num_classes: int = 5, use_rgb: bool = True, use_normal: bool = False,
                 use_geometric: bool = False, num_geometric_features: int = 32):
        super(PointNet2SemSeg, self).__init__()

        in_channel = 0
        if use_rgb:
            in_channel += 3
        if use_normal:
            in_channel += 3
        if use_geometric:
            in_channel += num_geometric_features
        if in_channel == 0:
            in_channel = 1

        self.use_rgb = use_rgb
        self.use_normal = use_normal
        self.use_geometric = use_geometric
        self.num_geometric_features = num_geometric_features
        self.in_channel = in_channel

        self.sa1 = PointNetSetAbstractionMsg(1024, [0.1, 0.2, 0.4], [16, 32, 128], in_channel,
                                             [[32, 32, 64], [64, 64, 128], [64, 96, 128]])
        self.sa2 = PointNetSetAbstractionMsg(256, [0.2, 0.4, 0.8], [32, 64, 128], 320,
                                             [[64, 64, 128], [128, 128, 256], [128, 128, 256]])
        self.sa3 = PointNetSetAbstraction(64, None, None, 640 + 3, [256, 512, 1024], True)

        self.fp3 = PointNetFeaturePropagation(1664, [256, 256])
        self.fp2 = PointNetFeaturePropagation(576, [256, 128])
        self.fp1 = PointNetFeaturePropagation(128 + in_channel + 3, [128, 128, 128])

        self.conv1 = nn.Conv1d(128, 128, 1)
        self.bn1 = nn.BatchNorm1d(128)
        self.drop1 = nn.Dropout(0.5)
        self.conv2 = nn.Conv1d(128, num_classes, 1)

    def _build_input(self, xyz: torch.Tensor, rgb: Optional[torch.Tensor] = None,
                     normal: Optional[torch.Tensor] = None,
                     geometric: Optional[torch.Tensor] = None) -> torch.Tensor:
        features = []
        if rgb is not None and self.use_rgb:
            features.append(rgb)
        if normal is not None and self.use_normal:
            features.append(normal)
        if geometric is not None and self.use_geometric:
            features.append(geometric)

        if len(features) == 0:
            B, _, N = xyz.shape
            features.append(torch.ones(B, 1, N, device=xyz.device))

        return torch.cat(features, dim=1)

    def forward(self, xyz: torch.Tensor, rgb: Optional[torch.Tensor] = None,
                normal: Optional[torch.Tensor] = None,
                geometric: Optional[torch.Tensor] = None) -> torch.Tensor:
        B, _, N = xyz.shape

        l0_points = self._build_input(xyz, rgb, normal, geometric)
        l0_xyz = xyz

        l1_xyz, l1_points = self.sa1(l0_xyz, l0_points)
        l2_xyz, l2_points = self.sa2(l1_xyz, l1_points)
        l3_xyz, l3_points = self.sa3(l2_xyz, l2_points)

        l2_points = self.fp3(l2_xyz, l3_xyz, l2_points, l3_points)
        l1_points = self.fp2(l1_xyz, l2_xyz, l1_points, l2_points)
        l0_points = self.fp1(l0_xyz, l1_xyz, torch.cat([l0_xyz, l0_points], dim=1), l1_points)

        feat = F.relu(self.bn1(self.conv1(l0_points)))
        feat = self.drop1(feat)
        x = self.conv2(feat)
        x = F.log_softmax(x, dim=1)
        x = x.permute(0, 2, 1)
        return x


def load_model(model_path: str, num_classes: int = 5, use_rgb: bool = True,
               use_normal: bool = False, use_geometric: bool = False,
               num_geometric_features: int = 32, device: str = 'cpu') -> PointNet2SemSeg:
    model = PointNet2SemSeg(
        num_classes=num_classes, use_rgb=use_rgb, use_normal=use_normal,
        use_geometric=use_geometric, num_geometric_features=num_geometric_features
    )
    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model


def preprocess_point_cloud_for_model(points: np.ndarray, colors: Optional[np.ndarray] = None,
                                     normals: Optional[np.ndarray] = None,
                                     num_points: int = 8192,
                                     normalize: bool = True) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, np.ndarray]:
    if len(points) < num_points:
        idx = np.random.choice(len(points), num_points, replace=True)
    else:
        idx = np.random.choice(len(points), num_points, replace=False)

    sampled_points = points[idx].copy()
    sampled_colors = colors[idx].copy() if colors is not None else None
    sampled_normals = normals[idx].copy() if normals is not None else None

    if normalize:
        centroid = np.mean(sampled_points, axis=0)
        sampled_points -= centroid
        max_distance = np.max(np.sqrt(np.sum(sampled_points ** 2, axis=1)))
        sampled_points /= max_distance

    xyz_tensor = torch.from_numpy(sampled_points).float().unsqueeze(0).permute(0, 2, 1)
    rgb_tensor = torch.from_numpy(sampled_colors).float().unsqueeze(0).permute(0, 2, 1) if sampled_colors is not None else None
    normal_tensor = torch.from_numpy(sampled_normals).float().unsqueeze(0).permute(0, 2, 1) if sampled_normals is not None else None

    return xyz_tensor, rgb_tensor, normal_tensor, idx


def compute_geometric_features_for_points(points: np.ndarray,
                                          use_multi_scale: bool = True,
                                          radii: List[float] = None) -> Optional[np.ndarray]:
    try:
        from .enhancement import extract_geometric_features
        from .data_io import PointCloudData
        temp_data = PointCloudData(points)
        features = extract_geometric_features(temp_data, use_multi_scale=use_multi_scale, radii=radii)
        return features
    except Exception as e:
        print(f"Warning: Could not compute geometric features: {e}")
        return None


@torch.no_grad()
def predict_segmentation(model: PointNet2SemSeg, points: np.ndarray,
                         colors: Optional[np.ndarray] = None,
                         normals: Optional[np.ndarray] = None,
                         batch_size: int = 4096,
                         normalize: bool = True,
                         use_geometric_features: bool = False,
                         geometric_radii: List[float] = None,
                         device: str = 'cpu') -> np.ndarray:
    model.eval()
    num_points = len(points)
    predictions = np.zeros(num_points, dtype=np.int32)
    confidence = np.zeros(num_points, dtype=np.float32)

    geometric_features = None
    if use_geometric_features and model.use_geometric:
        print("  Computing multi-scale geometric features for improved generalization...")
        geometric_features = compute_geometric_features_for_points(
            points, use_multi_scale=True, radii=geometric_radii
        )

    indices = np.arange(num_points)
    num_batches = int(np.ceil(num_points / batch_size))

    for i in range(num_batches):
        start_idx = i * batch_size
        end_idx = min(start_idx + batch_size, num_points)
        batch_indices = indices[start_idx:end_idx]
        batch_points = points[batch_indices]

        if normalize:
            centroid = np.mean(batch_points, axis=0)
            batch_points_normalized = batch_points - centroid
            max_dist = np.max(np.sqrt(np.sum(batch_points_normalized ** 2, axis=1))) + 1e-8
            batch_points_normalized /= max_dist
        else:
            batch_points_normalized = batch_points

        xyz = torch.from_numpy(batch_points_normalized).float().unsqueeze(0).permute(0, 2, 1).to(device)
        rgb = torch.from_numpy(colors[batch_indices]).float().unsqueeze(0).permute(0, 2, 1).to(device) if colors is not None else None
        normal = torch.from_numpy(normals[batch_indices]).float().unsqueeze(0).permute(0, 2, 1).to(device) if normals is not None else None
        geometric = None
        if geometric_features is not None:
            geometric = torch.from_numpy(geometric_features[batch_indices]).float().unsqueeze(0).permute(0, 2, 1).to(device)

        outputs = model(xyz, rgb, normal, geometric)
        probs = torch.exp(outputs)
        pred_labels = torch.argmax(probs, dim=-1).squeeze(0).cpu().numpy()
        pred_conf = torch.max(probs, dim=-1)[0].squeeze(0).cpu().numpy()

        predictions[batch_indices] = pred_labels
        confidence[batch_indices] = pred_conf

    return predictions


@torch.no_grad()
def predict_segmentation_full(model: PointNet2SemSeg, points: np.ndarray,
                              colors: Optional[np.ndarray] = None,
                              normals: Optional[np.ndarray] = None,
                              num_samples: int = 10,
                              points_per_sample: int = 8192,
                              use_geometric_features: bool = False,
                              geometric_radii: List[float] = None,
                              device: str = 'cpu') -> np.ndarray:
    model.eval()
    num_points = len(points)
    vote_counts = np.zeros((num_points, 5), dtype=np.float32)

    all_geometric = None
    if use_geometric_features and model.use_geometric:
        print("  Computing multi-scale geometric features...")
        all_geometric = compute_geometric_features_for_points(
            points, use_multi_scale=True, radii=geometric_radii
        )

    for _ in range(num_samples):
        idx = np.random.choice(num_points, points_per_sample, replace=True)

        sample_points = points[idx].copy()
        centroid = np.mean(sample_points, axis=0)
        sample_points -= centroid
        max_dist = np.max(np.sqrt(np.sum(sample_points ** 2, axis=1))) + 1e-8
        sample_points /= max_dist

        xyz = torch.from_numpy(sample_points).float().unsqueeze(0).permute(0, 2, 1).to(device)
        rgb = torch.from_numpy(colors[idx]).float().unsqueeze(0).permute(0, 2, 1).to(device) if colors is not None else None
        normal = torch.from_numpy(normals[idx]).float().unsqueeze(0).permute(0, 2, 1).to(device) if normals is not None else None
        geometric = None
        if all_geometric is not None:
            geometric = torch.from_numpy(all_geometric[idx]).float().unsqueeze(0).permute(0, 2, 1).to(device)

        outputs = model(xyz, rgb, normal, geometric)
        probs = torch.exp(outputs).squeeze(0).cpu().numpy()

        for i, point_idx in enumerate(idx):
            vote_counts[point_idx] += probs[i]

    predictions = np.argmax(vote_counts, axis=1)
    return predictions


class GCNConv(nn.Module):
    def __init__(self, in_features: int, out_features: int, bias: bool = True):
        super(GCNConv, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.weight = nn.Parameter(torch.FloatTensor(in_features, out_features))
        if bias:
            self.bias = nn.Parameter(torch.FloatTensor(out_features))
        else:
            self.register_parameter('bias', None)
        self.reset_parameters()

    def reset_parameters(self):
        stdv = 1. / np.sqrt(self.weight.size(1))
        self.weight.data.uniform_(-stdv, stdv)
        if self.bias is not None:
            self.bias.data.uniform_(-stdv, stdv)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        support = torch.matmul(x, self.weight)
        output = torch.matmul(adj, support)
        if self.bias is not None:
            return output + self.bias
        else:
            return output


class GCN(nn.Module):
    def __init__(self, num_features: int, num_classes: int, hidden_dim: int = 128,
                 dropout: float = 0.5):
        super(GCN, self).__init__()
        self.conv1 = GCNConv(num_features, hidden_dim)
        self.conv2 = GCNConv(hidden_dim, hidden_dim)
        self.conv3 = GCNConv(hidden_dim, num_classes)
        self.dropout = dropout

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.conv1(x, adj))
        x = F.dropout(x, self.dropout, training=self.training)
        x = F.relu(self.conv2(x, adj))
        x = F.dropout(x, self.dropout, training=self.training)
        x = self.conv3(x, adj)
        return F.log_softmax(x, dim=-1)


def build_graph(points: np.ndarray, k: int = 16) -> np.ndarray:
    from scipy.spatial import cKDTree
    tree = cKDTree(points)
    distances, indices = tree.query(points, k=k + 1)

    n = len(points)
    adj = np.zeros((n, n), dtype=np.float32)

    for i in range(n):
        for j in range(1, k + 1):
            adj[i, indices[i, j]] = 1.0
            adj[indices[i, j], i] = 1.0

    rowsum = adj.sum(axis=1)
    d_inv_sqrt = np.power(rowsum, -0.5).flatten()
    d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.
    d_mat_inv_sqrt = np.diag(d_inv_sqrt)
    adj_normalized = d_mat_inv_sqrt @ adj @ d_mat_inv_sqrt

    return adj_normalized
