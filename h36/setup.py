from setuptools import setup, find_packages

setup(
    name='protocol-reverser',
    version='1.0.0',
    description='PCAP protocol reverse engineering tool',
    author='Protocol Analysis Team',
    packages=find_packages(),
    install_requires=[
        'scapy>=2.5.0',
        'numpy>=1.24.0',
        'matplotlib>=3.7.0',
        'jinja2>=3.1.0',
        'tqdm>=4.65.0',
    ],
    entry_points={
        'console_scripts': [
            'protorev=protorev.cli:main',
        ],
    },
    python_requires='>=3.9',
)
