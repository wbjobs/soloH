import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from scipy.signal import butter, filtfilt
from config import Config


class EarthquakeDataset(Dataset):
    def __init__(self, waveforms, labels, window_size=200, transform=None):
        self.waveforms = waveforms
        self.labels = labels
        self.window_size = window_size
        self.transform = transform

    def __len__(self):
        return len(self.waveforms)

    def __getitem__(self, idx):
        waveform = self.waveforms[idx]
        label = self.labels[idx]

        if self.transform:
            waveform = self.transform(waveform)

        waveform = torch.FloatTensor(waveform)
        label = torch.LongTensor([label])

        return waveform, label


class CNNLSTMDetector(nn.Module):
    def __init__(self, input_channels=3, window_size=200, num_classes=2,
                 cnn_filters=[32, 64, 128], lstm_hidden=64, lstm_layers=2,
                 dropout=0.3):
        super(CNNLSTMDetector, self).__init__()

        self.input_channels = input_channels
        self.window_size = window_size
        self.num_classes = num_classes

        self.conv_layers = nn.Sequential(
            nn.Conv1d(input_channels, cnn_filters[0], kernel_size=3, padding=1),
            nn.BatchNorm1d(cnn_filters[0]),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Dropout(dropout),

            nn.Conv1d(cnn_filters[0], cnn_filters[1], kernel_size=3, padding=1),
            nn.BatchNorm1d(cnn_filters[1]),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Dropout(dropout),

            nn.Conv1d(cnn_filters[1], cnn_filters[2], kernel_size=3, padding=1),
            nn.BatchNorm1d(cnn_filters[2]),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Dropout(dropout),
        )

        self.lstm = nn.LSTM(
            input_size=cnn_filters[2],
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if lstm_layers > 1 else 0
        )

        self.fc_layers = nn.Sequential(
            nn.Linear(lstm_hidden * 2, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, num_classes)
        )

        self.attention = nn.Sequential(
            nn.Linear(lstm_hidden * 2, 32),
            nn.Tanh(),
            nn.Linear(32, 1)
        )

    def forward(self, x):
        x = x.permute(0, 2, 1)
        cnn_out = self.conv_layers(x)
        cnn_out = cnn_out.permute(0, 2, 1)

        lstm_out, _ = self.lstm(cnn_out)

        attention_weights = self.attention(lstm_out)
        attention_weights = torch.softmax(attention_weights, dim=1)
        context = torch.sum(lstm_out * attention_weights, dim=1)

        logits = self.fc_layers(context)

        return logits, attention_weights.squeeze(-1)


class DeepLearningPDetector:
    def __init__(self, model_path=None, window_size=200, sampling_rate=100.0,
                 device='cpu', threshold=0.5):
        self.window_size = window_size
        self.sampling_rate = sampling_rate
        self.device = torch.device(device)
        self.threshold = threshold
        self.model = None
        self.is_trained = False

        self.model = CNNLSTMDetector(
            input_channels=3,
            window_size=window_size,
            num_classes=2
        ).to(self.device)

        if model_path is not None:
            self.load_model(model_path)

    def preprocess_waveform(self, data):
        data = np.array(data)
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        npts, ncomp = data.shape
        processed = np.zeros_like(data)

        for i in range(ncomp):
            comp_data = data[:, i]
            comp_data = comp_data - np.mean(comp_data)
            comp_data = comp_data / (np.std(comp_data) + 1e-10)
            processed[:, i] = comp_data

        if processed.shape[1] == 1:
            processed = np.tile(processed, (1, 3))

        return processed

    def extract_windows(self, data, step_size=10):
        npts = data.shape[0]
        windows = []
        indices = []

        for start in range(0, npts - self.window_size + 1, step_size):
            end = start + self.window_size
            window = data[start:end, :]
            windows.append(window)
            indices.append((start, end))

        return np.array(windows), indices

    def detect_p_arrival(self, data, times=None, batch_size=32):
        processed = self.preprocess_waveform(data)
        windows, indices = self.extract_windows(processed, step_size=5)

        if len(windows) == 0:
            return []

        self.model.eval()
        all_probs = []
        all_attentions = []

        with torch.no_grad():
            for i in range(0, len(windows), batch_size):
                batch = torch.FloatTensor(windows[i:i+batch_size]).to(self.device)
                logits, attention = self.model(batch)
                probs = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
                all_probs.extend(probs)
                all_attentions.extend(attention.cpu().numpy())

        all_probs = np.array(all_probs)
        all_attentions = np.array(all_attentions)

        detections = []
        i = 0
        while i < len(all_probs):
            if all_probs[i] >= self.threshold:
                peak_start = i
                peak_prob = all_probs[i]
                peak_idx = i

                while i < len(all_probs) and all_probs[i] >= self.threshold * 0.5:
                    if all_probs[i] > peak_prob:
                        peak_prob = all_probs[i]
                        peak_idx = i
                    i += 1

                start, end = indices[peak_idx]
                attn = all_attentions[peak_idx]
                rel_pos = np.argmax(attn) / len(attn)
                exact_idx = int(start + rel_pos * (end - start))

                arrival_time = exact_idx / self.sampling_rate if times is None else times[exact_idx]

                detections.append({
                    'arrival_idx': exact_idx,
                    'arrival_time': arrival_time,
                    'confidence': float(peak_prob),
                    'method': 'cnn_lstm',
                    'attention_weights': attn,
                    'window_start': start,
                    'window_end': end
                })
            else:
                i += 1

        detections = self._deduplicate_detections(detections)
        return detections

    def _deduplicate_detections(self, detections, time_tolerance=1.0):
        if len(detections) <= 1:
            return detections

        detections = sorted(detections, key=lambda x: x['arrival_time'])
        deduplicated = []

        current_group = [detections[0]]
        for det in detections[1:]:
            if det['arrival_time'] - current_group[-1]['arrival_time'] <= time_tolerance:
                current_group.append(det)
            else:
                best = max(current_group, key=lambda x: x['confidence'])
                deduplicated.append(best)
                current_group = [det]

        if current_group:
            best = max(current_group, key=lambda x: x['confidence'])
            deduplicated.append(best)

        return deduplicated

    def train(self, train_loader, val_loader, num_epochs=50, learning_rate=0.001,
              class_weights=None, save_path='best_model.pth'):
        if class_weights is not None:
            class_weights = torch.FloatTensor(class_weights).to(self.device)
            criterion = nn.CrossEntropyLoss(weight=class_weights)
        else:
            criterion = nn.CrossEntropyLoss()

        optimizer = optim.Adam(self.model.parameters(), lr=learning_rate, weight_decay=1e-5)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=5, factor=0.5)

        best_val_acc = 0.0
        train_losses = []
        val_losses = []

        for epoch in range(num_epochs):
            self.model.train()
            total_loss = 0.0
            correct = 0
            total = 0

            for batch_idx, (data, target) in enumerate(train_loader):
                data, target = data.to(self.device), target.squeeze().to(self.device)

                optimizer.zero_grad()
                logits, _ = self.model(data)
                loss = criterion(logits, target)
                loss.backward()
                optimizer.step()

                total_loss += loss.item()
                _, predicted = torch.max(logits, 1)
                correct += (predicted == target).sum().item()
                total += target.size(0)

            train_loss = total_loss / len(train_loader)
            train_acc = correct / total
            train_losses.append(train_loss)

            val_loss, val_acc = self._validate(val_loader, criterion)
            val_losses.append(val_loss)

            scheduler.step(val_loss)

            print(f'Epoch {epoch+1}/{num_epochs}: '
                  f'Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}, '
                  f'Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}')

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                self.save_model(save_path)
                print(f'  -> 保存最优模型 (验证准确率: {best_val_acc:.4f})')

        self.is_trained = True
        return {
            'train_losses': train_losses,
            'val_losses': val_losses,
            'best_val_acc': best_val_acc
        }

    def _validate(self, val_loader, criterion):
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0

        with torch.no_grad():
            for data, target in val_loader:
                data, target = data.to(self.device), target.squeeze().to(self.device)
                logits, _ = self.model(data)
                loss = criterion(logits, target)

                total_loss += loss.item()
                _, predicted = torch.max(logits, 1)
                correct += (predicted == target).sum().item()
                total += target.size(0)

        return total_loss / len(val_loader), correct / total

    def save_model(self, path):
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'window_size': self.window_size,
            'sampling_rate': self.sampling_rate,
            'threshold': self.threshold
        }, path)
        print(f'模型已保存到: {path}')

    def load_model(self, path):
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.window_size = checkpoint.get('window_size', self.window_size)
        self.sampling_rate = checkpoint.get('sampling_rate', self.sampling_rate)
        self.threshold = checkpoint.get('threshold', self.threshold)
        self.is_trained = True
        print(f'模型已加载: {path}')

    def generate_synthetic_training_data(self, num_samples=1000, noise_level=0.5):
        waveforms = []
        labels = []

        for _ in range(num_samples // 2):
            waveform = self._generate_p_waveform()
            waveforms.append(waveform)
            labels.append(1)

        for _ in range(num_samples // 2):
            waveform = self._generate_noise_waveform(noise_level)
            waveforms.append(waveform)
            labels.append(0)

        indices = np.random.permutation(len(waveforms))
        waveforms = [waveforms[i] for i in indices]
        labels = [labels[i] for i in indices]

        return np.array(waveforms), np.array(labels)

    def _generate_p_waveform(self):
        data = np.zeros((self.window_size, 3))
        data += 0.01 * np.random.randn(self.window_size, 3)

        p_idx = np.random.randint(self.window_size // 4, 3 * self.window_size // 4)
        p_len = min(30, self.window_size - p_idx)

        t = np.arange(p_len) / self.sampling_rate
        envelope = (1 - np.exp(-t / 0.05)) * np.exp(-t / 0.3)
        amp = np.random.uniform(0.1, 0.5)

        inc = np.radians(np.random.uniform(10, 70))
        az = np.radians(np.random.uniform(0, 360))

        data[p_idx:p_idx+p_len, 0] += amp * envelope * np.cos(inc)
        data[p_idx:p_idx+p_len, 1] += amp * envelope * np.sin(inc) * np.cos(az)
        data[p_idx:p_idx+p_len, 2] += amp * envelope * np.sin(inc) * np.sin(az)

        return data

    def _generate_noise_waveform(self, noise_level=0.5):
        data = np.random.randn(self.window_size, 3) * noise_level * 0.1

        for i in range(3):
            b, a = butter(4, [0.5, 20.0], btype='band', fs=self.sampling_rate)
            data[:, i] = filtfilt(b, a, data[:, i])

        return data


def create_pretrained_detector(window_size=200, sampling_rate=100.0):
    detector = DeepLearningPDetector(window_size=window_size, sampling_rate=sampling_rate)

    print("正在生成合成数据并预训练模型...")
    waveforms, labels = detector.generate_synthetic_training_data(num_samples=2000)

    split = int(0.8 * len(waveforms))
    train_waveforms, val_waveforms = waveforms[:split], waveforms[split:]
    train_labels, val_labels = labels[:split], labels[split:]

    train_dataset = EarthquakeDataset(train_waveforms, train_labels, window_size)
    val_dataset = EarthquakeDataset(val_waveforms, val_labels, window_size)

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)

    class_counts = np.bincount(train_labels)
    class_weights = len(train_labels) / (2 * class_counts)

    detector.train(
        train_loader, val_loader,
        num_epochs=20,
        learning_rate=0.001,
        class_weights=class_weights,
        save_path='pretrained_detector.pth'
    )

    return detector


def hybrid_detection(sta_lta_detections, dl_detections, time_tolerance=1.0):
    all_detections = sta_lta_detections + dl_detections

    for det in all_detections:
        if 'method' not in det:
            det['method'] = 'sta_lta'
        if 'overall_confidence' not in det:
            conf = det.get('confidence', 0.5)
            det['overall_confidence'] = conf

    if len(all_detections) <= 1:
        return all_detections

    all_detections = sorted(all_detections, key=lambda x: x['arrival_time'])
    merged = []

    current_group = [all_detections[0]]
    for det in all_detections[1:]:
        if det['arrival_time'] - current_group[-1]['arrival_time'] <= time_tolerance:
            current_group.append(det)
        else:
            merged.append(_merge_group(current_group))
            current_group = [det]

    if current_group:
        merged.append(_merge_group(current_group))

    return merged


def _merge_group(group):
    if len(group) == 1:
        return group[0]

    has_sta_lta = any(d['method'] == 'sta_lta' for d in group)
    has_dl = any(d['method'] == 'cnn_lstm' for d in group)

    best = max(group, key=lambda x: x.get('overall_confidence', 0))
    merged = best.copy()

    if has_sta_lta and has_dl:
        merged['method'] = 'hybrid'
        merged['overall_confidence'] = min(0.99, merged.get('overall_confidence', 0) * 1.2)

    methods = sorted(list(set(d['method'] for d in group)))
    merged['detection_methods'] = methods

    avg_time = np.mean([d['arrival_time'] for d in group])
    merged['arrival_time'] = avg_time

    return merged
