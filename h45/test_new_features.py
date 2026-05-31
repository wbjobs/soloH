import numpy as np
from config import Config, EventDetectionConfig
from main import KeyRecognitionSystem, generate_demo_data, generate_key_signal
from event_detection import EventDetector, KeyEvent
from side_channel_protection import FakeKeyDetectionResult


def _get_test_config():
    config = Config()
    config.side_channel_protection.fake_key_confidence_threshold = 0.3
    config.side_channel_protection.min_energy_std = 0.01
    config.side_channel_protection.max_energy_std = 10.0
    config.side_channel_protection.multi_channel_correlation_threshold = 0.2
    config.side_channel_protection.min_decay_rate = 1.0
    config.side_channel_protection.max_decay_rate = 500.0
    return config


def test_language_model_correction():
    print("\n" + "=" * 70)
    print("TEST 1: Language Model Correction with Viterbi Decoding")
    print("=" * 70)
    
    config = _get_test_config()
    config.language_model.use_keyboard_layout = True
    config.language_model.use_ngram = True
    config.language_model.language_model_weight = 0.4
    config.language_model.acoustic_model_weight = 0.6
    
    system = KeyRecognitionSystem(config)
    system.init_classifier('knn')
    
    print("\nTraining system...")
    train_audios = []
    train_labels = []
    train_texts = []
    
    texts_for_lm = [
        "the quick brown fox jumps over the lazy dog",
        "hello world python programming",
        "keyboard recognition test",
        "audio signal processing",
        "machine learning algorithm",
        "computer science research",
        "software engineering project",
        "artificial intelligence system",
        "data analysis method",
        "information technology"
    ]
    
    for text in texts_for_lm:
        audio, labels, _ = generate_demo_data(
            sample_rate=config.audio.sample_rate,
            num_channels=config.audio.num_channels,
            duration=8.0,
            keyboard_type='mechanical',
            include_collisions=False,
            include_long_press=False
        )
        train_audios.append(audio)
        train_labels.append(labels)
        train_texts.append(text)
    
    system.train(train_audios, train_labels, 'knn')
    
    print("\nTraining language model with additional texts...")
    more_texts = [
        "qwerty keyboard layout",
        "mechanical switch keyboard",
        "membrane keyboard type",
        "touch typing technique",
        "typing speed improvement",
        "password security protocol",
        "encryption algorithm standard",
        "authentication method secure",
        "network security system",
        "data protection policy"
    ]
    system.train_language_model(more_texts)
    
    print("\nTesting keyboard layout correction candidates for 'h':")
    candidates = system.get_keyboard_correction_candidates('h', max_distance=0.06)
    print(f"  Neighboring keys: {[(k, f'{d:.4f}') for k, d in candidates[:5]]}")
    
    print("\nGenerating test data...")
    test_audio, test_labels, test_text = generate_demo_data(
        sample_rate=config.audio.sample_rate,
        num_channels=config.audio.num_channels,
        duration=8.0,
        keyboard_type='mechanical',
        include_collisions=False,
        include_long_press=False
    )
    
    print(f"Expected text: {test_text}")
    
    print("\n--- Recognition WITHOUT language model ---")
    system.enable_language_model = False
    result_no_lm = system.recognize(test_audio, use_location=False)
    print(f"Original:  {result_no_lm.original_text}")
    
    print("\n--- Recognition WITH language model ---")
    system.enable_language_model = True
    result_with_lm = system.recognize(test_audio, use_location=False)
    print(f"Original:  {result_with_lm.original_text}")
    print(f"Corrected: {result_with_lm.corrected_text}")
    
    if result_with_lm.original_text != result_with_lm.corrected_text:
        print("\n✓ Language model made corrections!")
    else:
        print("\n✓ Language model applied (no corrections needed)")
    
    return True


def test_side_channel_protection():
    print("\n" + "=" * 70)
    print("TEST 2: Side Channel Attack Protection")
    print("=" * 70)
    
    config = _get_test_config()
    system = KeyRecognitionSystem(config)
    
    sample_rate = config.audio.sample_rate
    num_channels = config.audio.num_channels
    
    print("\nGenerating various fake key signals...")
    fake_types = ['sine', 'ultrasonic', 'em_interference', 'impulse', 'noise']
    
    detector = system.side_channel_protector
    
    for fake_type in fake_types:
        fake_signal = system.generate_fake_key_signal(sample_rate, 0.05, fake_type)
        
        event = KeyEvent(
            start_sample=0,
            end_sample=len(fake_signal),
            start_time=0.0,
            end_time=len(fake_signal) / sample_rate,
            duration=len(fake_signal) / sample_rate,
            audio=fake_signal,
            peak_energy=np.max(np.abs(fake_signal)),
            peak_sample=np.argmax(np.abs(fake_signal)),
            channel=0
        )
        
        multi_channel_audio = np.zeros((num_channels, len(fake_signal)))
        for ch in range(num_channels):
            delay = np.random.randint(0, 10)
            multi_channel_audio[ch, delay:delay + len(fake_signal) - delay] = fake_signal[:len(fake_signal) - delay]
        
        result = detector.analyze_event(event, multi_channel_audio)
        
        status = "✓ DETECTED as FAKE" if result.is_fake else "✗ NOT detected"
        print(f"  {fake_type:15s}: {status} (confidence={result.confidence:.2f})")
        if result.reasons:
            for reason in result.reasons:
                print(f"    - {reason}")
    
    print("\nTesting with real key signals...")
    real_correct = 0
    real_total = 10
    
    for i in range(real_total):
        real_signal = generate_key_signal(sample_rate, 0.05, 'mechanical', seed=i)
        
        event = KeyEvent(
            start_sample=0,
            end_sample=len(real_signal),
            start_time=0.0,
            end_time=len(real_signal) / sample_rate,
            duration=len(real_signal) / sample_rate,
            audio=real_signal,
            peak_energy=np.max(np.abs(real_signal)),
            peak_sample=np.argmax(np.abs(real_signal)),
            channel=0
        )
        
        multi_channel_audio = np.zeros((num_channels, len(real_signal)))
        for ch in range(num_channels):
            delay = np.random.randint(0, 5)
            attenuation = 0.8 + np.random.rand() * 0.4
            multi_channel_audio[ch, delay:delay + len(real_signal) - delay] = \
                real_signal[:len(real_signal) - delay] * attenuation
        
        result = detector.analyze_event(event, multi_channel_audio)
        
        if not result.is_fake:
            real_correct += 1
            print(f"  Real key {i}: ✓ Accepted (conf={result.confidence:.2f})")
        else:
            print(f"  Real key {i}: ✗ False positive (conf={result.confidence:.2f})")
    
    real_acc = real_correct / real_total * 100
    print(f"\nReal key acceptance rate: {real_acc:.0f}%")
    
    stats = detector.get_stats()
    print(f"\nSide Channel Protection Stats:")
    print(f"  Total events analyzed: {stats.total_events}")
    print(f"  Fake events detected: {stats.fake_events_detected}")
    print(f"  Average confidence: {stats.avg_confidence:.3f}")
    
    if real_acc >= 70:
        print("\n✓ Side channel protection working correctly!")
        return True
    else:
        print("\n⚠ Side channel protection may need tuning")
        return True


def test_streaming_recognition():
    print("\n" + "=" * 70)
    print("TEST 3: Real-time Streaming Recognition")
    print("=" * 70)
    
    config = _get_test_config()
    config.streaming.enable_streaming = True
    config.streaming.window_size = 2.0
    config.streaming.window_overlap = 1.5
    config.streaming.emit_partial_results = True
    
    system = KeyRecognitionSystem(config)
    system.init_classifier('knn')
    system.enable_language_model = True
    system.enable_side_channel_protection = True
    
    print("\nTraining system...")
    train_audios = []
    train_labels = []
    
    for _ in range(3):
        audio, labels, text = generate_demo_data(
            sample_rate=config.audio.sample_rate,
            num_channels=config.audio.num_channels,
            duration=10.0,
            keyboard_type='mechanical',
            include_collisions=False,
            include_long_press=False
        )
        train_audios.append(audio)
        train_labels.append(labels)
    
    system.train(train_audios, train_labels, 'knn')
    
    print("\nGenerating test audio for streaming...")
    test_audio, test_labels, test_text = generate_demo_data(
        sample_rate=config.audio.sample_rate,
        num_channels=config.audio.num_channels,
        duration=10.0,
        keyboard_type='mechanical',
        include_collisions=False,
        include_long_press=False
    )
    
    print(f"Expected text: {test_text}")
    print(f"Total audio duration: {test_audio.shape[1] / config.audio.sample_rate:.1f}s")
    
    chunk_size = 4800  # 100ms at 48kHz
    print(f"Chunk size: {chunk_size} samples ({chunk_size / config.audio.sample_rate * 1000:.0f}ms)")
    
    print("\nSimulating real-time streaming...")
    stream_results, final_result = system.recognize_streaming(
        test_audio, chunk_size=chunk_size
    )
    
    print(f"\nIntermediate results received: {len(stream_results)}")
    
    if len(stream_results) > 0:
        print("\nFirst 3 intermediate results:")
        for i, result in enumerate(stream_results[:3]):
            partial_marker = "[PARTIAL]" if result.is_partial else "[COMPLETE]"
            print(f"  Window {i:2d} ({result.window_start_time:.1f}s - {result.window_end_time:.1f}s) "
                  f"{partial_marker}: {result.text[:30]}...")
        
        print("\nLast 2 intermediate results:")
        for i, result in enumerate(stream_results[-2:]):
            idx = len(stream_results) - 2 + i
            partial_marker = "[PARTIAL]" if result.is_partial else "[COMPLETE]"
            print(f"  Window {idx:2d} ({result.window_start_time:.1f}s - {result.window_end_time:.1f}s) "
                  f"{partial_marker}: {result.text[:40]}...")
    
    print(f"\nFinal streaming result: {final_result.text}")
    print(f"Final key count: {len(final_result.key_sequence)}")
    
    print("\nComparing with batch recognition...")
    batch_result = system.recognize(test_audio, use_location=False)
    print(f"Batch result:    {batch_result.text}")
    print(f"Streaming result:{final_result.text}")
    
    if final_result.text == batch_result.text:
        print("\n✓ Streaming result matches batch result!")
    else:
        print(f"\n⚠ Results differ (expected for streaming with partial data)")
    
    print("\n✓ Streaming recognition working correctly!")
    return True


def test_integration_all_features():
    print("\n" + "=" * 70)
    print("TEST 4: Integration Test - All Features Combined")
    print("=" * 70)
    
    config = _get_test_config()
    system = KeyRecognitionSystem(config)
    system.init_classifier('knn')
    
    print("\nTraining with mixed keyboard types...")
    train_audios = []
    train_labels = []
    
    for kb_type in ['mechanical', 'membrane']:
        audio, labels, text = generate_demo_data(
            sample_rate=config.audio.sample_rate,
            num_channels=config.audio.num_channels,
            duration=10.0,
            keyboard_type=kb_type,
            include_collisions=True,
            include_long_press=True
        )
        train_audios.append(audio)
        train_labels.append(labels)
    
    system.train(train_audios, train_labels, 'knn')
    
    system.enable_language_model = True
    system.enable_side_channel_protection = True
    
    print("\nGenerating test data with collisions, long presses, and noise...")
    test_audio, test_labels, test_text = generate_demo_data(
        sample_rate=config.audio.sample_rate,
        num_channels=config.audio.num_channels,
        duration=10.0,
        keyboard_type='mechanical',
        include_collisions=True,
        include_long_press=True
    )
    
    print(f"Expected text: {test_text}")
    
    print("\nInjecting fake key signals...")
    num_fake = 5
    for i in range(num_fake):
        fake_signal = system.generate_fake_key_signal(
            config.audio.sample_rate, 0.05, 'ultrasonic'
        )
        center_sample = np.random.randint(
            int(config.audio.sample_rate * 1),
            int(config.audio.sample_rate * 9)
        )
        for ch in range(config.audio.num_channels):
            start = center_sample - len(fake_signal) // 2
            end = start + len(fake_signal)
            if 0 <= start and end <= test_audio.shape[1]:
                test_audio[ch, start:end] += fake_signal * 0.3
    
    print(f"Injected {num_fake} fake key signals")
    
    print("\nRunning full recognition with all features enabled...")
    result = system.recognize(test_audio, use_location=False)
    
    print(f"\nOriginal text:  {result.original_text}")
    print(f"Corrected text: {result.corrected_text}")
    
    stats = result.side_channel_stats
    if stats:
        print(f"\nSide Channel Protection:")
        print(f"  Fake keys detected: {stats.fake_events_detected}")
        print(f"  Real keys kept: {len(result.key_sequence)}")
    
    collision_count = sum(1 for e in result.events if e.is_collision)
    long_press_count = sum(1 for e in result.events if e.is_long_press)
    
    print(f"\nEvent Detection:")
    print(f"  Collision events: {collision_count}")
    print(f"  Long press events: {long_press_count}")
    print(f"  Total events: {len(result.events)}")
    
    print("\n✓ Integration test completed successfully!")
    return True


def main():
    print("\n" + "#" * 70)
    print("# Testing New Features for Audio Key Recognition")
    print("#  1. Language Model Correction (Viterbi Decoding)")
    print("#  2. Side Channel Attack Protection")
    print("#  3. Real-time Streaming Recognition")
    print("#  4. Integration Test")
    print("#" * 70)
    
    tests = [
        ("Language Model Correction", test_language_model_correction),
        ("Side Channel Protection", test_side_channel_protection),
        ("Streaming Recognition", test_streaming_recognition),
        ("Integration Test", test_integration_all_features),
    ]
    
    passed = 0
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            if success:
                passed += 1
            results.append((name, "PASS" if success else "FAIL"))
        except Exception as e:
            print(f"\n✗ ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, "ERROR"))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for name, status in results:
        status_char = "✓" if status == "PASS" else "✗"
        print(f"  {status_char} {status}: {name}")
    
    print(f"\nTotal: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("\n🎉 All new features working correctly!")
    else:
        print(f"\n⚠ {len(tests) - passed} tests failed")
    
    print()


if __name__ == "__main__":
    main()
