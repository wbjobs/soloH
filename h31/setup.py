from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='cell-tracker',
    version='1.0.0',
    description='Cell tracking analysis pipeline with U-Net segmentation, Hungarian algorithm tracking, and division detection',
    author='Cell Tracker Team',
    packages=find_packages(),
    install_requires=requirements,
    python_requires='>=3.9',
    entry_points={
        'console_scripts': [
            'cell-tracker=cell_tracker.cli:cli',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'Topic :: Scientific/Engineering :: Image Recognition',
    ],
    keywords='cell-tracking segmentation unet napari hungarian-algorithm microscopy',
)
