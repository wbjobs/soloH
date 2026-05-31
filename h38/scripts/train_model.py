#!/usr/bin/env python
"""
Train CRISPR off-target prediction model using dummy data.
In production, replace with CRISOT and GUIDE-seq data.
"""
import os
import sys
import argparse
import torch
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.crispr_model import CRISPRModel, CRISPRPredictor
from app.models.model_utils import (
    create_dummy_training_data,
    train_model,
    save_model,
)
from app.config import get_settings


def main():
    parser = argparse.ArgumentParser(description="Train CRISPR off-target model")
    parser.add_argument(
        "--output-path",
        default=None,
        help="Path to save trained model",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=20,
        help="Number of training epochs",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1e-3,
        help="Learning rate",
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=5000,
        help="Number of training samples",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda"],
        help="Training device",
    )
    args = parser.parse_args()

    settings = get_settings()
    output_path = args.output_path or settings.MODEL_PATH

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print("Creating training data...")
    X_train, y_train = create_dummy_training_data(
        num_samples=args.num_samples
    )
    X_val, y_val = create_dummy_training_data(
        num_samples=args.num_samples // 5
    )

    print(f"Training data shape: {X_train.shape}")
    print(f"Training labels shape: {y_train.shape}")

    model = CRISPRModel()

    total_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {total_params:,}")

    print("\nStarting training...")
    trained_model = train_model(
        model=model,
        train_data=(X_train, y_train),
        val_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        device=args.device,
    )

    print("\nSaving model...")
    predictor = CRISPRPredictor(model=trained_model, device=args.device)
    save_model(predictor, output_path)
    print(f"Model saved to: {output_path}")

    print("\nTesting predictions...")
    test_input = X_train[:5].to(args.device)
    with torch.no_grad():
        predictions = predictor.predict(test_input)
    print(f"Sample predictions: {predictions.cpu().numpy()}")

    print("\nTraining complete!")


if __name__ == "__main__":
    main()
