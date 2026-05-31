import click
import os
import json
import torch
import numpy as np
from typing import List, Optional, Dict, Tuple, Union
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .tts_engine import TTSEngine, SynthesisResult


def parse_emotion(ctx, param, value):
    if value is None:
        return None
    
    if "+" in value:
        emotion_dict = {}
        total_weight = 0.0
        for part in value.split("+"):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                e, w = part.rsplit(":", 1)
                emotion_dict[e.strip()] = float(w)
                total_weight += float(w)
            else:
                emotion_dict[part] = 1.0
                total_weight += 1.0
        
        if total_weight > 0 and abs(total_weight - 1.0) > 1e-6:
            emotion_dict = {k: v / total_weight for k, v in emotion_dict.items()}
        return emotion_dict
    elif ":" in value:
        parts = value.rsplit(":", 1)
        return parts[0], float(parts[1])
    else:
        return value


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default="config.yaml",
    help="Path to configuration file.",
)
@click.option(
    "--device",
    "-d",
    type=click.Choice(["cpu", "cuda"]),
    default=None,
    help="Device to use for inference.",
)
@click.option(
    "--vocoder",
    "-v",
    type=click.Choice(["waveglow", "hifigan"]),
    default="waveglow",
    help="Vocoder type to use.",
)
@click.pass_context
def cli(ctx, config, device, vocoder):
    """Emotional Text-to-Speech Command Line Tool."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["device"] = device
    ctx.obj["vocoder"] = vocoder


@cli.command()
@click.option(
    "--text",
    "-t",
    type=str,
    required=True,
    help="Text to synthesize.",
)
@click.option(
    "--emotion",
    "-e",
    type=str,
    required=True,
    callback=parse_emotion,
    help="Emotion label. Format: 'happy', 'happy:0.8', 'happy:0.7+surprise:0.3'",
)
@click.option(
    "--intensity",
    "-i",
    type=float,
    default=1.0,
    help="Emotion intensity (0.0 - 1.0).",
)
@click.option(
    "--reference-audio",
    "-r",
    type=click.Path(exists=True),
    default=None,
    help="Reference audio path for style encoding.",
)
@click.option(
    "--speaker-audio",
    "-s",
    type=click.Path(exists=True),
    multiple=True,
    help="Target speaker audio paths for speaker adaptation.",
)
@click.option(
    "--speaker-text",
    "-st",
    type=str,
    multiple=True,
    help="Transcripts for speaker adaptation audios.",
)
@click.option(
    "--fine-tune/--no-fine-tune",
    default=False,
    help="Whether to fine-tune for speaker adaptation.",
)
@click.option(
    "--pitch-shift",
    type=float,
    default=0.0,
    help="Pitch shift in semitones.",
)
@click.option(
    "--energy-scale",
    type=float,
    default=1.0,
    help="Energy scaling factor.",
)
@click.option(
    "--duration-scale",
    type=float,
    default=1.0,
    help="Duration scaling factor.",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Validate synthesized speech with emotion classifier.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="./output",
    help="Output directory.",
)
@click.option(
    "--output-filename",
    "-f",
    type=str,
    default=None,
    help="Output filename.",
)
@click.option(
    "--tacotron-path",
    type=click.Path(exists=True),
    default=None,
    help="Path to pretrained Tacotron2 model.",
)
@click.option(
    "--reference-encoder-path",
    type=click.Path(exists=True),
    default=None,
    help="Path to pretrained reference encoder.",
)
@click.option(
    "--vocoder-path",
    type=click.Path(exists=True),
    default=None,
    help="Path to pretrained vocoder model.",
)
@click.option(
    "--emotion-embedding-path",
    type=click.Path(exists=True),
    default=None,
    help="Path to pretrained emotion embeddings.",
)
@click.option(
    "--classifier-path",
    type=click.Path(exists=True),
    default=None,
    help="Path to pretrained emotion classifier.",
)
@click.pass_context
def synthesize(
    ctx,
    text,
    emotion,
    intensity,
    reference_audio,
    speaker_audio,
    speaker_text,
    fine_tune,
    pitch_shift,
    energy_scale,
    duration_scale,
    validate,
    output_dir,
    output_filename,
    tacotron_path,
    reference_encoder_path,
    vocoder_path,
    emotion_embedding_path,
    classifier_path,
):
    """Synthesize speech with specified emotion."""
    click.echo(f"Initializing TTS Engine...")
    engine = TTSEngine(
        config_path=ctx.obj["config_path"],
        device=ctx.obj["device"],
        vocoder_type=ctx.obj["vocoder"],
    )
    
    if any([tacotron_path, reference_encoder_path, vocoder_path, emotion_embedding_path, classifier_path]):
        click.echo("Loading pretrained models...")
        engine.load_pretrained_models(
            tacotron_path=tacotron_path,
            reference_encoder_path=reference_encoder_path,
            vocoder_path=vocoder_path,
            emotion_embedding_path=emotion_embedding_path,
            classifier_path=classifier_path,
        )
    
    if isinstance(emotion, tuple):
        emotion_label, intensity_from_label = emotion
        intensity = intensity if intensity != 1.0 else intensity_from_label
    else:
        emotion_label = emotion
    
    click.echo(f"Text: {text}")
    if isinstance(emotion_label, dict):
        emotion_str = " + ".join([f"{k}:{v:.2f}" for k, v in emotion_label.items()])
        click.echo(f"Emotion: {emotion_str}")
    else:
        click.echo(f"Emotion: {emotion_label}")
    click.echo(f"Intensity: {intensity}")
    
    speaker_audio_list = list(speaker_audio) if speaker_audio else None
    speaker_text_list = list(speaker_text) if speaker_text else None
    
    os.makedirs(output_dir, exist_ok=True)
    
    with click.progressbar(length=1, label="Synthesizing") as bar:
        result = engine.synthesize(
            text=text,
            emotion=emotion_label,
            intensity=intensity,
            reference_audio=reference_audio,
            speaker_audio=speaker_audio_list,
            speaker_texts=speaker_text_list,
            do_fine_tuning=fine_tune,
            validate=validate,
            pitch_shift=pitch_shift,
            energy_scale=energy_scale,
            duration_scale=duration_scale,
            output_dir=output_dir,
            output_filename=output_filename,
        )
        bar.update(1)
    
    click.echo(f"\n✓ Synthesis complete!")
    click.echo(f"  Output: {result.output_path}")
    click.echo(f"  Duration: {len(result.wav) / result.sampling_rate:.2f}s")
    click.echo(f"  Sampling Rate: {result.sampling_rate} Hz")
    
    if result.validation_result:
        click.echo(f"\nValidation Results:")
        val = result.validation_result
        click.echo(f"  Quality Score: {val['quality_score']:.4f}")
        click.echo(f"  Target Emotion Match: {'✓' if val['target_emotion_match'] else '✗'}")
        click.echo(f"  Target Probability: {val['target_probability']:.4f}")
        click.echo(f"  Predicted Emotion: {val['predicted_emotion']}")
        click.echo(f"  Predicted Confidence: {val['predicted_confidence']:.4f}")
        click.echo(f"  Acceptable: {'✓' if val['is_acceptable'] else '✗'}")
    
    meta_path = os.path.splitext(result.output_path)[0] + "_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    click.echo(f"\nMetadata saved to: {meta_path}")


@cli.command()
@click.option(
    "--wav-path",
    "-w",
    type=click.Path(exists=True),
    required=True,
    help="Path to WAV file to validate.",
)
@click.option(
    "--target-emotion",
    "-e",
    type=str,
    required=True,
    help="Target emotion label.",
)
@click.option(
    "--target-intensity",
    "-i",
    type=float,
    default=1.0,
    help="Target emotion intensity.",
)
@click.option(
    "--classifier-path",
    type=click.Path(exists=True),
    default=None,
    help="Path to pretrained emotion classifier.",
)
@click.pass_context
def validate(ctx, wav_path, target_emotion, target_intensity, classifier_path):
    """Validate synthesized speech emotion."""
    click.echo(f"Initializing validator...")
    engine = TTSEngine(
        config_path=ctx.obj["config_path"],
        device=ctx.obj["device"],
        vocoder_type=ctx.obj["vocoder"],
    )
    
    if classifier_path:
        engine.validator.load_classifier_weights(classifier_path)
    
    click.echo(f"Validating: {wav_path}")
    click.echo(f"Target Emotion: {target_emotion}")
    click.echo(f"Target Intensity: {target_intensity}")
    
    result = engine.validate_synthesis(wav_path, target_emotion, target_intensity)
    
    click.echo(f"\nValidation Results:")
    click.echo(f"  Quality Score: {result['quality_score']:.4f}")
    click.echo(f"  Target Emotion Match: {'✓' if result['target_emotion_match'] else '✗'}")
    click.echo(f"  Target Probability: {result['target_probability']:.4f}")
    click.echo(f"  Predicted Emotion: {result['predicted_emotion']}")
    click.echo(f"  Predicted Confidence: {result['predicted_confidence']:.4f}")
    click.echo(f"  Acceptable: {'✓' if result['is_acceptable'] else '✗'} (threshold: {result['threshold']})")
    
    if "all_probabilities" in result:
        click.echo(f"\nAll Emotion Probabilities:")
        for emotion, prob in result["all_probabilities"].items():
            bar = "█" * int(prob * 20)
            click.echo(f"  {emotion:10s}: {prob:.4f} {bar}")


@cli.command()
@click.option(
    "--reference-audio",
    "-r",
    type=click.Path(exists=True),
    multiple=True,
    required=True,
    help="Reference audio paths for speaker adaptation.",
)
@click.option(
    "--reference-text",
    "-t",
    type=str,
    multiple=True,
    help="Transcripts for reference audios (required for fine-tuning).",
)
@click.option(
    "--emotion",
    "-e",
    type=str,
    default=None,
    callback=parse_emotion,
    help="Emotion for speaker adaptation.",
)
@click.option(
    "--fine-tune/--no-fine-tune",
    default=True,
    help="Whether to fine-tune the model.",
)
@click.option(
    "--save-path",
    "-s",
    type=click.Path(),
    default=None,
    help="Path to save speaker embedding.",
)
@click.option(
    "--tacotron-path",
    type=click.Path(exists=True),
    default=None,
    help="Path to pretrained Tacotron2 model.",
)
@click.option(
    "--emotion-embedding-path",
    type=click.Path(exists=True),
    default=None,
    help="Path to pretrained emotion embeddings.",
)
@click.pass_context
def adapt(
    ctx,
    reference_audio,
    reference_text,
    emotion,
    fine_tune,
    save_path,
    tacotron_path,
    emotion_embedding_path,
):
    """Perform speaker adaptation from reference audio."""
    click.echo(f"Initializing speaker adaptation...")
    engine = TTSEngine(
        config_path=ctx.obj["config_path"],
        device=ctx.obj["device"],
        vocoder_type=ctx.obj["vocoder"],
    )
    
    if tacotron_path or emotion_embedding_path:
        engine.load_pretrained_models(
            tacotron_path=tacotron_path,
            emotion_embedding_path=emotion_embedding_path,
        )
    
    reference_audios = list(reference_audio)
    reference_texts = list(reference_text) if reference_text else None
    
    click.echo(f"Reference Audios: {len(reference_audios)} file(s)")
    for i, audio in enumerate(reference_audios):
        click.echo(f"  [{i+1}] {audio}")
    
    emotion_emb = None
    if emotion:
        if isinstance(emotion, tuple):
            emotion_label, intensity = emotion
            emotion_emb, _ = engine.emotion_controller.process_emotion_input(
                emotion_label, intensity
            )
        else:
            emotion_emb, _ = engine.emotion_controller.process_emotion_input(
                emotion, 1.0
            )
        click.echo(f"Emotion for adaptation: {emotion}")
    
    click.echo(f"\nPerforming speaker adaptation...")
    with click.progressbar(length=1, label="Adapting") as bar:
        speaker_embedding, fine_tune_stats = engine.adapt_speaker(
            reference_audio_paths=reference_audios,
            reference_texts=reference_texts,
            emotion_embedding=emotion_emb,
            do_fine_tuning=fine_tune,
            save_path=save_path,
        )
        bar.update(1)
    
    click.echo(f"\n✓ Speaker adaptation complete!")
    click.echo(f"  Speaker embedding shape: {speaker_embedding.shape}")
    
    if fine_tune_stats:
        click.echo(f"\nFine-tuning Statistics:")
        click.echo(f"  Steps: {fine_tune_stats['steps']}")
        click.echo(f"  Final Loss: {fine_tune_stats['final_loss']:.6f}")
        click.echo(f"  Average Loss: {fine_tune_stats['average_loss']:.6f}")
        click.echo(f"  Min Loss: {fine_tune_stats['min_loss']:.6f}")
    
    if save_path:
        click.echo(f"\nSpeaker embedding saved to: {save_path}")
    
    return speaker_embedding


@cli.command()
def list_emotions():
    """List available emotion labels."""
    config_path = os.path.join(os.getcwd(), "config.yaml")
    if os.path.exists(config_path):
        from src.utils.config import load_config
        config = load_config(config_path)
        emotions = config["emotion"]["emotions"]
        
        click.echo("Available Emotions:")
        for i, emotion in enumerate(emotions, 1):
            click.echo(f"  {i}. {emotion}")
        
        click.echo("\nUsage Examples:")
        click.echo("  Single emotion:    --emotion happy")
        click.echo("  With intensity:    --emotion happy:0.8")
        click.echo("  Mixed emotions:    --emotion happy:0.7+surprise:0.3")
    else:
        click.echo("Error: config.yaml not found in current directory.")


@cli.command()
@click.option(
    "--source-emotion-audio",
    "-se",
    type=str,
    required=True,
    help="Path to source audio with the emotion to transfer.",
)
@click.option(
    "--target-speaker-audio",
    "-ts",
    type=str,
    required=True,
    help="Path to target speaker audio (neutral voice).",
)
@click.option(
    "--text",
    "-t",
    type=str,
    required=True,
    help="Text to synthesize with transferred emotion.",
)
@click.option(
    "--emotion",
    "-e",
    type=str,
    default=None,
    callback=parse_emotion,
    help="Reference emotion label (overrides source audio emotion).",
)
@click.option(
    "--intensity",
    "-i",
    type=float,
    default=1.0,
    help="Emotion intensity (0.0-1.0).",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Validate synthesized emotion.",
)
@click.option(
    "--output-dir",
    "-o",
    type=str,
    default=None,
    help="Output directory for WAV file.",
)
@click.option(
    "--output-filename",
    "-of",
    type=str,
    default=None,
    help="Output filename.",
)
@click.pass_context
def transfer(
    ctx,
    source_emotion_audio: str,
    target_speaker_audio: str,
    text: str,
    emotion: Union[str, Dict[str, float]],
    intensity: float,
    validate: bool,
    output_dir: Optional[str],
    output_filename: Optional[str],
):
    """Transfer emotion from source audio to target speaker's voice."""
    engine = ctx.obj.get("engine")
    if engine is None:
        config_path = ctx.obj.get("config_path", "config.yaml")
        device = ctx.obj.get("device")
        vocoder_type = ctx.obj.get("vocoder_type", "waveglow")
        engine = TTSEngine(config_path, device, vocoder_type)
    
    if output_dir is None:
        output_dir = engine.output_dir
    
    try:
        result = engine.transfer_emotion(
            source_emotion_audio=source_emotion_audio,
            target_speaker_audio=target_speaker_audio,
            text=text,
            emotion_intensity=intensity,
            reference_emotion=emotion,
            validate=validate,
            output_dir=output_dir,
            output_filename=output_filename,
        )
        
        click.echo("✓ Emotion transfer completed!")
        click.echo(f"  Output: {result.output_path}")
        click.echo(f"  Duration: {len(result.wav) / result.sampling_rate:.2f}s")
        
        if result.validation_result:
            click.echo(f"  Quality Score: {result.validation_result['quality_score']:.3f}")
            click.echo(f"  Emotion Match: {result.validation_result['target_emotion_match']}")
        
    except Exception as e:
        click.echo(f"✗ Error during emotion transfer: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise click.Abort()


@cli.command()
@click.option(
    "--neutral-audio",
    "-na",
    type=str,
    required=True,
    help="Path to neutral input audio.",
)
@click.option(
    "--emotion",
    "-e",
    type=str,
    required=True,
    callback=parse_emotion,
    help="Target emotion label.",
)
@click.option(
    "--intensity",
    "-i",
    type=float,
    default=1.0,
    help="Emotion intensity (0.0-1.0).",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Validate converted emotion.",
)
@click.option(
    "--output-dir",
    "-o",
    type=str,
    default=None,
    help="Output directory for WAV file.",
)
@click.option(
    "--output-filename",
    "-of",
    type=str,
    default=None,
    help="Output filename.",
)
@click.pass_context
def convert(
    ctx,
    neutral_audio: str,
    emotion: Union[str, Dict[str, float]],
    intensity: float,
    validate: bool,
    output_dir: Optional[str],
    output_filename: Optional[str],
):
    """Add emotion to neutral voice audio."""
    engine = ctx.obj.get("engine")
    if engine is None:
        config_path = ctx.obj.get("config_path", "config.yaml")
        device = ctx.obj.get("device")
        vocoder_type = ctx.obj.get("vocoder_type", "waveglow")
        engine = TTSEngine(config_path, device, vocoder_type)
    
    if output_dir is None:
        output_dir = engine.output_dir
    
    try:
        result = engine.convert_voice_emotion(
            neutral_audio_path=neutral_audio,
            target_emotion=emotion,
            emotion_intensity=intensity,
            validate=validate,
            output_dir=output_dir,
            output_filename=output_filename,
        )
        
        click.echo("✓ Emotion conversion completed!")
        click.echo(f"  Output: {result.output_path}")
        click.echo(f"  Duration: {len(result.wav) / result.sampling_rate:.2f}s")
        click.echo(f"  Target Emotion: {result.emotion}")
        click.echo(f"  Intensity: {result.emotion_intensity:.2f}")
        
        if result.validation_result:
            click.echo(f"  Quality Score: {result.validation_result['quality_score']:.3f}")
            click.echo(f"  Emotion Match: {result.validation_result['target_emotion_match']}")
        
    except Exception as e:
        click.echo(f"✗ Error during emotion conversion: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise click.Abort()


@cli.command()
@click.option(
    "--audio",
    "-a",
    type=str,
    required=True,
    help="Path to audio file to analyze.",
)
@click.option(
    "--output-format",
    "-f",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze(ctx, audio: str, output_format: str):
    """Analyze audio to detect emotion and disentangle content/style."""
    engine = ctx.obj.get("engine")
    if engine is None:
        config_path = ctx.obj.get("config_path", "config.yaml")
        device = ctx.obj.get("device")
        vocoder_type = ctx.obj.get("vocoder_type", "waveglow")
        engine = TTSEngine(config_path, device, vocoder_type)
    
    try:
        analysis = engine.analyze_audio_emotion(audio)
        
        if output_format == "json":
            result_json = {
                "predicted_emotion": analysis["predicted_emotion"],
                "confidence": analysis["confidence"],
                "emotion_similarities": analysis["emotion_similarities"],
                "content_shape": analysis["content_representation"].shape,
                "emotion_embedding_shape": analysis["emotion_embedding"].shape,
                "speaker_embedding_shape": analysis["speaker_embedding"].shape,
            }
            click.echo(json.dumps(result_json, indent=2))
        else:
            click.echo("Audio Analysis Result:")
            click.echo(f"  Predicted Emotion: {analysis['predicted_emotion']}")
            click.echo(f"  Confidence: {analysis['confidence']:.3f}")
            click.echo("")
            click.echo("  Emotion Similarities:")
            for emotion, sim in analysis["emotion_similarities"].items():
                bar = "█" * int(sim * 20)
                click.echo(f"    {emotion:<10} {bar} {sim:.3f}")
            click.echo("")
            click.echo("  Disentangled Representations:")
            click.echo(f"    Content: shape={analysis['content_representation'].shape}")
            click.echo(f"    Emotion: shape={analysis['emotion_embedding'].shape}")
            click.echo(f"    Speaker: shape={analysis['speaker_embedding'].shape}")
        
    except Exception as e:
        click.echo(f"✗ Error during audio analysis: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise click.Abort()


@cli.command()
def version():
    """Show version information."""
    click.echo("Emotional TTS Tool v1.1.0")
    click.echo("A Python command-line tool for emotional speech synthesis.")
    click.echo("")
    click.echo("Features:")
    click.echo("  • Tacotron2 + WaveGlow/HiFi-GAN architecture")
    click.echo("  • Emotion control via reference encoder or prosody parameters")
    click.echo("  • Emotion intensity control (0-1) with saturation")
    click.echo("  • Mixed emotion support (e.g., 70% happy + 30% surprise)")
    click.echo("  • Semi-supervised emotion disentanglement (content/style)")
    click.echo("  • Multi-speaker emotion transfer (A→B)")
    click.echo("  • Voice-to-emotion conversion (neutral → emotional)")
    click.echo("  • WAV output with emotion classifier validation")
    click.echo("  • Speaker adaptation from target speaker recordings")


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
