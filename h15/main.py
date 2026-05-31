#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MRI 采集与重建模拟系统
======================

功能:
- 生成Shepp-Logan phantom
- 计算全采样k空间 (256x256)
- 多种欠采样模式: 笛卡尔、径向、螺旋、随机
- 重建算法: TV正则化、SENSE、CS-MRI (IST/FISTA)
- 小波基: Daubechies, Symlet
- GUI展示: 重建图像、误差图、PSNR/SSIM指标
- 批量处理对比不同采样模式

运行:
    python main.py
"""

import sys
from gui import main


if __name__ == "__main__":
    main()
