from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='speaker_verification',
    version='1.0.0',
    description='说话人验证与反伪装检测工具',
    author='Speaker Verification Team',
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'speaker-verify=speaker_verification.cli:main',
        ],
    },
    python_requires='>=3.9',
)
