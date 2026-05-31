import os
import sys
import json
import click
import numpy as np
from typing import List, Optional, Tuple

from . import utils
from .verification import SpeakerVerifier, VerificationReport
from .spoofing import SpoofingSimulator


@click.group()
@click.option('--config', '-c', default='config.yaml',
              help='配置文件路径')
@click.option('--device', '-d', default='cpu',
              type=click.Choice(['cpu', 'cuda']),
              help='计算设备 (cpu/cuda)')
@click.option('--verbose', '-v', is_flag=True, default=False,
              help='显示详细信息')
@click.pass_context
def main(ctx, config: str, device: str, verbose: bool):
    """说话人验证与反伪装检测工具"""
    ctx.ensure_object(dict)

    config_path = os.path.abspath(config)
    if os.path.exists(config_path):
        cfg = utils.load_config(config_path)
    else:
        cfg = utils.load_config()

    ctx.obj['config'] = cfg
    ctx.obj['device'] = device
    ctx.obj['verbose'] = verbose

    if verbose:
        click.echo(f"加载配置文件: {config_path}")
        click.echo(f"使用设备: {device}")


@main.command()
@click.argument('enroll_audio', nargs=-1, required=True,
                type=click.Path(exists=True))
@click.option('--model-type', '-m', default=None,
              type=click.Choice(['ecapa', 'xvector']),
              help='嵌入模型类型')
@click.option('--embedding-save', '-s', default=None,
              type=click.Path(),
              help='保存嵌入向量的路径')
@click.pass_context
def enroll(ctx, enroll_audio: List[str], model_type: Optional[str],
           embedding_save: Optional[str]):
    """注册说话人音频"""
    cfg = ctx.obj['config']
    device = ctx.obj['device']
    verbose = ctx.obj['verbose']

    if model_type is None:
        model_type = cfg['embedding']['model_type']

    if verbose:
        click.echo(f"使用模型: {model_type}")
        click.echo(f"注册音频数量: {len(enroll_audio)}")

    verifier = SpeakerVerifier(
        model_type=model_type,
        embedding_dim=cfg['embedding']['embedding_dim'],
        sample_rate=cfg['audio']['sample_rate'],
        device=device,
        phase_threshold=cfg['anti_spoofing']['phase_residual_threshold'],
        spectral_threshold=cfg['anti_spoofing']['spectral_consistency_threshold'],
        scoring=cfg['verification']['scoring'],
        threshold=cfg['verification']['threshold']
    )

    result = verifier.enroll_speaker(list(enroll_audio))

    if embedding_save:
        save_dir = os.path.dirname(embedding_save)
        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir)
        np.save(embedding_save, verifier.enrolled_embedding)
        click.echo(f"嵌入向量已保存到: {embedding_save}")

    ctx.obj['verifier'] = verifier
    ctx.obj['enrolled'] = True

    click.echo("\n" + "=" * 50)
    click.echo("说话人注册完成")
    click.echo("=" * 50)
    click.echo(f"  注册样本数: {result['num_enrollment_samples']}")
    click.echo(f"  嵌入维度: {result['embedding_dim']}")
    click.echo("=" * 50)

    return verifier


@main.command()
@click.argument('test_audio', type=click.Path(exists=True))
@click.option('--enroll-audio', '-e', multiple=True,
              type=click.Path(exists=True),
              help='注册音频文件（如果未预注册）')
@click.option('--enroll-embedding', '-em', default=None,
              type=click.Path(exists=True),
              help='预注册的嵌入向量文件')
@click.option('--model-type', '-m', default=None,
              type=click.Choice(['ecapa', 'xvector']),
              help='嵌入模型类型')
@click.option('--apply-restoration/--no-restoration', default=True,
              help='是否应用音频恢复')
@click.option('--output-format', '-o', default='text',
              type=click.Choice(['text', 'json', 'report']),
              help='输出格式')
@click.option('--output-file', '-f', default=None,
              type=click.Path(),
              help='结果输出文件路径')
@click.pass_context
def verify(ctx, test_audio: str, enroll_audio: List[str],
           enroll_embedding: Optional[str], model_type: Optional[str],
           apply_restoration: bool, output_format: str,
           output_file: Optional[str]):
    """验证测试音频是否属于注册说话人"""
    cfg = ctx.obj['config']
    device = ctx.obj['device']
    verbose = ctx.obj['verbose']

    if model_type is None:
        model_type = cfg['embedding']['model_type']

    verifier = SpeakerVerifier(
        model_type=model_type,
        embedding_dim=cfg['embedding']['embedding_dim'],
        sample_rate=cfg['audio']['sample_rate'],
        device=device,
        phase_threshold=cfg['anti_spoofing']['phase_residual_threshold'],
        spectral_threshold=cfg['anti_spoofing']['spectral_consistency_threshold'],
        scoring=cfg['verification']['scoring'],
        threshold=cfg['verification']['threshold']
    )

    if enroll_embedding:
        embedding = np.load(enroll_embedding)
        verifier.set_enrolled_embedding(embedding)
        if verbose:
            click.echo(f"加载预注册嵌入: {enroll_embedding}")
    elif enroll_audio:
        verifier.enroll_speaker(list(enroll_audio))
        if verbose:
            click.echo(f"使用注册音频: {len(enroll_audio)} 个文件")
    elif ctx.obj.get('verifier') and ctx.obj.get('enrolled'):
        verifier = ctx.obj['verifier']
    else:
        click.echo("错误: 请提供注册音频（--enroll-audio）或预注册嵌入（--enroll-embedding）",
                   err=True)
        sys.exit(1)

    if verbose:
        click.echo(f"测试音频: {test_audio}")
        click.echo(f"应用音频恢复: {apply_restoration}")

    result = verifier.verify(test_audio, apply_restoration=apply_restoration)

    if output_format == 'text':
        report = VerificationReport.generate(result)
        click.echo(report)
    elif output_format == 'json':
        output = VerificationReport.to_dict(result)
        click.echo(json.dumps(output, indent=2, ensure_ascii=False))
    elif output_format == 'report':
        report = VerificationReport.generate(result)
        click.echo(report)

    if output_file:
        save_dir = os.path.dirname(output_file)
        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir)

        if output_format == 'json':
            output = VerificationReport.to_dict(result)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
        else:
            report = VerificationReport.generate(result)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
        click.echo(f"\n结果已保存到: {output_file}")

    return result


@main.command()
@click.argument('enroll_audio', type=click.Path(exists=True))
@click.argument('test_audio', type=click.Path(exists=True))
@click.option('--spoofing-type', '-t', default='random',
              type=click.Choice(['pitch_shift', 'time_stretch',
                                 'phase_vocoder', 'replay', 'random']),
              help='伪装类型')
@click.option('--pitch-shift', '-p', default=2.0, type=float,
              help='变调半音数（用于pitch_shift和phase_vocoder）')
@click.option('--time-stretch', '-ts', default=1.0, type=float,
              help='时间拉伸比率（用于time_stretch和phase_vocoder）')
@click.option('--replay-quality', '-q', default='medium',
              type=click.Choice(['low', 'medium', 'high']),
              help='回放攻击质量')
@click.option('--model-type', '-m', default=None,
              type=click.Choice(['ecapa', 'xvector']),
              help='嵌入模型类型')
@click.option('--output-format', '-o', default='text',
              type=click.Choice(['text', 'json', 'report']),
              help='输出格式')
@click.pass_context
def simulate(ctx, enroll_audio: str, test_audio: str,
             spoofing_type: str, pitch_shift: float,
             time_stretch: float, replay_quality: str,
             model_type: Optional[str], output_format: str):
    """模拟伪装攻击并进行验证测试"""
    cfg = ctx.obj['config']
    device = ctx.obj['device']
    verbose = ctx.obj['verbose']

    if model_type is None:
        model_type = cfg['embedding']['model_type']

    if verbose:
        click.echo(f"注册音频: {enroll_audio}")
        click.echo(f"测试音频: {test_audio}")
        click.echo(f"伪装类型: {spoofing_type}")
        if spoofing_type in ['pitch_shift', 'phase_vocoder']:
            click.echo(f"变调: {pitch_shift} 半音")
        if spoofing_type in ['time_stretch', 'phase_vocoder']:
            click.echo(f"时间拉伸: {time_stretch}x")
        if spoofing_type == 'replay':
            click.echo(f"回放质量: {replay_quality}")

    verifier = SpeakerVerifier(
        model_type=model_type,
        embedding_dim=cfg['embedding']['embedding_dim'],
        sample_rate=cfg['audio']['sample_rate'],
        device=device,
        phase_threshold=cfg['anti_spoofing']['phase_residual_threshold'],
        spectral_threshold=cfg['anti_spoofing']['spectral_consistency_threshold'],
        scoring=cfg['verification']['scoring'],
        threshold=cfg['verification']['threshold']
    )

    kwargs = {}
    if spoofing_type in ['pitch_shift']:
        kwargs['n_steps'] = pitch_shift
    elif spoofing_type in ['time_stretch']:
        kwargs['rate'] = time_stretch
    elif spoofing_type in ['phase_vocoder']:
        kwargs['pitch_shift'] = pitch_shift
        kwargs['time_stretch'] = time_stretch
    elif spoofing_type == 'replay':
        kwargs['quality'] = replay_quality

    result = verifier.verify_with_spoofing_simulation(
        enroll_audio, test_audio, spoofing_type, **kwargs
    )

    click.echo("\n" + "=" * 60)
    click.echo("伪装模拟验证结果")
    click.echo("=" * 60)
    click.echo(f"\n应用的伪装: {result['applied_spoofing']['type']}")
    if 'n_steps' in result['applied_spoofing']:
        click.echo(f"变调半音数: {result['applied_spoofing']['n_steps']}")
    if 'factor' in result['applied_spoofing']:
        click.echo(f"变调因子: {result['applied_spoofing']['factor']:.4f}")
    if 'rate' in result['applied_spoofing']:
        click.echo(f"时间拉伸比率: {result['applied_spoofing']['rate']}x")
    if 'quality' in result['applied_spoofing']:
        click.echo(f"回放质量: {result['applied_spoofing']['quality']}")

    if output_format == 'text':
        report = VerificationReport.generate(result['verification'])
        click.echo(report)
    elif output_format == 'json':
        output = VerificationReport.to_dict(result['verification'])
        output['applied_spoofing'] = result['applied_spoofing']
        click.echo(json.dumps(output, indent=2, ensure_ascii=False))
    elif output_format == 'report':
        report = VerificationReport.generate(result['verification'])
        click.echo(report)

    return result


@main.command()
@click.argument('input_audio', type=click.Path(exists=True))
@click.argument('output_audio', type=click.Path())
@click.option('--transform-type', '-t', default='pitch_shift',
              type=click.Choice(['pitch_shift', 'time_stretch',
                                 'phase_vocoder', 'replay']),
              help='变换类型')
@click.option('--pitch-shift', '-p', default=2.0, type=float,
              help='变调半音数')
@click.option('--time-stretch', '-ts', default=1.2, type=float,
              help='时间拉伸比率')
@click.option('--sample-rate', '-sr', default=16000, type=int,
              help='采样率')
@click.pass_context
def transform(ctx, input_audio: str, output_audio: str,
              transform_type: str, pitch_shift: float,
              time_stretch: float, sample_rate: int):
    """对音频应用伪装变换"""
    verbose = ctx.obj['verbose']

    audio, sr = utils.load_audio(input_audio, sample_rate=sample_rate)

    simulator = SpoofingSimulator(sample_rate=sample_rate)

    if transform_type == 'pitch_shift':
        transformed, info = simulator.apply_pitch_shift_psola(audio, pitch_shift)
    elif transform_type == 'time_stretch':
        transformed, info = simulator.apply_time_stretch_resample(audio, time_stretch)
    elif transform_type == 'phase_vocoder':
        transformed, info = simulator.apply_phase_vocoder(
            audio, pitch_shift=pitch_shift, time_stretch=time_stretch
        )
    elif transform_type == 'replay':
        transformed, info = simulator.apply_replay_attack(audio, 'medium')

    save_dir = os.path.dirname(output_audio)
    if save_dir and not os.path.exists(save_dir):
        os.makedirs(save_dir)

    utils.save_audio(output_audio, transformed, sample_rate)

    click.echo(f"\n变换完成: {transform_type}")
    click.echo(f"输入: {input_audio}")
    click.echo(f"输出: {output_audio}")
    if 'n_steps' in info:
        click.echo(f"变调: {info['n_steps']} 半音")
    if 'factor' in info:
        click.echo(f"变调因子: {info['factor']:.4f}")
    if 'rate' in info:
        click.echo(f"时间拉伸: {info['rate']}x")

    return transformed, info


@main.command()
@click.argument('input_audio', type=click.Path(exists=True))
@click.argument('output_audio', type=click.Path())
@click.option('--reference-audio', '-r', default=None,
              type=click.Path(exists=True),
              help='参考音频用于频谱匹配')
@click.option('--pitch-factor', '-p', default=None, type=float,
              help='指定变调因子进行恢复')
@click.option('--use-iterative/--no-iterative', default=False,
              help='使用迭代恢复')
@click.option('--sample-rate', '-sr', default=16000, type=int,
              help='采样率')
@click.pass_context
def restore(ctx, input_audio: str, output_audio: str,
            reference_audio: Optional[str], pitch_factor: Optional[float],
            use_iterative: bool, sample_rate: int):
    """恢复被伪装的音频"""
    from .pitch_recovery import AudioRestoration
    from .anti_spoofing import AntiSpoofingDetector

    verbose = ctx.obj['verbose']

    audio, sr = utils.load_audio(input_audio, sample_rate=sample_rate)

    if pitch_factor is None:
        detector = AntiSpoofingDetector(sample_rate=sample_rate)
        result = detector.detect_spoofing(audio)
        pitch_factor = result['estimated_pitch_factor']
        if verbose:
            click.echo(f"检测到的变调因子: {pitch_factor:.4f}")

    reference = None
    if reference_audio:
        reference, _ = utils.load_audio(reference_audio, sample_rate=sample_rate)

    restorer = AudioRestoration(sample_rate=sample_rate)
    restored, info = restorer.restore_audio(
        audio,
        estimated_pitch_factor=pitch_factor,
        reference_audio=reference,
        use_iterative=use_iterative
    )

    save_dir = os.path.dirname(output_audio)
    if save_dir and not os.path.exists(save_dir):
        os.makedirs(save_dir)

    utils.save_audio(output_audio, restored, sample_rate)

    click.echo(f"\n音频恢复完成")
    click.echo(f"输入: {input_audio}")
    click.echo(f"输出: {output_audio}")
    click.echo(f"使用变调因子: {pitch_factor:.4f}")
    if info.get('final_snr_improvement'):
        click.echo(f"SNR改善: {info['final_snr_improvement']:.2f} dB")

    return restored, info


@main.command()
@click.argument('input_audio', type=click.Path(exists=True))
@click.argument('output_audio', type=click.Path())
@click.option('--model-type', '-m', default='gan',
              type=click.Choice(['gan', 'cyclegan', 'hybrid']),
              help='修复模型类型')
@click.option('--reference-audio', '-r', default=None,
              type=click.Path(exists=True),
              help='参考音频（干净样本）')
@click.option('--pretrained-path', '-p', default=None,
              type=click.Path(),
              help='预训练模型路径')
@click.option('--use-hybrid/--no-hybrid', default=False,
              help='使用混合修复（先CWT后GAN）')
@click.option('--sample-rate', '-sr', default=16000, type=int,
              help='采样率')
@click.pass_context
def gan_repair(ctx, input_audio: str, output_audio: str,
               model_type: str, reference_audio: Optional[str],
               pretrained_path: Optional[str], use_hybrid: bool,
               sample_rate: int):
    """基于GAN的伪装语音修复"""
    from .gan_repair import GANVoiceRepair

    verbose = ctx.obj['verbose']
    device = ctx.obj['device']

    audio, sr = utils.load_audio(input_audio, sample_rate=sample_rate)

    reference = None
    if reference_audio:
        reference, _ = utils.load_audio(reference_audio, sample_rate=sample_rate)

    if use_hybrid:
        from .pitch_recovery import AudioRestoration
        from .anti_spoofing import AntiSpoofingDetector

        detector = AntiSpoofingDetector(sample_rate=sample_rate)
        detect_result = detector.detect_spoofing(audio)
        pitch_factor = detect_result['estimated_pitch_factor']

        restorer = AudioRestoration(sample_rate=sample_rate)
        audio, _ = restorer.restore_audio(
            audio, estimated_pitch_factor=pitch_factor,
            reference_audio=reference, use_iterative=True
        )
        if verbose:
            click.echo("完成CWT预修复，开始GAN优化...")

    repairer = GANVoiceRepair(
        model_type=model_type,
        sample_rate=sample_rate,
        device=device
    )

    if pretrained_path and os.path.exists(pretrained_path):
        repairer.load_model(pretrained_path)
        if verbose:
            click.echo(f"加载预训练模型: {pretrained_path}")

    repaired_audio, repair_info = repairer.repair_audio(audio, reference_audio=reference)

    save_dir = os.path.dirname(output_audio)
    if save_dir and not os.path.exists(save_dir):
        os.makedirs(save_dir)

    utils.save_audio(output_audio, repaired_audio, sample_rate)

    click.echo("\n" + "=" * 50)
    click.echo("GAN语音修复完成")
    click.echo("=" * 50)
    click.echo(f"  输入: {input_audio}")
    click.echo(f"  输出: {output_audio}")
    click.echo(f"  模型类型: {model_type}")
    click.echo(f"  混合修复: {'是' if use_hybrid else '否'}")
    if 'snr_improvement' in repair_info:
        click.echo(f"  SNR改善: {repair_info['snr_improvement']:.2f} dB")
    if 'model_type' in repair_info:
        click.echo(f"  使用模型: {repair_info['model_type']}")
    click.echo("=" * 50)

    return {'repaired_audio': repaired_audio, 'info': repair_info}


@main.command()
@click.argument('test_audio', type=click.Path(exists=True))
@click.option('--enroll-audio', '-e', multiple=True,
              type=click.Path(exists=True),
              required=True,
              help='注册音频文件')
@click.option('--check-liveness/--no-liveness', default=True,
              help='是否检查活体性')
@click.option('--check-replay/--no-replay', default=True,
              help='是否检查录音重放')
@click.option('--check-spoofing/--no-spoofing', default=True,
              help='是否检查伪装')
@click.option('--threshold', '-t', default=0.7, type=float,
              help='整体验证阈值')
@click.option('--model-type', '-m', default=None,
              type=click.Choice(['ecapa', 'xvector']),
              help='嵌入模型类型')
@click.option('--output-format', '-o', default='text',
              type=click.Choice(['text', 'json']),
              help='输出格式')
@click.pass_context
def voiceprint_lock(ctx, test_audio: str, enroll_audio: List[str],
                    check_liveness: bool, check_replay: bool,
                    check_spoofing: bool, threshold: float,
                    model_type: Optional[str], output_format: str):
    """声纹锁验证（防录音重放+活体检测+说话人匹配）"""
    from .voiceprint_lock import VoiceprintLock

    cfg = ctx.obj['config']
    device = ctx.obj['device']
    verbose = ctx.obj['verbose']

    if model_type is None:
        model_type = cfg['embedding']['model_type']

    if verbose:
        click.echo(f"注册音频: {len(enroll_audio)} 个文件")
        click.echo(f"测试音频: {test_audio}")
        click.echo(f"活体检测: {'开启' if check_liveness else '关闭'}")
        click.echo(f"重放检测: {'开启' if check_replay else '关闭'}")
        click.echo(f"伪装检测: {'开启' if check_spoofing else '关闭'}")

    lock = VoiceprintLock(
        model_type=model_type,
        embedding_dim=cfg['embedding']['embedding_dim'],
        sample_rate=cfg['audio']['sample_rate'],
        device=device,
        threshold=threshold
    )

    lock.enroll_speaker(list(enroll_audio))

    result = lock.verify(
        test_audio,
        check_liveness=check_liveness,
        check_replay=check_replay,
        check_spoofing=check_spoofing
    )

    if output_format == 'json':
        output = {
            'verified': result['verified'],
            'overall_score': float(result['overall_score']),
            'threshold': float(threshold),
            'passed_checks': int(result['passed_checks']),
            'total_checks': int(result['total_checks']),
            'decision': result['decision'],
            'reject_reason': result.get('reject_reason'),
            'speaker_verification': {
                'passed': bool(result['speaker_verified']),
                'score': float(result['verification_score']),
                'weight': 0.4
            },
            'replay_detection': {
                'passed': bool(not result['is_replay']) if 'is_replay' in result else None,
                'score': float(1 - result['replay_detection']['replay_probability']) if 'replay_detection' in result else None,
                'weight': 0.25
            },
            'liveness_detection': {
                'passed': bool(result['is_live']) if 'is_live' in result else None,
                'score': float(result['liveness_detection']['liveness_probability']) if 'liveness_detection' in result else None,
                'weight': 0.25
            },
            'spoofing_detection': {
                'passed': bool(not result['is_spoofed']) if 'is_spoofed' in result else None,
                'score': float(1 - result['spoofing_detection']['spoofing_probability']) if 'spoofing_detection' in result else None,
                'weight': 0.1
            }
        }
        click.echo(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        click.echo(lock.generate_report(result))

    return result


@main.command()
@click.argument('input_audio', type=click.Path(exists=True))
@click.option('--enroll-speaker', '-e', multiple=True, nargs=2,
              type=(str, click.Path(exists=True)),
              help='注册说话人，格式: (名字, 音频路径)')
@click.option('--max-speakers', '-n', default=5, type=int,
              help='最大说话人数')
@click.option('--diarize-only/--identify', default=False,
              help='仅做说话人分割不做识别')
@click.option('--output-dir', '-o', default=None,
              type=click.Path(),
              help='分离音频输出目录')
@click.option('--model-type', '-m', default=None,
              type=click.Choice(['ecapa', 'xvector']),
              help='嵌入模型类型')
@click.option('--sample-rate', '-sr', default=16000, type=int,
              help='采样率')
@click.pass_context
def multi_speaker(ctx, input_audio: str,
                  enroll_speaker: List[Tuple[str, str]],
                  max_speakers: int, diarize_only: bool,
                  output_dir: Optional[str], model_type: Optional[str],
                  sample_rate: int):
    """多说话人混合场景的分离和识别"""
    from .multi_speaker import MultiSpeakerIdentifier

    cfg = ctx.obj['config']
    device = ctx.obj['device']
    verbose = ctx.obj['verbose']

    if model_type is None:
        model_type = cfg['embedding']['model_type']

    audio, sr = utils.load_audio(input_audio, sample_rate=sample_rate)

    identifier = MultiSpeakerIdentifier(
        model_type=model_type,
        embedding_dim=cfg['embedding']['embedding_dim'],
        sample_rate=sample_rate,
        device=device
    )

    if not diarize_only and enroll_speaker:
        for name, audio_path in enroll_speaker:
            identifier.register_speaker(name, [audio_path])
            if verbose:
                click.echo(f"已注册说话人: {name}")

    if diarize_only:
        result = identifier.separator.separate_speakers(
            audio, max_speakers=max_speakers
        )
    else:
        result = identifier.diarize(audio, max_speakers=max_speakers)

    click.echo("\n" + "=" * 60)
    click.echo("多说话人分离识别结果")
    click.echo("=" * 60)
    click.echo(f"  检测到的说话人数: {result['n_speakers'] if diarize_only else result['n_detected_speakers']}")
    if not diarize_only:
        click.echo(f"  识别出的说话人数: {result['n_identified_speakers']}")
        if result['identified_speakers']:
            click.echo(f"  识别出的说话人: {', '.join(result['identified_speakers'])}")
    click.echo("\n  说话人时间线:")
    click.echo("  " + "-" * 56)

    timeline = []
    if diarize_only:
        for speaker_id, seg_info in enumerate(result['speaker_segments']):
            for seg in seg_info['segments']:
                timeline.append({
                    'start_time': seg['start_time'],
                    'end_time': seg['end_time'],
                    'speaker': f"Speaker_{speaker_id}"
                })
    else:
        timeline = result['timeline']

    timeline.sort(key=lambda x: x['start_time'])
    for entry in timeline:
        speaker = entry.get('speaker') or entry.get('identified_speaker') or f"Speaker_{entry.get('speaker_index', 0)}"
        conf = entry.get('confidence', 0.0)
        if not diarize_only and 'confidence' in entry:
            click.echo(f"  {entry['start_time']:7.2f}s - {entry['end_time']:7.2f}s | {speaker:20s} (置信度: {conf:.3f})")
        else:
            click.echo(f"  {entry['start_time']:7.2f}s - {entry['end_time']:7.2f}s | {speaker}")
    click.echo("=" * 60)

    if output_dir:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        separated = result['separated_audios'] if diarize_only else result['separation_result']['separated_audios']
        for i, audio_sep in enumerate(separated):
            if not diarize_only and result['identifications'][i]['identified_speaker']:
                name = result['identifications'][i]['identified_speaker']
                output_path = os.path.join(output_dir, f"speaker_{i}_{name}.wav")
            else:
                output_path = os.path.join(output_dir, f"speaker_{i}.wav")
            utils.save_audio(output_path, audio_sep, sample_rate)
            click.echo(f"  已保存分离音频: {output_path}")

    if not diarize_only and 'diarization_report' in result:
        click.echo("\n  详细分割报告:")
        for line in result['diarization_report']:
            click.echo(f"    {line}")

    return result


@main.command()
def version():
    """显示版本信息"""
    from . import __version__
    click.echo(f"说话人验证工具 v{__version__}")
    click.echo("支持功能:")
    click.echo("  - 说话人嵌入提取 (X-Vector / ECAPA-TDNN)")
    click.echo("  - 伪装变换模拟 (PSOLA/相位声码器/重采样)")
    click.echo("  - 反伪装检测 (相位残差/频谱一致性)")
    click.echo("  - 音频恢复 (CWT小波变换)")
    click.echo("  - GAN语音修复 (GAN/CycleGAN/混合修复)")
    click.echo("  - 声纹锁系统 (四重验证机制)")
    click.echo("  - 多说话人分离与识别 (GMM聚类+嵌入识别)")


if __name__ == '__main__':
    main(obj={})
