from setuptools import setup, find_packages

setup(
    name='bearing_diagnosis',
    version='1.0.0',
    description='Bearing Fault Diagnosis Tool with PyTorch and Signal Processing',
    author='Bearing Diagnosis Team',
    packages=find_packages(),
    install_requires=[
        'numpy>=1.21.0',
        'scipy>=1.7.0',
        'matplotlib>=3.4.0',
        'scikit-learn>=1.0.0',
        'torch>=1.9.0',
        'pywavelets>=1.1.1',
        'pandas>=1.3.0',
        'tqdm>=4.62.0',
        'click>=8.0.0',
        'joblib>=1.0.0',
    ],
    entry_points={
        'console_scripts': [
            'bearing-diagnosis=bearing_diagnosis.cli:main',
        ],
    },
    python_requires='>=3.7',
)
