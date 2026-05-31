#!/usr/bin/env python
"""
Test script to verify all modules can be imported correctly.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test importing all modules."""
    print('Testing imports...')
    
    try:
        from sea_ice_drift import io
        print('  ✓ io module imported successfully')
    except Exception as e:
        print(f'  ✗ io module failed: {e}')
        return False
    
    try:
        from sea_ice_drift import preprocess
        print('  ✓ preprocess module imported successfully')
    except Exception as e:
        print(f'  ✗ preprocess module failed: {e}')
        return False
    
    try:
        from sea_ice_drift import motion
        print('  ✓ motion module imported successfully')
    except Exception as e:
        print(f'  ✗ motion module failed: {e}')
        return False
    
    try:
        from sea_ice_drift import mask
        print('  ✓ mask module imported successfully')
    except Exception as e:
        print(f'  ✗ mask module failed: {e}')
        return False
    
    try:
        from sea_ice_drift import quality
        print('  ✓ quality module imported successfully')
    except Exception as e:
        print(f'  ✗ quality module failed: {e}')
        return False
    
    try:
        from sea_ice_drift import output
        print('  ✓ output module imported successfully')
    except Exception as e:
        print(f'  ✗ output module failed: {e}')
        return False
    
    try:
        from sea_ice_drift import validation
        print('  ✓ validation module imported successfully')
    except Exception as e:
        print(f'  ✗ validation module failed: {e}')
        return False
    
    print('\nAll modules imported successfully!')
    return True


def test_classes():
    """Test that key classes and functions are accessible."""
    print('\nTesting key classes and functions...')
    
    from sea_ice_drift.io import BrightnessTemperatureData, create_sample_data
    from sea_ice_drift.motion import MotionField, estimate_motion
    from sea_ice_drift.mask import create_full_mask
    from sea_ice_drift.quality import quality_control_pipeline
    from sea_ice_drift.validation import BuoyObservation
    
    print('  ✓ BrightnessTemperatureData')
    print('  ✓ MotionField')
    print('  ✓ BuoyObservation')
    print('  ✓ create_sample_data')
    print('  ✓ estimate_motion')
    print('  ✓ create_full_mask')
    print('  ✓ quality_control_pipeline')
    
    return True


def test_synthetic_data():
    """Test creating synthetic data."""
    print('\nTesting synthetic data creation...')
    
    from sea_ice_drift.io import create_sample_data
    
    try:
        sample_dir = create_sample_data(
            shape=(50, 50),
            num_frames=2,
            save_dir='test_sample_data'
        )
        print(f'  ✓ Sample data created in: {sample_dir}')
        return True
    except Exception as e:
        print(f'  ✗ Sample data creation failed: {e}')
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print('=' * 60)
    print('Sea Ice Drift Toolkit - Import and Basic Functionality Test')
    print('=' * 60)
    
    all_passed = True
    
    all_passed &= test_imports()
    all_passed &= test_classes()
    all_passed &= test_synthetic_data()
    
    print('\n' + '=' * 60)
    if all_passed:
        print('All tests passed! ✓')
    else:
        print('Some tests failed! ✗')
    print('=' * 60)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
