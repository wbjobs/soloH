from setuptools import setup, find_packages

setup(
    name='lidar_tree_tool',
    version='1.0.0',
    description='LiDAR point cloud processing tool for tree segmentation and analysis',
    author='LiDAR Tree Tool',
    packages=find_packages(),
    install_requires=[
        'torch>=1.12.0',
        'numpy>=1.21.0',
        'open3d>=0.16.0',
        'plyfile>=0.7.4',
        'laspy>=2.4.0',
        'pandas>=1.3.0',
        'scipy>=1.7.0',
        'scikit-learn>=1.0.0',
        'tqdm>=4.62.0',
    ],
    entry_points={
        'console_scripts': [
            'lidar-tree-tool=lidar_tree_tool.main:main',
        ],
    },
    python_requires='>=3.8',
)
