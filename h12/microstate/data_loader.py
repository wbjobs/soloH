import numpy as np
import mne


class EEGDataLoader:
    def __init__(self):
        self.raw = None
        self.data = None
        self.ch_names = None
        self.sfreq = None
        self.n_channels = None
        self.times = None

    def load_edf(self, filepath):
        self.raw = mne.io.read_raw_edf(filepath, preload=True, verbose=False)
        
        eeg_indices = mne.pick_types(self.raw.info, meg=False, eeg=True, 
                                     stim=False, eog=False, ecg=False)
        
        if len(eeg_indices) < 32:
            raise ValueError(f"EEG数据需要至少32个通道，当前只有{len(eeg_indices)}个EEG通道")
        
        self.raw.pick_channels([self.raw.ch_names[i] for i in eeg_indices[:32]])
        
        self.sfreq = self.raw.info['sfreq']
        if self.sfreq < 250:
            raise ValueError(f"采样率需要≥250Hz，当前为{self.sfreq}Hz")
        
        self.data = self.raw.get_data()
        self.ch_names = self.raw.ch_names
        self.n_channels = len(self.ch_names)
        self.times = self.raw.times
        
        return self.data, self.ch_names, self.sfreq, self.times

    def get_channel_positions(self):
        if self.raw is None:
            raise ValueError("请先加载EEG数据")
        
        montage = mne.channels.make_standard_montage('standard_1020')
        self.raw.set_montage(montage, match_case=False, on_missing='warn')
        
        pos = np.array([self.raw.info['chs'][i]['loc'][:2] 
                        for i in range(self.n_channels)])
        return pos

    def get_info(self):
        return {
            'n_channels': self.n_channels,
            'sfreq': self.sfreq,
            'ch_names': self.ch_names,
            'duration': self.times[-1] if self.times is not None else 0,
            'n_samples': self.data.shape[1] if self.data is not None else 0
        }
