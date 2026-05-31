import yaml
import os
from typing import Dict, Any


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return config


def save_config(config: Dict[str, Any], config_path: str) -> None:
    """Save configuration to YAML file."""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def get_default_config() -> Dict[str, Any]:
    """Get default configuration."""
    return {
        "audio": {
            "sampling_rate": 22050,
            "filter_length": 1024,
            "hop_length": 256,
            "win_length": 1024,
            "n_mel_channels": 80,
            "mel_fmin": 0.0,
            "mel_fmax": 8000.0,
            "max_wav_value": 32768.0,
        },
        "model": {
            "type": "tacotron2",
            "n_symbols": 148,
            "symbols_embedding_dim": 512,
            "encoder_kernel_size": 5,
            "encoder_n_convolutions": 3,
            "encoder_embedding_dim": 512,
            "decoder_rnn_dim": 1024,
            "prenet_dim": 256,
            "max_decoder_steps": 1000,
            "gate_threshold": 0.5,
            "p_attention_dropout": 0.1,
            "p_decoder_dropout": 0.1,
            "attention_rnn_dim": 1024,
            "attention_dim": 128,
            "attention_location_n_filters": 32,
            "attention_location_kernel_size": 31,
            "n_frames_per_step": 1,
            "postnet_embedding_dim": 512,
            "postnet_kernel_size": 5,
            "postnet_n_convolutions": 5,
        },
        "reference_encoder": {
            "ref_enc_filters": [32, 32, 64, 64, 128, 128],
            "ref_enc_size": [3, 3],
            "ref_enc_strides": [2, 2],
            "ref_enc_pad": [1, 1],
            "ref_enc_gru_size": 128,
            "style_embedding_dim": 128,
            "num_heads": 4,
        },
        "emotion": {
            "emotions": ["neutral", "happy", "sad", "angry", "surprise"],
            "emotion_embedding_dim": 64,
            "prosody_dim": 3,
            "min_intensity": 0.0,
            "max_intensity": 1.0,
        },
        "vocoder": {
            "type": "waveglow",
            "n_mel_channels": 80,
            "n_flows": 12,
            "n_group": 8,
            "n_early_every": 4,
            "n_early_size": 2,
            "WN_config": {
                "n_layers": 8,
                "n_channels": 256,
                "kernel_size": 3,
            },
        },
        "speaker_adaptation": {
            "adapter_type": "dvector",
            "dvector_dim": 256,
            "num_speakers": 100,
            "fine_tune_steps": 100,
            "learning_rate": 0.0001,
        },
        "classifier": {
            "type": "cnn",
            "num_classes": 5,
            "hidden_dim": 256,
            "dropout": 0.3,
        },
        "training": {
            "batch_size": 32,
            "learning_rate": 0.001,
            "epochs": 100,
            "weight_decay": 0.000001,
            "grad_clip_thresh": 1.0,
            "seed": 1234,
        },
        "inference": {
            "gate_threshold": 0.5,
            "max_decoder_steps": 1000,
            "do_trim_silence": True,
            "trim_silence_threshold": 45,
        },
        "paths": {
            "checkpoints_dir": "./checkpoints",
            "output_dir": "./output",
            "data_dir": "./data",
            "reference_dir": "./reference_audio",
            "pretrained_models": "./pretrained",
        },
        "logging": {
            "log_interval": 100,
            "save_interval": 1000,
            "val_interval": 1000,
        },
    }
