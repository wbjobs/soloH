class OilPaintingApp {
    constructor() {
        this.originalImage = null;
        this.originalWidth = 0;
        this.originalHeight = 0;
        this.processedImageData = null;
        this.superpixels = [];
        this.gradientField = null;
        this.currentStyle = 'impressionist';
        this.currentTab = 'original';
        this.comparePosition = 50;
        this.isRendering = false;
        this.debounceTimer = null;
        
        this.paintParticles = [];
        this.thicknessMap = null;
        this.specularMap = null;
        
        this.styleImages = [];
        this.learnedStyle = null;
        
        this.videoFrames = [];
        this.processedVideoFrames = [];
        this.opticalFlowFields = [];
        this.currentVideoFrame = 0;
        this.videoPlaybackTimer = null;
        
        this.styleConfigs = {
            impressionist: {
                brushShape: 'ellipse',
                brushLengthRatio: 2.5,
                colorVariation: 0.15,
                opacityVariation: 0.2,
                edgeSoftness: 0.4,
                textureNoise: 0.3,
                saturationBoost: 1.1,
                contrastBoost: 1.05,
                description: '印象派 - 柔和笔触，捕捉光影瞬间'
            },
            expressionist: {
                brushShape: 'irregular',
                brushLengthRatio: 3.5,
                colorVariation: 0.35,
                opacityVariation: 0.4,
                edgeSoftness: 0.2,
                textureNoise: 0.6,
                saturationBoost: 1.4,
                contrastBoost: 1.2,
                description: '表现派 - 强烈笔触，情感宣泄'
            },
            pointillist: {
                brushShape: 'circle',
                brushLengthRatio: 1,
                colorVariation: 0.25,
                opacityVariation: 0.15,
                edgeSoftness: 0.6,
                textureNoise: 0.2,
                saturationBoost: 1.25,
                contrastBoost: 1.1,
                description: '点彩派 - 色点交织，光学混合'
            }
        };
        
        this.init();
    }
    
    init() {
        this.setupElements();
        this.setupEventListeners();
        this.setupCanvas();
    }
    
    setupElements() {
        this.originalCanvas = document.getElementById('originalCanvas');
        this.processedCanvas = document.getElementById('processedCanvas');
        this.overlayCanvas = document.getElementById('overlayCanvas');
        this.thicknessCanvas = document.getElementById('thicknessCanvas');
        this.particlesCanvas = document.getElementById('particlesCanvas');
        this.originalCtx = this.originalCanvas.getContext('2d');
        this.processedCtx = this.processedCanvas.getContext('2d');
        this.overlayCtx = this.overlayCanvas.getContext('2d');
        this.thicknessCtx = this.thicknessCanvas.getContext('2d');
        this.particlesCtx = this.particlesCanvas.getContext('2d');
        
        this.uploadArea = document.getElementById('uploadArea');
        this.imageInput = document.getElementById('imageInput');
        this.renderBtn = document.getElementById('renderBtn');
        this.exportPngBtn = document.getElementById('exportPngBtn');
        this.exportPsdBtn = document.getElementById('exportPsdBtn');
        
        this.brushSizeSlider = document.getElementById('brushSize');
        this.textureStrengthSlider = document.getElementById('textureStrength');
        this.brushDirectionSlider = document.getElementById('brushDirection');
        this.colorIntensitySlider = document.getElementById('colorIntensity');
        
        this.brushSizeValue = document.getElementById('brushSizeValue');
        this.textureStrengthValue = document.getElementById('textureStrengthValue');
        this.brushDirectionValue = document.getElementById('brushDirectionValue');
        this.colorIntensityValue = document.getElementById('colorIntensityValue');
        
        this.enablePhysicsCheckbox = document.getElementById('enablePhysics');
        this.paintThicknessSlider = document.getElementById('paintThickness');
        this.paintWetnessSlider = document.getElementById('paintWetness');
        this.paintMixingSlider = document.getElementById('paintMixing');
        this.specularStrengthSlider = document.getElementById('specularStrength');
        
        this.paintThicknessValue = document.getElementById('paintThicknessValue');
        this.paintWetnessValue = document.getElementById('paintWetnessValue');
        this.paintMixingValue = document.getElementById('paintMixingValue');
        this.specularStrengthValue = document.getElementById('specularStrengthValue');
        
        this.styleUploadArea = document.getElementById('styleUploadArea');
        this.styleImageInput = document.getElementById('styleImageInput');
        this.styleThumbs = document.getElementById('styleThumbs');
        this.styleInfo = document.getElementById('styleInfo');
        this.styleSampleCount = document.getElementById('styleSampleCount');
        this.stylePalettePreview = document.getElementById('stylePalettePreview');
        this.styleBrushType = document.getElementById('styleBrushType');
        this.learnStyleBtn = document.getElementById('learnStyleBtn');
        this.applyLearnedStyleBtn = document.getElementById('applyLearnedStyleBtn');
        this.clearStyleBtn = document.getElementById('clearStyleBtn');
        
        this.videoUploadArea = document.getElementById('videoUploadArea');
        this.videoInput = document.getElementById('videoInput');
        this.videoFramesEl = document.getElementById('videoFrames');
        this.videoInfo = document.getElementById('videoInfo');
        this.videoFrameCount = document.getElementById('videoFrameCount');
        this.videoCurrentFrame = document.getElementById('videoCurrentFrame');
        this.videoFrameSize = document.getElementById('videoFrameSize');
        this.temporalConsistencySlider = document.getElementById('temporalConsistency');
        this.temporalConsistencyValue = document.getElementById('temporalConsistencyValue');
        this.enableOpticalFlowCheckbox = document.getElementById('enableOpticalFlow');
        this.processVideoBtn = document.getElementById('processVideoBtn');
        this.exportVideoBtn = document.getElementById('exportVideoBtn');
        
        this.compareSlider = document.getElementById('compareSlider');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.loadingText = document.getElementById('loadingText');
        this.noImagePlaceholder = document.getElementById('noImagePlaceholder');
        this.canvasContainer = document.getElementById('canvasContainer');
        
        this.originalSizeEl = document.getElementById('originalSize');
        this.outputSizeEl = document.getElementById('outputSize');
        this.superpixelCountEl = document.getElementById('superpixelCount');
        this.renderTimeEl = document.getElementById('renderTime');
    }
    
    setupEventListeners() {
        this.uploadArea.addEventListener('click', () => this.imageInput.click());
        this.imageInput.addEventListener('change', (e) => this.handleFileSelect(e));
        
        this.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadArea.classList.add('dragover');
        });
        this.uploadArea.addEventListener('dragleave', () => {
            this.uploadArea.classList.remove('dragover');
        });
        this.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.loadImage(files[0]);
            }
        });
        
        document.querySelectorAll('.style-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentStyle = btn.dataset.style;
                if (this.originalImage) {
                    this.scheduleRender();
                }
            });
        });
        
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.switchTab(btn.dataset.tab);
            });
        });
        
        this.brushSizeSlider.addEventListener('input', () => {
            this.brushSizeValue.textContent = this.brushSizeSlider.value;
            if (this.originalImage) this.scheduleRender();
        });
        this.textureStrengthSlider.addEventListener('input', () => {
            this.textureStrengthValue.textContent = this.textureStrengthSlider.value;
            if (this.originalImage) this.scheduleRender();
        });
        this.brushDirectionSlider.addEventListener('input', () => {
            this.brushDirectionValue.textContent = this.brushDirectionSlider.value;
            if (this.originalImage) this.scheduleRender();
        });
        this.colorIntensitySlider.addEventListener('input', () => {
            this.colorIntensityValue.textContent = this.colorIntensitySlider.value;
            if (this.originalImage) this.scheduleRender();
        });
        
        document.querySelectorAll('input[name="resolution"]').forEach(radio => {
            radio.addEventListener('change', () => {
                if (this.originalImage) {
                    this.updateOutputSize();
                    this.scheduleRender();
                }
            });
        });
        
        this.renderBtn.addEventListener('click', () => this.renderOilPainting());
        this.exportPngBtn.addEventListener('click', () => this.exportPNG());
        this.exportPsdBtn.addEventListener('click', () => this.exportPSD());
        
        this.enablePhysicsCheckbox.addEventListener('change', () => {
            if (this.originalImage) this.scheduleRender();
        });
        
        this.paintThicknessSlider.addEventListener('input', () => {
            this.paintThicknessValue.textContent = this.paintThicknessSlider.value;
            if (this.originalImage) this.scheduleRender();
        });
        this.paintWetnessSlider.addEventListener('input', () => {
            this.paintWetnessValue.textContent = this.paintWetnessSlider.value;
            if (this.originalImage) this.scheduleRender();
        });
        this.paintMixingSlider.addEventListener('input', () => {
            this.paintMixingValue.textContent = this.paintMixingSlider.value;
            if (this.originalImage) this.scheduleRender();
        });
        this.specularStrengthSlider.addEventListener('input', () => {
            this.specularStrengthValue.textContent = this.specularStrengthSlider.value;
            if (this.originalImage) this.scheduleRender();
        });
        
        this.styleUploadArea.addEventListener('click', () => this.styleImageInput.click());
        this.styleImageInput.addEventListener('change', (e) => this.handleStyleImages(e));
        
        this.styleUploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.styleUploadArea.classList.add('dragover');
        });
        this.styleUploadArea.addEventListener('dragleave', () => {
            this.styleUploadArea.classList.remove('dragover');
        });
        this.styleUploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.styleUploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            this.loadStyleImages(files);
        });
        
        this.learnStyleBtn.addEventListener('click', () => this.learnArtistStyle());
        this.applyLearnedStyleBtn.addEventListener('click', () => this.applyLearnedStyle());
        this.clearStyleBtn.addEventListener('click', () => this.clearLearnedStyle());
        
        this.videoUploadArea.addEventListener('click', () => this.videoInput.click());
        this.videoInput.addEventListener('change', (e) => this.handleVideoInput(e));
        
        this.videoUploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.videoUploadArea.classList.add('dragover');
        });
        this.videoUploadArea.addEventListener('dragleave', () => {
            this.videoUploadArea.classList.remove('dragover');
        });
        this.videoUploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.videoUploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            this.loadVideoFiles(files);
        });
        
        this.temporalConsistencySlider.addEventListener('input', () => {
            this.temporalConsistencyValue.textContent = this.temporalConsistencySlider.value;
        });
        
        this.processVideoBtn.addEventListener('click', () => this.processVideoStyleTransfer());
        this.exportVideoBtn.addEventListener('click', () => this.exportVideo());
        
        this.setupCompareSlider();
    }
    
    setupCanvas() {
        const containerWidth = this.canvasContainer.clientWidth;
        const containerHeight = Math.max(500, this.canvasContainer.clientHeight);
        
        this.originalCanvas.width = containerWidth;
        this.originalCanvas.height = containerHeight;
        this.processedCanvas.width = containerWidth;
        this.processedCanvas.height = containerHeight;
        this.overlayCanvas.width = containerWidth;
        this.overlayCanvas.height = containerHeight;
    }
    
    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.loadImage(file);
        }
    }
    
    loadImage(file) {
        if (!file.type.startsWith('image/')) {
            alert('请上传图片文件');
            return;
        }
        
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                this.originalImage = img;
                this.originalWidth = img.width;
                this.originalHeight = img.height;
                
                this.originalSizeEl.textContent = `${img.width} × ${img.height}`;
                this.updateOutputSize();
                
                this.noImagePlaceholder.style.display = 'none';
                this.renderBtn.disabled = false;
                
                this.displayImageOnCanvas(img, this.originalCanvas, this.originalCtx);
                this.setupCanvasDimensions();
                this.renderOilPainting();
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    }
    
    updateOutputSize() {
        const resolution = document.querySelector('input[name="resolution"]:checked').value;
        const { width, height } = this.getTargetResolution(resolution);
        this.outputSizeEl.textContent = `${width} × ${height}`;
    }
    
    getTargetResolution(preset) {
        const aspect = this.originalWidth / this.originalHeight;
        let targetWidth, targetHeight;
        
        switch (preset) {
            case 'preview':
                targetWidth = Math.min(1920, this.originalWidth);
                targetHeight = Math.round(targetWidth / aspect);
                if (targetHeight > 1080) {
                    targetHeight = 1080;
                    targetWidth = Math.round(targetHeight * aspect);
                }
                break;
            case '2k':
                if (aspect >= 1) {
                    targetWidth = 2560;
                    targetHeight = Math.round(2560 / aspect);
                    if (targetHeight > 1440) {
                        targetHeight = 1440;
                        targetWidth = Math.round(1440 * aspect);
                    }
                } else {
                    targetHeight = 2560;
                    targetWidth = Math.round(2560 * aspect);
                }
                break;
            case '4k':
                if (aspect >= 1) {
                    targetWidth = 3840;
                    targetHeight = Math.round(3840 / aspect);
                    if (targetHeight > 2160) {
                        targetHeight = 2160;
                        targetWidth = Math.round(2160 * aspect);
                    }
                } else {
                    targetHeight = 3840;
                    targetWidth = Math.round(3840 * aspect);
                }
                break;
            default:
                targetWidth = this.originalWidth;
                targetHeight = this.originalHeight;
        }
        
        return { width: targetWidth, height: targetHeight };
    }
    
    setupCanvasDimensions() {
        const resolution = document.querySelector('input[name="resolution"]:checked').value;
        const { width, height } = this.getTargetResolution(resolution);
        
        const container = this.canvasContainer;
        const maxWidth = container.clientWidth - 40;
        const maxHeight = 700;
        
        let displayWidth = width;
        let displayHeight = height;
        
        if (displayWidth > maxWidth) {
            displayHeight = (maxWidth / width) * height;
            displayWidth = maxWidth;
        }
        if (displayHeight > maxHeight) {
            displayWidth = (maxHeight / height) * width;
            displayHeight = maxHeight;
        }
        
        this.originalCanvas.width = width;
        this.originalCanvas.height = height;
        this.originalCanvas.style.width = displayWidth + 'px';
        this.originalCanvas.style.height = displayHeight + 'px';
        
        this.processedCanvas.width = width;
        this.processedCanvas.height = height;
        this.processedCanvas.style.width = displayWidth + 'px';
        this.processedCanvas.style.height = displayHeight + 'px';
        
        this.overlayCanvas.width = width;
        this.overlayCanvas.height = height;
        this.overlayCanvas.style.width = displayWidth + 'px';
        this.overlayCanvas.style.height = displayHeight + 'px';
        
        this.thicknessCanvas.width = width;
        this.thicknessCanvas.height = height;
        this.thicknessCanvas.style.width = displayWidth + 'px';
        this.thicknessCanvas.style.height = displayHeight + 'px';
        
        this.particlesCanvas.width = width;
        this.particlesCanvas.height = height;
        this.particlesCanvas.style.width = displayWidth + 'px';
        this.particlesCanvas.style.height = displayHeight + 'px';
        
        this.displayImageOnCanvas(this.originalImage, this.originalCanvas, this.originalCtx);
    }
    
    displayImageOnCanvas(img, canvas, ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    }
    
    switchTab(tab) {
        this.currentTab = tab;
        
        this.originalCanvas.style.opacity = '1';
        this.processedCanvas.classList.remove('visible');
        this.overlayCanvas.classList.remove('visible');
        this.compareSlider.classList.remove('active');
        this.thicknessCanvas.classList.remove('visible');
        this.particlesCanvas.classList.remove('visible');
        
        switch (tab) {
            case 'original':
                this.originalCanvas.style.opacity = '1';
                break;
            case 'processed':
                if (this.processedImageData) {
                    this.processedCanvas.classList.add('visible');
                }
                break;
            case 'compare':
                this.processedCanvas.classList.add('visible');
                this.compareSlider.classList.add('active');
                this.updateCompareView();
                break;
            case 'directions':
                this.overlayCanvas.classList.add('visible');
                this.drawDirectionField();
                break;
            case 'superpixels':
                this.overlayCanvas.classList.add('visible');
                this.drawSuperpixelBoundaries();
                break;
            case 'thickness':
                this.thicknessCanvas.classList.add('visible');
                if (this.thicknessMap) {
                    this.drawThicknessMap();
                }
                break;
            case 'particles':
                this.particlesCanvas.classList.add('visible');
                if (this.paintParticles.length > 0) {
                    this.drawParticlesView();
                }
                break;
        }
    }
    
    setupCompareSlider() {
        let isDragging = false;
        
        const startDrag = (e) => {
            if (this.currentTab !== 'compare') return;
            isDragging = true;
            document.body.style.cursor = 'ew-resize';
            e.preventDefault();
        };
        
        const onDrag = (e) => {
            if (!isDragging) return;
            
            const rect = this.canvasContainer.getBoundingClientRect();
            const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
            const x = clientX - rect.left;
            const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
            
            this.comparePosition = percentage;
            this.compareSlider.style.left = percentage + '%';
            this.updateCompareView();
        };
        
        const endDrag = () => {
            isDragging = false;
            document.body.style.cursor = '';
        };
        
        this.compareSlider.addEventListener('mousedown', startDrag);
        this.compareSlider.addEventListener('touchstart', startDrag);
        document.addEventListener('mousemove', onDrag);
        document.addEventListener('touchmove', onDrag);
        document.addEventListener('mouseup', endDrag);
        document.addEventListener('touchend', endDrag);
    }
    
    updateCompareView() {
        const width = this.processedCanvas.width;
        const clipX = (this.comparePosition / 100) * width;
        
        this.processedCtx.save();
        this.processedCtx.beginPath();
        this.processedCtx.rect(clipX, 0, width - clipX, this.processedCanvas.height);
        this.processedCtx.clip();
        
        if (this.processedImageData) {
            this.processedCtx.putImageData(this.processedImageData, 0, 0);
        }
        
        this.processedCtx.restore();
    }
    
    scheduleRender() {
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        this.debounceTimer = setTimeout(() => {
            this.renderOilPainting();
        }, 200);
    }
    
    async renderOilPainting() {
        if (!this.originalImage || this.isRendering) return;
        
        this.isRendering = true;
        this.showLoading('正在分析图像...');
        
        const startTime = performance.now();
        
        try {
            const resolution = document.querySelector('input[name="resolution"]:checked').value;
            const { width, height } = this.getTargetResolution(resolution);
            
            await this.sleep(50);
            
            this.loadingText.textContent = '正在计算超像素分割...';
            this.superpixels = this.computeSuperpixels(width, height);
            this.superpixelCountEl.textContent = this.superpixels.length;
            
            await this.sleep(50);
            
            this.loadingText.textContent = '正在计算梯度方向场...';
            this.gradientField = this.computeGradientField(width, height);
            
            await this.sleep(50);
            
            this.loadingText.textContent = '正在应用油画渲染...';
            this.processedImageData = this.applyBrushRendering(width, height);
            
            this.processedCtx.putImageData(this.processedImageData, 0, 0);
            
            this.exportPngBtn.disabled = false;
            this.exportPsdBtn.disabled = false;
            
            const endTime = performance.now();
            const renderTime = ((endTime - startTime) / 1000).toFixed(2);
            this.renderTimeEl.textContent = renderTime + ' 秒';
            
            this.switchTab(this.currentTab);
            
        } catch (error) {
            console.error('渲染错误:', error);
            alert('渲染过程中发生错误: ' + error.message);
        } finally {
            this.isRendering = false;
            this.hideLoading();
        }
    }
    
    computeSuperpixels(width, height) {
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = width;
        tempCanvas.height = height;
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.drawImage(this.originalImage, 0, 0, width, height);
        
        const imageData = tempCtx.getImageData(0, 0, width, height);
        const data = imageData.data;
        
        const brushSize = parseInt(this.brushSizeSlider.value);
        const regionSize = Math.max(10, brushSize * 2);
        
        const numCols = Math.ceil(width / regionSize);
        const numRows = Math.ceil(height / regionSize);
        
        const clusters = [];
        
        for (let row = 0; row < numRows; row++) {
            for (let col = 0; col < numCols; col++) {
                const centerX = Math.min(width - 1, (col + 0.5) * regionSize);
                const centerY = Math.min(height - 1, (row + 0.5) * regionSize);
                
                const adjustedCenter = this.findLocalMinimum(data, centerX, centerY, width, height, 3);
                
                const pixelIndex = (Math.floor(adjustedCenter.y) * width + Math.floor(adjustedCenter.x)) * 4;
                clusters.push({
                    x: adjustedCenter.x,
                    y: adjustedCenter.y,
                    r: data[pixelIndex],
                    g: data[pixelIndex + 1],
                    b: data[pixelIndex + 2],
                    pixels: [],
                    colorVariance: 0
                });
            }
        }
        
        const labels = new Int32Array(width * height);
        
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const pixelIndex = (y * width + x) * 4;
                const pr = data[pixelIndex];
                const pg = data[pixelIndex + 1];
                const pb = data[pixelIndex + 2];
                
                let minDist = Infinity;
                let bestCluster = -1;
                
                const col = Math.floor(x / regionSize);
                const row = Math.floor(y / regionSize);
                
                for (let dr = -1; dr <= 1; dr++) {
                    for (let dc = -1; dc <= 1; dc++) {
                        const nr = row + dr;
                        const nc = col + dc;
                        
                        if (nr >= 0 && nr < numRows && nc >= 0 && nc < numCols) {
                            const clusterIndex = nr * numCols + nc;
                            const cluster = clusters[clusterIndex];
                            
                            const dx = x - cluster.x;
                            const dy = y - cluster.y;
                            const spatialDist = Math.sqrt(dx * dx + dy * dy);
                            
                            const dr2 = pr - cluster.r;
                            const dg2 = pg - cluster.g;
                            const db2 = pb - cluster.b;
                            const colorDist = Math.sqrt(dr2 * dr2 + dg2 * dg2 + db2 * db2);
                            
                            const m = 20;
                            const S = regionSize;
                            const Ds = spatialDist / S;
                            const Dc = colorDist / m;
                            const dist = Ds * Ds + Dc * Dc;
                            
                            if (dist < minDist) {
                                minDist = dist;
                                bestCluster = clusterIndex;
                            }
                        }
                    }
                }
                
                labels[y * width + x] = bestCluster;
                if (bestCluster >= 0) {
                    clusters[bestCluster].pixels.push({ x, y, r: pr, g: pg, b: pb });
                }
            }
        }
        
        for (const cluster of clusters) {
            if (cluster.pixels.length > 0) {
                let sumR = 0, sumG = 0, sumB = 0, sumX = 0, sumY = 0;
                
                for (const p of cluster.pixels) {
                    sumR += p.r;
                    sumG += p.g;
                    sumB += p.b;
                    sumX += p.x;
                    sumY += p.y;
                }
                
                const n = cluster.pixels.length;
                cluster.r = sumR / n;
                cluster.g = sumG / n;
                cluster.b = sumB / n;
                cluster.x = sumX / n;
                cluster.y = sumY / n;
                
                let variance = 0;
                for (const p of cluster.pixels) {
                    const dr = p.r - cluster.r;
                    const dg = p.g - cluster.g;
                    const db = p.b - cluster.b;
                    variance += dr * dr + dg * dg + db * db;
                }
                cluster.colorVariance = Math.sqrt(variance / n) / 255;
            }
        }
        
        return clusters.filter(c => c.pixels.length > 0);
    }
    
    findLocalMinimum(data, centerX, centerY, width, height, radius) {
        let minGrad = Infinity;
        let bestX = centerX;
        let bestY = centerY;
        
        for (let dy = -radius; dy <= radius; dy++) {
            for (let dx = -radius; dx <= radius; dx++) {
                const x = Math.max(1, Math.min(width - 2, centerX + dx));
                const y = Math.max(1, Math.min(height - 2, centerY + dy));
                
                const idx = (y * width + x) * 4;
                const idxRight = (y * width + x + 1) * 4;
                const idxDown = ((y + 1) * width + x) * 4;
                
                const gx = data[idxRight] - data[idx];
                const gy = data[idxDown] - data[idx];
                const grad = Math.sqrt(gx * gx + gy * gy);
                
                if (grad < minGrad) {
                    minGrad = grad;
                    bestX = x;
                    bestY = y;
                }
            }
        }
        
        return { x: bestX, y: bestY };
    }
    
    computeGradientField(width, height) {
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = width;
        tempCanvas.height = height;
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.drawImage(this.originalImage, 0, 0, width, height);
        
        const imageData = tempCtx.getImageData(0, 0, width, height);
        const data = imageData.data;
        
        const gray = new Float32Array(width * height);
        for (let i = 0; i < width * height; i++) {
            const idx = i * 4;
            gray[i] = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
        }
        
        const gradientX = new Float32Array(width * height);
        const gradientY = new Float32Array(width * height);
        const magnitude = new Float32Array(width * height);
        const direction = new Float32Array(width * height);
        
        const sobelX = [-1, 0, 1, -2, 0, 2, -1, 0, 1];
        const sobelY = [-1, -2, -1, 0, 0, 0, 1, 2, 1];
        
        for (let y = 1; y < height - 1; y++) {
            for (let x = 1; x < width - 1; x++) {
                let gx = 0, gy = 0;
                
                for (let ky = -1; ky <= 1; ky++) {
                    for (let kx = -1; kx <= 1; kx++) {
                        const pixel = gray[(y + ky) * width + (x + kx)];
                        const kidx = (ky + 1) * 3 + (kx + 1);
                        gx += pixel * sobelX[kidx];
                        gy += pixel * sobelY[kidx];
                    }
                }
                
                const idx = y * width + x;
                gradientX[idx] = gx;
                gradientY[idx] = gy;
                magnitude[idx] = Math.sqrt(gx * gx + gy * gy);
                direction[idx] = Math.atan2(gy, gx);
            }
        }
        
        const smoothMagnitude = this.boxBlur(magnitude, width, height, 3);
        const smoothDirection = this.smoothDirectionField(direction, magnitude, width, height, 5);
        
        return {
            gradientX,
            gradientY,
            magnitude: smoothMagnitude,
            direction: smoothDirection,
            width,
            height
        };
    }
    
    boxBlur(data, width, height, radius) {
        const result = new Float32Array(data.length);
        const temp = new Float32Array(data.length);
        
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                let sum = 0;
                let count = 0;
                
                for (let k = -radius; k <= radius; k++) {
                    const xx = Math.max(0, Math.min(width - 1, x + k));
                    sum += data[y * width + xx];
                    count++;
                }
                
                temp[y * width + x] = sum / count;
            }
        }
        
        for (let x = 0; x < width; x++) {
            for (let y = 0; y < height; y++) {
                let sum = 0;
                let count = 0;
                
                for (let k = -radius; k <= radius; k++) {
                    const yy = Math.max(0, Math.min(height - 1, y + k));
                    sum += temp[yy * width + x];
                    count++;
                }
                
                result[y * width + x] = sum / count;
            }
        }
        
        return result;
    }
    
    smoothDirectionField(direction, magnitude, width, height, radius) {
        const result = new Float32Array(direction.length);
        
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                let sumSin = 0;
                let sumCos = 0;
                let totalWeight = 0;
                
                for (let ky = -radius; ky <= radius; ky++) {
                    for (let kx = -radius; kx <= radius; kx++) {
                        const yy = Math.max(0, Math.min(height - 1, y + ky));
                        const xx = Math.max(0, Math.min(width - 1, x + kx));
                        const idx = yy * width + xx;
                        
                        const weight = magnitude[idx] + 0.1;
                        const angle = direction[idx];
                        
                        sumSin += Math.sin(2 * angle) * weight;
                        sumCos += Math.cos(2 * angle) * weight;
                        totalWeight += weight;
                    }
                }
                
                if (totalWeight > 0) {
                    result[y * width + x] = Math.atan2(sumSin / totalWeight, sumCos / totalWeight) / 2;
                } else {
                    result[y * width + x] = direction[y * width + x];
                }
            }
        }
        
        return result;
    }
    
    applyBrushRendering(width, height) {
        const styleConfig = this.styleConfigs[this.currentStyle];
        const brushSize = parseInt(this.brushSizeSlider.value);
        const textureStrength = parseFloat(this.textureStrengthSlider.value);
        const directionStrength = parseFloat(this.brushDirectionSlider.value);
        const colorIntensity = parseFloat(this.colorIntensitySlider.value);
        
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = width;
        tempCanvas.height = height;
        const ctx = tempCanvas.getContext('2d');
        
        const sourceCanvas = document.createElement('canvas');
        sourceCanvas.width = width;
        sourceCanvas.height = height;
        const sourceCtx = sourceCanvas.getContext('2d');
        sourceCtx.drawImage(this.originalImage, 0, 0, width, height);
        const sourceData = sourceCtx.getImageData(0, 0, width, height);
        
        ctx.fillStyle = '#f5f0e6';
        ctx.fillRect(0, 0, width, height);
        
        const baseCanvas = this.createCanvasTexture(width, height, textureStrength);
        ctx.drawImage(baseCanvas, 0, 0);
        
        ctx.globalAlpha = 0.8;
        
        const sortedSuperpixels = [...this.superpixels].sort((a, b) => {
            return (a.y * width + a.x) - (b.y * width + b.x);
        });
        
        for (const sp of sortedSuperpixels) {
            const clusterAngle = this.getClusterDirection(sp, width, height);
            const clusterMagnitude = this.getClusterMagnitude(sp, width, height);
            
            const randomAngle = Math.random() * Math.PI - Math.PI / 2;
            const effectiveAngle = this.lerpAngle(
                randomAngle,
                clusterAngle,
                directionStrength
            );
            
            const baseR = sp.r * colorIntensity;
            const baseG = sp.g * colorIntensity;
            const baseB = sp.b * colorIntensity;
            
            const originalR = sp.r;
            const originalG = sp.g;
            const originalB = sp.b;
            
            const numStrokes = Math.max(1, Math.floor(sp.pixels.length / (brushSize * brushSize)));
            
            for (let i = 0; i < numStrokes; i++) {
                const pixel = sp.pixels[Math.floor(Math.random() * sp.pixels.length)];
                if (!pixel) continue;
                
                const strokeAngle = this.lerpAngle(
                    effectiveAngle,
                    effectiveAngle + (Math.random() - 0.5) * 0.5,
                    0.5
                );
                
                const colorVar = styleConfig.colorVariation;
                const maxColorDeviation = 80;
                
                let r = baseR + (Math.random() - 0.5) * 255 * colorVar;
                let g = baseG + (Math.random() - 0.5) * 255 * colorVar;
                let b = baseB + (Math.random() - 0.5) * 255 * colorVar;
                
                r = this.clampColor(r, originalR, maxColorDeviation);
                g = this.clampColor(g, originalG, maxColorDeviation);
                b = this.clampColor(b, originalB, maxColorDeviation);
                
                const lengthScale = styleConfig.brushLengthRatio * (1 + clusterMagnitude * directionStrength);
                const strokeLength = brushSize * lengthScale * (0.8 + Math.random() * 0.4);
                const strokeWidth = brushSize * (0.6 + Math.random() * 0.4);
                
                const opacityVar = styleConfig.opacityVariation;
                const alpha = 0.6 + Math.random() * (0.4 - opacityVar * 0.4);
                
                this.drawBrushStroke(
                    ctx,
                    pixel.x,
                    pixel.y,
                    strokeLength,
                    strokeWidth,
                    strokeAngle,
                    r, g, b,
                    alpha,
                    styleConfig,
                    textureStrength
                );
            }
        }
        
        ctx.globalAlpha = 1;
        
        if (textureStrength > 0.3) {
            this.applyVarnishTexture(ctx, width, height, textureStrength * 0.5);
        }
        
        this.applyColorGrading(ctx, width, height, styleConfig, sourceData);
        
        const enablePhysics = this.enablePhysicsCheckbox.checked;
        
        if (enablePhysics) {
            this.simulatePaintPhysics(ctx, width, height, sortedSuperpixels);
            this.computeThicknessAndSpecular(ctx, width, height);
        } else {
            this.thicknessMap = null;
            this.specularMap = null;
            this.paintParticles = [];
        }
        
        return ctx.getImageData(0, 0, width, height);
    }
    
    createCanvasTexture(width, height, strength) {
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        
        const imageData = ctx.createImageData(width, height);
        const data = imageData.data;
        
        for (let i = 0; i < data.length; i += 4) {
            const noise = (Math.random() - 0.5) * 30 * strength;
            const base = 245 + noise;
            data[i] = Math.min(255, Math.max(0, base));
            data[i + 1] = Math.min(255, Math.max(0, base - 3 + noise * 0.5));
            data[i + 2] = Math.min(255, Math.max(0, base - 8 + noise * 0.3));
            data[i + 3] = 255;
        }
        
        ctx.putImageData(imageData, 0, 0);
        return canvas;
    }
    
    getClusterDirection(superpixel, width, height) {
        if (!this.gradientField) return Math.random() * Math.PI;
        
        let sumSin = 0;
        let sumCos = 0;
        let totalWeight = 0;
        
        for (const p of superpixel.pixels) {
            const idx = Math.floor(p.y) * width + Math.floor(p.x);
            const mag = this.gradientField.magnitude[idx] || 0.1;
            const dir = this.gradientField.direction[idx] || 0;
            
            sumSin += Math.sin(2 * dir) * mag;
            sumCos += Math.cos(2 * dir) * mag;
            totalWeight += mag;
        }
        
        if (totalWeight > 0) {
            return Math.atan2(sumSin / totalWeight, sumCos / totalWeight) / 2 + Math.PI / 2;
        }
        
        return Math.random() * Math.PI;
    }
    
    getClusterMagnitude(superpixel, width, height) {
        if (!this.gradientField) return 0.5;
        
        let sumMag = 0;
        for (const p of superpixel.pixels) {
            const idx = Math.floor(p.y) * width + Math.floor(p.x);
            sumMag += this.gradientField.magnitude[idx] || 0;
        }
        
        const avgMag = sumMag / superpixel.pixels.length;
        return Math.min(1, avgMag / 100);
    }
    
    drawBrushStroke(ctx, x, y, length, width, angle, r, g, b, alpha, styleConfig, textureStrength) {
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(angle);
        
        const halfLength = length / 2;
        const halfWidth = width / 2;
        
        const gradient = ctx.createLinearGradient(-halfLength, 0, halfLength, 0);
        const edgeSoftness = styleConfig.edgeSoftness;
        
        const colorStart = `rgba(${r}, ${g}, ${b}, ${alpha})`;
        const colorMid = `rgba(${r}, ${g}, ${b}, ${alpha * (1 + edgeSoftness * 0.3)})`;
        const colorEnd = `rgba(${r}, ${g}, ${b}, ${alpha * 0.7})`;
        
        gradient.addColorStop(0, colorStart);
        gradient.addColorStop(0.3, colorMid);
        gradient.addColorStop(0.7, colorMid);
        gradient.addColorStop(1, colorEnd);
        
        ctx.fillStyle = gradient;
        
        switch (styleConfig.brushShape) {
            case 'ellipse':
                this.drawEllipseStroke(ctx, halfLength, halfWidth, styleConfig, textureStrength, r, g, b, alpha);
                break;
            case 'circle':
                this.drawPointillistStroke(ctx, halfLength, halfWidth, styleConfig, textureStrength, r, g, b, alpha);
                break;
            case 'irregular':
                this.drawIrregularStroke(ctx, halfLength, halfWidth, styleConfig, textureStrength, r, g, b, alpha);
                break;
            default:
                this.drawEllipseStroke(ctx, halfLength, halfWidth, styleConfig, textureStrength, r, g, b, alpha);
        }
        
        ctx.restore();
    }
    
    drawEllipseStroke(ctx, halfLength, halfWidth, styleConfig, textureStrength, r, g, b, alpha) {
        ctx.beginPath();
        ctx.ellipse(0, 0, halfLength, halfWidth, 0, 0, Math.PI * 2);
        ctx.fill();
        
        if (textureStrength > 0.3) {
            ctx.globalAlpha = textureStrength * 0.3;
            ctx.globalCompositeOperation = 'overlay';
            
            for (let i = 0; i < 3; i++) {
                const offsetX = (Math.random() - 0.5) * halfLength;
                const offsetY = (Math.random() - 0.5) * halfWidth;
                const noiseR = this.clampColor(r + (Math.random() - 0.5) * 40 * textureStrength, r, 30);
                const noiseG = this.clampColor(g + (Math.random() - 0.5) * 40 * textureStrength, g, 30);
                const noiseB = this.clampColor(b + (Math.random() - 0.5) * 40 * textureStrength, b, 30);
                
                ctx.fillStyle = `rgb(${noiseR}, ${noiseG}, ${noiseB})`;
                ctx.beginPath();
                ctx.ellipse(
                    offsetX, offsetY,
                    halfLength * (0.3 + Math.random() * 0.3),
                    halfWidth * (0.3 + Math.random() * 0.3),
                    (Math.random() - 0.5) * 0.5,
                    0, Math.PI * 2
                );
                ctx.fill();
            }
            
            ctx.globalCompositeOperation = 'source-over';
            ctx.globalAlpha = 1;
        }
    }
    
    drawPointillistStroke(ctx, halfLength, halfWidth, styleConfig, textureStrength, r, g, b, alpha) {
        const numDots = 4 + Math.floor(Math.random() * 4);
        
        const regionWidth = halfLength * 0.8;
        const regionHeight = halfWidth * 0.8;
        const minDist = Math.max(halfWidth * 0.25, 2);
        
        const dotPositions = this.poissonDiskSampling(
            regionWidth * 2,
            regionHeight * 2,
            minDist,
            numDots,
            20
        );
        
        for (const pos of dotPositions) {
            const offsetX = pos.x * 0.5;
            const offsetY = pos.y * 0.5;
            const dotRadius = halfWidth * (0.35 + Math.random() * 0.5);
            
            const dotR = this.clampColor(r + (Math.random() - 0.5) * 60, r, 50);
            const dotG = this.clampColor(g + (Math.random() - 0.5) * 60, g, 50);
            const dotB = this.clampColor(b + (Math.random() - 0.5) * 60, b, 50);
            const dotAlpha = alpha * (0.5 + Math.random() * 0.5);
            
            const gradient = ctx.createRadialGradient(
                offsetX, offsetY, 0,
                offsetX, offsetY, dotRadius
            );
            gradient.addColorStop(0, `rgba(${dotR}, ${dotG}, ${dotB}, ${dotAlpha})`);
            gradient.addColorStop(0.7, `rgba(${dotR}, ${dotG}, ${dotB}, ${dotAlpha * 0.7})`);
            gradient.addColorStop(1, `rgba(${dotR}, ${dotG}, ${dotB}, 0)`);
            
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(offsetX, offsetY, dotRadius, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    
    drawIrregularStroke(ctx, halfLength, halfWidth, styleConfig, textureStrength, r, g, b, alpha) {
        ctx.beginPath();
        
        const numPoints = 8;
        const angleStep = (Math.PI * 2) / numPoints;
        
        for (let i = 0; i < numPoints; i++) {
            const angle = i * angleStep;
            const radiusVariation = 0.7 + Math.random() * 0.6;
            
            let px = Math.cos(angle) * halfLength * radiusVariation;
            let py = Math.sin(angle) * halfWidth * radiusVariation;
            
            px += (Math.random() - 0.5) * halfLength * 0.2;
            py += (Math.random() - 0.5) * halfWidth * 0.2;
            
            if (i === 0) {
                ctx.moveTo(px, py);
            } else {
                const prevAngle = (i - 1) * angleStep;
                const prevX = Math.cos(prevAngle) * halfLength;
                const prevY = Math.sin(prevAngle) * halfWidth;
                const cpx = (prevX + px) / 2 + (Math.random() - 0.5) * halfLength * 0.3;
                const cpy = (prevY + py) / 2 + (Math.random() - 0.5) * halfWidth * 0.3;
                ctx.quadraticCurveTo(cpx, cpy, px, py);
            }
        }
        
        ctx.closePath();
        ctx.fill();
        
        if (textureStrength > 0.2) {
            ctx.globalAlpha = textureStrength * 0.4;
            ctx.globalCompositeOperation = 'source-atop';
            
            for (let i = 0; i < 2; i++) {
                const scratchAngle = Math.random() * Math.PI;
                const scratchLength = halfLength * (0.5 + Math.random() * 0.5);
                const scratchX = (Math.random() - 0.5) * halfLength * 0.5;
                const scratchY = (Math.random() - 0.5) * halfWidth * 0.5;
                
                const scratchR = this.clampColor(r + 30, r, 30);
                const scratchG = this.clampColor(g + 30, g, 30);
                const scratchB = this.clampColor(b + 30, b, 30);
                ctx.strokeStyle = `rgba(${scratchR}, ${scratchG}, ${scratchB}, ${alpha * 0.3})`;
                ctx.lineWidth = 1 + Math.random() * 2;
                ctx.beginPath();
                ctx.moveTo(scratchX - Math.cos(scratchAngle) * scratchLength / 2, 
                          scratchY - Math.sin(scratchAngle) * scratchLength / 2);
                ctx.lineTo(scratchX + Math.cos(scratchAngle) * scratchLength / 2,
                          scratchY + Math.sin(scratchAngle) * scratchLength / 2);
                ctx.stroke();
            }
            
            ctx.globalCompositeOperation = 'source-over';
            ctx.globalAlpha = 1;
        }
    }
    
    applyVarnishTexture(ctx, width, height, strength) {
        const textureCanvas = document.createElement('canvas');
        textureCanvas.width = width;
        textureCanvas.height = height;
        const textureCtx = textureCanvas.getContext('2d');
        
        const imageData = textureCtx.createImageData(width, height);
        const data = imageData.data;
        
        for (let i = 0; i < data.length; i += 4) {
            const noise = (Math.random() - 0.5) * 50 * strength;
            data[i] = 200 + noise;
            data[i + 1] = 180 + noise * 0.8;
            data[i + 2] = 150 + noise * 0.6;
            data[i + 3] = Math.floor(30 * strength);
        }
        
        textureCtx.putImageData(imageData, 0, 0);
        ctx.globalCompositeOperation = 'overlay';
        ctx.globalAlpha = strength * 0.3;
        ctx.drawImage(textureCanvas, 0, 0);
        ctx.globalCompositeOperation = 'source-over';
        ctx.globalAlpha = 1;
    }
    
    applyColorGrading(ctx, width, height, styleConfig, sourceData) {
        const imageData = ctx.getImageData(0, 0, width, height);
        const data = imageData.data;
        const sourcePixels = sourceData.data;
        
        const saturation = styleConfig.saturationBoost;
        const contrast = styleConfig.contrastBoost;
        const maxColorShift = 60;
        
        for (let i = 0; i < data.length; i += 4) {
            const origR = sourcePixels[i];
            const origG = sourcePixels[i + 1];
            const origB = sourcePixels[i + 2];
            
            let r = data[i];
            let g = data[i + 1];
            let b = data[i + 2];
            
            r = ((r / 255 - 0.5) * contrast + 0.5) * 255;
            g = ((g / 255 - 0.5) * contrast + 0.5) * 255;
            b = ((b / 255 - 0.5) * contrast + 0.5) * 255;
            
            const gray = 0.299 * r + 0.587 * g + 0.114 * b;
            r = gray + (r - gray) * saturation;
            g = gray + (g - gray) * saturation;
            b = gray + (b - gray) * saturation;
            
            r = this.clampColor(r, origR, maxColorShift);
            g = this.clampColor(g, origG, maxColorShift);
            b = this.clampColor(b, origB, maxColorShift);
            
            data[i] = Math.min(255, Math.max(0, r));
            data[i + 1] = Math.min(255, Math.max(0, g));
            data[i + 2] = Math.min(255, Math.max(0, b));
        }
        
        ctx.putImageData(imageData, 0, 0);
    }
    
    drawDirectionField() {
        if (!this.gradientField) return;
        
        const { width, height, direction, magnitude } = this.gradientField;
        const ctx = this.overlayCtx;
        
        ctx.clearRect(0, 0, width, height);
        
        const step = Math.max(10, Math.floor(width / 100));
        
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.lineWidth = 1.5;
        
        for (let y = step; y < height - step; y += step) {
            for (let x = step; x < width - step; x += step) {
                const idx = y * width + x;
                const angle = direction[idx];
                const mag = Math.min(1, magnitude[idx] / 50);
                
                if (mag > 0.1) {
                    const length = step * 0.4 + mag * step * 0.4;
                    
                    const x1 = x - Math.cos(angle) * length / 2;
                    const y1 = y - Math.sin(angle) * length / 2;
                    const x2 = x + Math.cos(angle) * length / 2;
                    const y2 = y + Math.sin(angle) * length / 2;
                    
                    const hue = (angle + Math.PI / 2) * (180 / Math.PI) + 180;
                    ctx.strokeStyle = `hsla(${hue}, 80%, 60%, ${0.5 + mag * 0.5})`;
                    
                    ctx.beginPath();
                    ctx.moveTo(x1, y1);
                    ctx.lineTo(x2, y2);
                    ctx.stroke();
                    
                    const arrowSize = 3 + mag * 3;
                    const arrowAngle = Math.PI / 6;
                    
                    ctx.beginPath();
                    ctx.moveTo(x2, y2);
                    ctx.lineTo(
                        x2 - arrowSize * Math.cos(angle - arrowAngle),
                        y2 - arrowSize * Math.sin(angle - arrowAngle)
                    );
                    ctx.moveTo(x2, y2);
                    ctx.lineTo(
                        x2 - arrowSize * Math.cos(angle + arrowAngle),
                        y2 - arrowSize * Math.sin(angle + arrowAngle)
                    );
                    ctx.stroke();
                }
            }
        }
    }
    
    drawSuperpixelBoundaries() {
        if (!this.gradientField || this.superpixels.length === 0) return;
        
        const { width, height } = this.gradientField;
        const ctx = this.overlayCtx;
        
        ctx.clearRect(0, 0, width, height);
        
        const labels = new Int32Array(width * height);
        for (let i = 0; i < this.superpixels.length; i++) {
            for (const p of this.superpixels[i].pixels) {
                labels[Math.floor(p.y) * width + Math.floor(p.x)] = i;
            }
        }
        
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
        ctx.lineWidth = 1;
        
        for (let y = 1; y < height - 1; y++) {
            for (let x = 1; x < width - 1; x++) {
                const current = labels[y * width + x];
                const right = labels[y * width + x + 1];
                const down = labels[(y + 1) * width + x];
                
                if (current !== right) {
                    ctx.beginPath();
                    ctx.moveTo(x + 0.5, y - 1);
                    ctx.lineTo(x + 0.5, y + 2);
                    ctx.stroke();
                }
                
                if (current !== down) {
                    ctx.beginPath();
                    ctx.moveTo(x - 1, y + 0.5);
                    ctx.lineTo(x + 2, y + 0.5);
                    ctx.stroke();
                }
            }
        }
        
        ctx.fillStyle = 'rgba(255, 100, 100, 0.8)';
        for (const sp of this.superpixels) {
            ctx.beginPath();
            ctx.arc(sp.x, sp.y, 2, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    
    exportPNG() {
        if (!this.processedImageData) return;
        
        const exportCanvas = document.createElement('canvas');
        exportCanvas.width = this.processedImageData.width;
        exportCanvas.height = this.processedImageData.height;
        const ctx = exportCanvas.getContext('2d');
        ctx.putImageData(this.processedImageData, 0, 0);
        
        const link = document.createElement('a');
        link.download = `oil_painting_${this.currentStyle}_${Date.now()}.png`;
        link.href = exportCanvas.toDataURL('image/png');
        link.click();
    }
    
    async exportPSD() {
        if (!this.processedImageData || !this.originalImage) return;
        
        this.showLoading('正在生成PSD文件...');
        
        try {
            const resolution = document.querySelector('input[name="resolution"]:checked').value;
            const { width, height } = this.getTargetResolution(resolution);
            
            const bgCanvas = document.createElement('canvas');
            bgCanvas.width = width;
            bgCanvas.height = height;
            const bgCtx = bgCanvas.getContext('2d');
            bgCtx.fillStyle = '#f5f0e6';
            bgCtx.fillRect(0, 0, width, height);
            
            const textureCanvas = this.createCanvasTexture(width, height, 0.3);
            
            const originalCanvas = document.createElement('canvas');
            originalCanvas.width = width;
            originalCanvas.height = height;
            const originalCtx = originalCanvas.getContext('2d');
            originalCtx.drawImage(this.originalImage, 0, 0, width, height);
            
            const processedCanvas = document.createElement('canvas');
            processedCanvas.width = width;
            processedCanvas.height = height;
            const processedCtx = processedCanvas.getContext('2d');
            processedCtx.putImageData(this.processedImageData, 0, 0);
            
            if (typeof window.AgPsd === 'undefined') {
                alert('PSD导出库加载失败，请刷新页面后重试');
                this.hideLoading();
                return;
            }
            
            const { writePsdBuffer, fromCanvas } = window.AgPsd;
            
            const psd = {
                width,
                height,
                channels: 3,
                bitsPerChannel: 8,
                colorMode: 3,
                children: [
                    {
                        name: '油画效果',
                        canvas: fromCanvas(processedCanvas),
                        opacity: 255,
                        blendMode: 'normal'
                    },
                    {
                        name: '原图',
                        canvas: fromCanvas(originalCanvas),
                        opacity: 0,
                        blendMode: 'normal'
                    },
                    {
                        name: '画布纹理',
                        canvas: fromCanvas(textureCanvas),
                        opacity: 77,
                        blendMode: 'multiply'
                    },
                    {
                        name: '背景',
                        canvas: fromCanvas(bgCanvas),
                        opacity: 255,
                        blendMode: 'normal'
                    }
                ]
            };
            
            const buffer = writePsdBuffer(psd);
            const blob = new Blob([buffer], { type: 'application/octet-stream' });
            
            const link = document.createElement('a');
            link.download = `oil_painting_${this.currentStyle}_${Date.now()}.psd`;
            link.href = URL.createObjectURL(blob);
            link.click();
            
            setTimeout(() => URL.revokeObjectURL(link.href), 1000);
            
        } catch (error) {
            console.error('PSD导出错误:', error);
            alert('PSD导出失败: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }
    
    showLoading(text) {
        this.loadingText.textContent = text;
        this.loadingOverlay.hidden = false;
    }
    
    hideLoading() {
        this.loadingOverlay.hidden = true;
    }
    
    lerp(a, b, t) {
        return a + (b - a) * t;
    }
    
    lerpAngle(a, b, t) {
        const diff = b - a;
        const adjustedDiff = ((diff + Math.PI) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2) - Math.PI;
        return a + adjustedDiff * t;
    }
    
    poissonDiskSampling(width, height, minDist, numPoints, maxAttempts = 30) {
        const cellSize = minDist / Math.sqrt(2);
        const gridCols = Math.ceil(width / cellSize);
        const gridRows = Math.ceil(height / cellSize);
        const grid = new Array(gridCols * gridRows).fill(-1);
        const points = [];
        const activeList = [];
        
        const halfW = width / 2;
        const halfH = height / 2;
        
        const getGridIndex = (x, y) => {
            const gx = Math.floor((x + halfW) / cellSize);
            const gy = Math.floor((y + halfH) / cellSize);
            return gy * gridCols + gx;
        };
        
        const isValidPoint = (x, y) => {
            if (Math.abs(x) > halfW || Math.abs(y) > halfH) return false;
            
            const gx = Math.floor((x + halfW) / cellSize);
            const gy = Math.floor((y + halfH) / cellSize);
            
            for (let dy = -2; dy <= 2; dy++) {
                for (let dx = -2; dx <= 2; dx++) {
                    const ngx = gx + dx;
                    const ngy = gy + dy;
                    if (ngx >= 0 && ngx < gridCols && ngy >= 0 && ngy < gridRows) {
                        const neighborIdx = grid[ngy * gridCols + ngx];
                        if (neighborIdx !== -1) {
                            const neighbor = points[neighborIdx];
                            const distX = x - neighbor.x;
                            const distY = y - neighbor.y;
                            if (distX * distX + distY * distY < minDist * minDist) {
                                return false;
                            }
                        }
                    }
                }
            }
            return true;
        };
        
        if (numPoints > 0) {
            const firstX = (Math.random() - 0.5) * width;
            const firstY = (Math.random() - 0.5) * height;
            points.push({ x: firstX, y: firstY });
            activeList.push(0);
            grid[getGridIndex(firstX, firstY)] = 0;
        }
        
        while (points.length < numPoints && activeList.length > 0) {
            const activeIdx = Math.floor(Math.random() * activeList.length);
            const currentIdx = activeList[activeIdx];
            const current = points[currentIdx];
            
            let found = false;
            
            for (let attempt = 0; attempt < maxAttempts; attempt++) {
                const angle = Math.random() * Math.PI * 2;
                const dist = minDist + Math.random() * minDist;
                const newX = current.x + Math.cos(angle) * dist;
                const newY = current.y + Math.sin(angle) * dist;
                
                if (isValidPoint(newX, newY)) {
                    const newIdx = points.length;
                    points.push({ x: newX, y: newY });
                    activeList.push(newIdx);
                    grid[getGridIndex(newX, newY)] = newIdx;
                    found = true;
                    break;
                }
            }
            
            if (!found) {
                activeList.splice(activeIdx, 1);
            }
        }
        
        while (points.length < numPoints) {
            const newX = (Math.random() - 0.5) * width;
            const newY = (Math.random() - 0.5) * height;
            if (isValidPoint(newX, newY)) {
                const newIdx = points.length;
                points.push({ x: newX, y: newY });
                activeList.push(newIdx);
                grid[getGridIndex(newX, newY)] = newIdx;
            }
        }
        
        return points.slice(0, numPoints);
    }
    
    clampColor(value, original, maxDeviation = 80) {
        const minVal = Math.max(0, original - maxDeviation);
        const maxVal = Math.min(255, original + maxDeviation);
        return Math.max(minVal, Math.min(maxVal, value));
    }
    
    simulatePaintPhysics(ctx, width, height, superpixels) {
        const paintThickness = parseFloat(this.paintThicknessSlider.value);
        const paintWetness = parseFloat(this.paintWetnessSlider.value);
        const paintMixing = parseFloat(this.paintMixingSlider.value);
        
        this.paintParticles = [];
        
        for (const sp of superpixels) {
            const numParticles = Math.max(2, Math.floor(sp.pixels.length / 50));
            
            for (let i = 0; i < numParticles; i++) {
                const pixel = sp.pixels[Math.floor(Math.random() * sp.pixels.length)];
                if (!pixel) continue;
                
                const idx = Math.floor(pixel.y) * width + Math.floor(pixel.x);
                const mag = this.gradientField ? (this.gradientField.magnitude[idx] || 0) : 0;
                const dir = this.gradientField ? (this.gradientField.direction[idx] || 0) : Math.random() * Math.PI;
                
                const flowSpeed = paintWetness * (mag / 100);
                const flowX = Math.cos(dir + Math.PI / 2) * flowSpeed * 3;
                const flowY = Math.sin(dir + Math.PI / 2) * flowSpeed * 3 + paintThickness * 2;
                
                const sizeVariation = 0.5 + Math.random() * 0.5;
                const particleSize = Math.max(1, paintThickness * 8 * sizeVariation);
                
                this.paintParticles.push({
                    x: pixel.x,
                    y: pixel.y,
                    originX: pixel.x,
                    originY: pixel.y,
                    r: sp.r,
                    g: sp.g,
                    b: sp.b,
                    size: particleSize,
                    thickness: paintThickness * (0.5 + Math.random() * 0.5),
                    flowX,
                    flowY,
                    age: 0,
                    maxAge: 10 + Math.floor(Math.random() * 10),
                    wetness: paintWetness
                });
            }
        }
        
        if (paintMixing > 0.2) {
            this.simulateParticleMixing(width, height, paintMixing);
        }
        
        this.applyParticlePainting(ctx, width, height);
    }
    
    simulateParticleMixing(width, height, mixingStrength) {
        const gridSize = 20;
        const gridCols = Math.ceil(width / gridSize);
        const gridRows = Math.ceil(height / gridSize);
        const grid = new Array(gridCols * gridRows).fill(null).map(() => []);
        
        for (const p of this.paintParticles) {
            const gx = Math.floor(p.x / gridSize);
            const gy = Math.floor(p.y / gridSize);
            if (gx >= 0 && gx < gridCols && gy >= 0 && gy < gridRows) {
                grid[gy * gridCols + gx].push(p);
            }
        }
        
        for (const p of this.paintParticles) {
            const gx = Math.floor(p.x / gridSize);
            const gy = Math.floor(p.y / gridSize);
            
            for (let dy = -1; dy <= 1; dy++) {
                for (let dx = -1; dx <= 1; dx++) {
                    const ngx = gx + dx;
                    const ngy = gy + dy;
                    if (ngx >= 0 && ngx < gridCols && ngy >= 0 && ngy < gridRows) {
                        const neighbors = grid[ngy * gridCols + ngx];
                        
                        for (const np of neighbors) {
                            if (np === p) continue;
                            
                            const dist = Math.sqrt((p.x - np.x) ** 2 + (p.y - np.y) ** 2);
                            if (dist < 30 && Math.random() < mixingStrength * 0.1) {
                                const mixFactor = mixingStrength * 0.2;
                                p.r = this.lerp(p.r, np.r, mixFactor);
                                p.g = this.lerp(p.g, np.g, mixFactor);
                                p.b = this.lerp(p.b, np.b, mixFactor);
                                np.r = this.lerp(np.r, p.r, mixFactor);
                                np.g = this.lerp(np.g, p.g, mixFactor);
                                np.b = this.lerp(np.b, p.b, mixFactor);
                            }
                        }
                    }
                }
            }
        }
    }
    
    applyParticlePainting(ctx, width, height) {
        ctx.globalCompositeOperation = 'source-over';
        
        for (const p of this.paintParticles) {
            const finalX = p.x + p.flowX;
            const finalY = p.y + p.flowY;
            
            if (finalX < 0 || finalX >= width || finalY < 0 || finalY >= height) continue;
            
            const gradient = ctx.createRadialGradient(
                finalX, finalY, 0,
                finalX, finalY, p.size
            );
            
            const alpha = p.thickness * 0.4;
            gradient.addColorStop(0, `rgba(${p.r}, ${p.g}, ${p.b}, ${alpha})`);
            gradient.addColorStop(0.5, `rgba(${p.r}, ${p.g}, ${p.b}, ${alpha * 0.5})`);
            gradient.addColorStop(1, `rgba(${p.r}, ${p.g}, ${p.b}, 0)`);
            
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(finalX, finalY, p.size, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    
    computeThicknessAndSpecular(ctx, width, height) {
        const specularStrength = parseFloat(this.specularStrengthSlider.value);
        
        this.thicknessMap = new Float32Array(width * height);
        this.specularMap = new Float32Array(width * height);
        
        for (const p of this.paintParticles) {
            const px = Math.floor(p.x);
            const py = Math.floor(p.y);
            
            for (let dy = -3; dy <= 3; dy++) {
                for (let dx = -3; dx <= 3; dx++) {
                    const x = px + dx;
                    const y = py + dy;
                    if (x < 0 || x >= width || y < 0 || y >= height) continue;
                    
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist <= p.size) {
                        const falloff = 1 - dist / p.size;
                        const idx = y * width + x;
                        this.thicknessMap[idx] += p.thickness * falloff * 0.3;
                    }
                }
            }
        }
        
        for (let i = 0; i < this.thicknessMap.length; i++) {
            this.thicknessMap[i] = Math.min(1, this.thicknessMap[i]);
        }
        
        for (let y = 1; y < height - 1; y++) {
            for (let x = 1; x < width - 1; x++) {
                const idx = y * width + x;
                const t = this.thicknessMap[idx];
                
                const tx = this.thicknessMap[idx + 1] - this.thicknessMap[idx - 1];
                const ty = this.thicknessMap[idx + width] - this.thicknessMap[idx - width];
                
                const nx = -tx;
                const ny = -ty;
                const nz = 1;
                const nLen = Math.sqrt(nx * nx + ny * ny + nz * nz);
                
                const lx = 0.5, ly = -0.5, lz = 0.7;
                const lLen = Math.sqrt(lx * lx + ly * ly + lz * lz);
                
                const dot = (nx * lx + ny * ly + nz * lz) / (nLen * lLen);
                const specular = Math.pow(Math.max(0, dot), 32) * specularStrength * t;
                
                this.specularMap[idx] = specular;
            }
        }
        
        this.applySpecularHighlight(ctx, width, height);
    }
    
    applySpecularHighlight(ctx, width, height) {
        if (!this.specularMap) return;
        
        const imageData = ctx.getImageData(0, 0, width, height);
        const data = imageData.data;
        
        for (let i = 0; i < data.length; i += 4) {
            const specular = this.specularMap[i / 4] || 0;
            
            if (specular > 0) {
                data[i] = Math.min(255, data[i] + specular * 255);
                data[i + 1] = Math.min(255, data[i + 1] + specular * 255);
                data[i + 2] = Math.min(255, data[i + 2] + specular * 255);
            }
        }
        
        ctx.putImageData(imageData, 0, 0);
    }
    
    drawThicknessMap() {
        if (!this.thicknessMap) return;
        
        const { width, height } = this.thicknessCanvas;
        const ctx = this.thicknessCtx;
        
        const imageData = ctx.createImageData(width, height);
        const data = imageData.data;
        
        for (let i = 0; i < this.thicknessMap.length; i++) {
            const t = this.thicknessMap[i];
            const idx = i * 4;
            
            const intensity = Math.min(255, t * 255 * 2);
            data[idx] = intensity;
            data[idx + 1] = Math.min(255, intensity * 0.8);
            data[idx + 2] = Math.min(255, intensity * 0.6);
            data[idx + 3] = 255;
        }
        
        ctx.putImageData(imageData, 0, 0);
    }
    
    drawParticlesView() {
        const { width, height } = this.particlesCanvas;
        const ctx = this.particlesCtx;
        
        ctx.clearRect(0, 0, width, height);
        
        ctx.fillStyle = '#1a1a2e';
        ctx.fillRect(0, 0, width, height);
        
        for (const p of this.paintParticles) {
            const finalX = p.x + p.flowX;
            const finalY = p.y + p.flowY;
            
            ctx.strokeStyle = `rgba(${p.r}, ${p.g}, ${p.b}, 0.3)`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(p.originX, p.originY);
            ctx.lineTo(finalX, finalY);
            ctx.stroke();
            
            const gradient = ctx.createRadialGradient(
                finalX, finalY, 0,
                finalX, finalY, p.size * 1.5
            );
            gradient.addColorStop(0, `rgba(${p.r}, ${p.g}, ${p.b}, 0.9)`);
            gradient.addColorStop(0.5, `rgba(${p.r}, ${p.g}, ${p.b}, 0.5)`);
            gradient.addColorStop(1, `rgba(${p.r}, ${p.g}, ${p.b}, 0)`);
            
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(finalX, finalY, p.size * 1.5, 0, Math.PI * 2);
            ctx.fill();
            
            ctx.fillStyle = '#fff';
            ctx.beginPath();
            ctx.arc(finalX, finalY, 2, 0, Math.PI * 2);
            ctx.fill();
        }
        
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(10, 10, 180, 60);
        ctx.fillStyle = '#fff';
        ctx.font = '12px monospace';
        ctx.fillText(`粒子总数: ${this.paintParticles.length}`, 20, 30);
        ctx.fillText(`厚度强度: ${this.paintThicknessSlider.value}`, 20, 50);
        ctx.fillText(`湿度: ${this.paintWetnessSlider.value}`, 20, 65);
    }
    
    handleStyleImages(e) {
        this.loadStyleImages(e.target.files);
    }
    
    loadStyleImages(files) {
        const imageFiles = Array.from(files).filter(f => f.type.startsWith('image/'));
        
        if (imageFiles.length < 3) {
            alert('请至少上传3张艺术家作品以进行风格学习');
            return;
        }
        
        if (imageFiles.length > 5) {
            alert('最多支持5张作品，将使用前5张');
        }
        
        this.styleImages = [];
        this.styleThumbs.innerHTML = '';
        this.learnedStyle = null;
        this.applyLearnedStyleBtn.disabled = true;
        
        let loadedCount = 0;
        const maxImages = Math.min(5, imageFiles.length);
        
        for (let i = 0; i < maxImages; i++) {
            const file = imageFiles[i];
            const reader = new FileReader();
            
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    this.styleImages.push(img);
                    
                    const thumb = document.createElement('img');
                    thumb.src = e.target.result;
                    thumb.className = 'style-thumb';
                    thumb.addEventListener('click', () => {
                        document.querySelectorAll('.style-thumb').forEach(t => t.classList.remove('active'));
                        thumb.classList.add('active');
                    });
                    this.styleThumbs.appendChild(thumb);
                    
                    loadedCount++;
                    if (loadedCount === maxImages) {
                        this.learnStyleBtn.disabled = false;
                        this.styleInfo.hidden = true;
                    }
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        }
    }
    
    async learnArtistStyle() {
        if (this.styleImages.length < 3) {
            alert('请至少上传3张艺术家作品');
            return;
        }
        
        this.showLoading('正在分析艺术家风格...');
        await this.sleep(100);
        
        try {
            const allColors = [];
            const brushStats = [];
            let totalBrightness = 0;
            let totalContrast = 0;
            
            for (const img of this.styleImages) {
                const tempCanvas = document.createElement('canvas');
                const maxSize = 300;
                const scale = Math.min(maxSize / img.width, maxSize / img.height);
                tempCanvas.width = img.width * scale;
                tempCanvas.height = img.height * scale;
                const tempCtx = tempCanvas.getContext('2d');
                tempCtx.drawImage(img, 0, 0, tempCanvas.width, tempCanvas.height);
                
                const imageData = tempCtx.getImageData(0, 0, tempCanvas.width, tempCanvas.height);
                const data = imageData.data;
                
                const imgColors = [];
                let imgBrightness = 0;
                let imgContrast = 0;
                
                for (let i = 0; i < data.length; i += 16) {
                    const r = data[i];
                    const g = data[i + 1];
                    const b = data[i + 2];
                    
                    imgColors.push({ r, g, b });
                    allColors.push({ r, g, b });
                    
                    const lum = 0.299 * r + 0.587 * g + 0.114 * b;
                    imgBrightness += lum;
                }
                
                const pixelCount = data.length / 16;
                imgBrightness /= pixelCount;
                totalBrightness += imgBrightness;
                
                for (let i = 0; i < data.length; i += 16) {
                    const lum = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
                    imgContrast += (lum - imgBrightness) ** 2;
                }
                imgContrast = Math.sqrt(imgContrast / pixelCount);
                totalContrast += imgContrast;
                
                const imgBrushStat = this.analyzeBrushStyle(tempCtx, tempCanvas.width, tempCanvas.height);
                brushStats.push(imgBrushStat);
            }
            
            const palette = this.extractPalette(allColors, 8);
            
            const avgBrushStat = {
                strokeLength: brushStats.reduce((s, b) => s + b.strokeLength, 0) / brushStats.length,
                strokeVariation: brushStats.reduce((s, b) => s + b.strokeVariation, 0) / brushStats.length,
                directionPreference: brushStats.reduce((s, b) => s + b.directionPreference, 0) / brushStats.length,
                edgeSharpness: brushStats.reduce((s, b) => s + b.edgeSharpness, 0) / brushStats.length
            };
            
            this.learnedStyle = {
                palette,
                brightness: totalBrightness / this.styleImages.length / 255,
                contrast: totalContrast / this.styleImages.length / 255,
                brushStats: avgBrushStat,
                sourceImages: this.styleImages.length
            };
            
            this.displayLearnedStyleInfo();
            this.applyLearnedStyleBtn.disabled = false;
            this.clearStyleBtn.disabled = false;
            this.styleInfo.hidden = false;
            
        } catch (error) {
            console.error('风格学习错误:', error);
            alert('风格学习失败: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }
    
    analyzeBrushStyle(ctx, width, height) {
        const sobelX = [-1, 0, 1, -2, 0, 2, -1, 0, 1];
        const sobelY = [-1, -2, -1, 0, 0, 0, 1, 2, 1];
        
        const imageData = ctx.getImageData(0, 0, width, height);
        const data = imageData.data;
        
        const gray = new Float32Array(width * height);
        for (let i = 0; i < width * height; i++) {
            const idx = i * 4;
            gray[i] = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
        }
        
        let totalEdgeStrength = 0;
        let totalEdgeDirection = 0;
        let edgeCount = 0;
        let edgeVariance = 0;
        
        for (let y = 1; y < height - 1; y++) {
            for (let x = 1; x < width - 1; x++) {
                let gx = 0, gy = 0;
                
                for (let ky = -1; ky <= 1; ky++) {
                    for (let kx = -1; kx <= 1; kx++) {
                        const pixel = gray[(y + ky) * width + (x + kx)];
                        const kidx = (ky + 1) * 3 + (kx + 1);
                        gx += pixel * sobelX[kidx];
                        gy += pixel * sobelY[kidx];
                    }
                }
                
                const mag = Math.sqrt(gx * gx + gy * gy);
                
                if (mag > 30) {
                    totalEdgeStrength += mag;
                    const dir = Math.atan2(gy, gx);
                    totalEdgeDirection += Math.abs(Math.sin(2 * dir));
                    edgeCount++;
                }
            }
        }
        
        if (edgeCount > 0) {
            const avgMag = totalEdgeStrength / edgeCount;
            
            for (let y = 1; y < height - 1; y++) {
                for (let x = 1; x < width - 1; x++) {
                    let gx = 0, gy = 0;
                    for (let ky = -1; ky <= 1; ky++) {
                        for (let kx = -1; kx <= 1; kx++) {
                            const pixel = gray[(y + ky) * width + (x + kx)];
                            const kidx = (ky + 1) * 3 + (kx + 1);
                            gx += pixel * sobelX[kidx];
                            gy += pixel * sobelY[kidx];
                        }
                    }
                    const mag = Math.sqrt(gx * gx + gy * gy);
                    if (mag > 30) {
                        edgeVariance += (mag - avgMag) ** 2;
                    }
                }
            }
            
            edgeVariance = Math.sqrt(edgeVariance / edgeCount);
        }
        
        return {
            strokeLength: totalEdgeStrength / (edgeCount || 1),
            strokeVariation: edgeVariance,
            directionPreference: totalEdgeDirection / (edgeCount || 1),
            edgeSharpness: Math.min(1, totalEdgeStrength / (width * height * 0.5))
        };
    }
    
    extractPalette(colors, numColors) {
        const buckets = new Array(numColors).fill(null).map(() => []);
        
        for (const color of colors) {
            const lum = 0.299 * color.r + 0.587 * color.g + 0.114 * color.b;
            const bucketIdx = Math.min(numColors - 1, Math.floor(lum / (256 / numColors)));
            buckets[bucketIdx].push(color);
        }
        
        const palette = [];
        for (const bucket of buckets) {
            if (bucket.length > 0) {
                let sumR = 0, sumG = 0, sumB = 0;
                for (const c of bucket) {
                    sumR += c.r;
                    sumG += c.g;
                    sumB += c.b;
                }
                palette.push({
                    r: Math.round(sumR / bucket.length),
                    g: Math.round(sumG / bucket.length),
                    b: Math.round(sumB / bucket.length),
                    weight: bucket.length / colors.length
                });
            }
        }
        
        return palette.sort((a, b) => b.weight - a.weight).slice(0, numColors);
    }
    
    displayLearnedStyleInfo() {
        if (!this.learnedStyle) return;
        
        this.styleSampleCount.textContent = this.learnedStyle.sourceImages + ' 张';
        
        this.stylePalettePreview.innerHTML = '';
        const paletteContainer = document.createElement('div');
        paletteContainer.className = 'palette-preview';
        
        for (const color of this.learnedStyle.palette.slice(0, 5)) {
            const colorSwatch = document.createElement('div');
            colorSwatch.className = 'palette-color';
            colorSwatch.style.background = `rgb(${color.r}, ${color.g}, ${color.b})`;
            colorSwatch.title = `RGB(${color.r}, ${color.g}, ${color.b})`;
            paletteContainer.appendChild(colorSwatch);
        }
        this.stylePalettePreview.appendChild(paletteContainer);
        
        const bs = this.learnedStyle.brushStats;
        if (bs.edgeSharpness > 0.5 && bs.strokeVariation > 40) {
            this.styleBrushType.textContent = '表现派 (粗犷)';
        } else if (bs.strokeLength > 60) {
            this.styleBrushType.textContent = '印象派 (流畅)';
        } else {
            this.styleBrushType.textContent = '点彩派 (细腻)';
        }
    }
    
    applyLearnedStyle() {
        if (!this.learnedStyle || !this.originalImage) {
            alert('请先学习艺术家风格并上传照片');
            return;
        }
        
        const style = this.learnedStyle;
        const bs = style.brushStats;
        
        if (bs.edgeSharpness > 0.5 && bs.strokeVariation > 40) {
            this.currentStyle = 'expressionist';
        } else if (bs.strokeLength > 60) {
            this.currentStyle = 'impressionist';
        } else {
            this.currentStyle = 'pointillist';
        }
        
        document.querySelectorAll('.style-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.style === this.currentStyle);
        });
        
        const baseConfig = { ...this.styleConfigs[this.currentStyle] };
        const customConfig = {
            ...baseConfig,
            colorVariation: baseConfig.colorVariation * (0.8 + bs.strokeVariation / 100),
            textureNoise: baseConfig.textureNoise * (0.7 + bs.edgeSharpness),
            saturationBoost: 1 + (style.brightness - 0.5) * 0.3,
            contrastBoost: 1 + (style.contrast - 0.3) * 0.5
        };
        
        const styleConfig = { ...customConfig };
        this.renderOilPaintingWithCustomStyle(styleConfig, style.palette);
    }
    
    async renderOilPaintingWithCustomStyle(customStyleConfig, palette) {
        if (!this.originalImage || this.isRendering) return;
        
        this.isRendering = true;
        this.showLoading('正在应用学习的艺术家风格...');
        
        const startTime = performance.now();
        
        try {
            const resolution = document.querySelector('input[name="resolution"]:checked').value;
            const { width, height } = this.getTargetResolution(resolution);
            
            await this.sleep(50);
            
            this.loadingText.textContent = '正在计算超像素分割...';
            this.superpixels = this.computeSuperpixels(width, height);
            this.superpixelCountEl.textContent = this.superpixels.length;
            
            await this.sleep(50);
            
            this.loadingText.textContent = '正在计算梯度方向场...';
            this.gradientField = this.computeGradientField(width, height);
            
            await this.sleep(50);
            
            this.loadingText.textContent = '正在匹配艺术家调色板...';
            this.processedImageData = this.applyBrushRenderingWithPalette(width, height, customStyleConfig, palette);
            
            this.processedCtx.putImageData(this.processedImageData, 0, 0);
            
            this.exportPngBtn.disabled = false;
            this.exportPsdBtn.disabled = false;
            
            const endTime = performance.now();
            const renderTime = ((endTime - startTime) / 1000).toFixed(2);
            this.renderTimeEl.textContent = renderTime + ' 秒';
            
            this.switchTab('processed');
            
        } catch (error) {
            console.error('风格渲染错误:', error);
            alert('渲染过程中发生错误: ' + error.message);
        } finally {
            this.isRendering = false;
            this.hideLoading();
        }
    }
    
    applyBrushRenderingWithPalette(width, height, styleConfig, palette) {
        const brushSize = parseInt(this.brushSizeSlider.value);
        const textureStrength = parseFloat(this.textureStrengthSlider.value);
        const directionStrength = parseFloat(this.brushDirectionSlider.value);
        const colorIntensity = parseFloat(this.colorIntensitySlider.value);
        
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = width;
        tempCanvas.height = height;
        const ctx = tempCanvas.getContext('2d');
        
        const sourceCanvas = document.createElement('canvas');
        sourceCanvas.width = width;
        sourceCanvas.height = height;
        const sourceCtx = sourceCanvas.getContext('2d');
        sourceCtx.drawImage(this.originalImage, 0, 0, width, height);
        const sourceData = sourceCtx.getImageData(0, 0, width, height);
        
        ctx.fillStyle = '#f5f0e6';
        ctx.fillRect(0, 0, width, height);
        
        const baseCanvas = this.createCanvasTexture(width, height, textureStrength);
        ctx.drawImage(baseCanvas, 0, 0);
        
        ctx.globalAlpha = 0.8;
        
        const sortedSuperpixels = [...this.superpixels].sort((a, b) => {
            return (a.y * width + a.x) - (b.y * width + b.x);
        });
        
        for (const sp of sortedSuperpixels) {
            const clusterAngle = this.getClusterDirection(sp, width, height);
            const clusterMagnitude = this.getClusterMagnitude(sp, width, height);
            
            const randomAngle = Math.random() * Math.PI - Math.PI / 2;
            const effectiveAngle = this.lerpAngle(
                randomAngle,
                clusterAngle,
                directionStrength
            );
            
            const originalR = sp.r;
            const originalG = sp.g;
            const originalB = sp.b;
            
            let baseR = sp.r * colorIntensity;
            let baseG = sp.g * colorIntensity;
            let baseB = sp.b * colorIntensity;
            
            if (palette && palette.length > 0) {
                const nearestColor = this.findNearestPaletteColor(baseR, baseG, baseB, palette);
                const blendFactor = 0.3;
                baseR = this.lerp(baseR, nearestColor.r, blendFactor);
                baseG = this.lerp(baseG, nearestColor.g, blendFactor);
                baseB = this.lerp(baseB, nearestColor.b, blendFactor);
            }
            
            const numStrokes = Math.max(1, Math.floor(sp.pixels.length / (brushSize * brushSize)));
            
            for (let i = 0; i < numStrokes; i++) {
                const pixel = sp.pixels[Math.floor(Math.random() * sp.pixels.length)];
                if (!pixel) continue;
                
                const strokeAngle = this.lerpAngle(
                    effectiveAngle,
                    effectiveAngle + (Math.random() - 0.5) * 0.5,
                    0.5
                );
                
                const colorVar = styleConfig.colorVariation;
                const maxColorDeviation = 80;
                
                let r = baseR + (Math.random() - 0.5) * 255 * colorVar;
                let g = baseG + (Math.random() - 0.5) * 255 * colorVar;
                let b = baseB + (Math.random() - 0.5) * 255 * colorVar;
                
                r = this.clampColor(r, originalR, maxColorDeviation);
                g = this.clampColor(g, originalG, maxColorDeviation);
                b = this.clampColor(b, originalB, maxColorDeviation);
                
                const lengthScale = styleConfig.brushLengthRatio * (1 + clusterMagnitude * directionStrength);
                const strokeLength = brushSize * lengthScale * (0.8 + Math.random() * 0.4);
                const strokeWidth = brushSize * (0.6 + Math.random() * 0.4);
                
                const opacityVar = styleConfig.opacityVariation;
                const alpha = 0.6 + Math.random() * (0.4 - opacityVar * 0.4);
                
                this.drawBrushStroke(
                    ctx,
                    pixel.x,
                    pixel.y,
                    strokeLength,
                    strokeWidth,
                    strokeAngle,
                    r, g, b,
                    alpha,
                    styleConfig,
                    textureStrength
                );
            }
        }
        
        ctx.globalAlpha = 1;
        
        if (textureStrength > 0.3) {
            this.applyVarnishTexture(ctx, width, height, textureStrength * 0.5);
        }
        
        this.applyColorGrading(ctx, width, height, styleConfig, sourceData);
        
        const enablePhysics = this.enablePhysicsCheckbox.checked;
        if (enablePhysics) {
            this.simulatePaintPhysics(ctx, width, height, sortedSuperpixels);
            this.computeThicknessAndSpecular(ctx, width, height);
        }
        
        return ctx.getImageData(0, 0, width, height);
    }
    
    findNearestPaletteColor(r, g, b, palette) {
        let minDist = Infinity;
        let nearest = palette[0];
        
        for (const color of palette) {
            const dr = r - color.r;
            const dg = g - color.g;
            const db = b - color.b;
            const dist = Math.sqrt(dr * dr + dg * dg + db * db);
            
            if (dist < minDist) {
                minDist = dist;
                nearest = color;
            }
        }
        
        return nearest;
    }
    
    clearLearnedStyle() {
        this.learnedStyle = null;
        this.styleImages = [];
        this.styleThumbs.innerHTML = '';
        this.styleInfo.hidden = true;
        this.learnStyleBtn.disabled = true;
        this.applyLearnedStyleBtn.disabled = true;
        this.clearStyleBtn.disabled = true;
        
        this.currentStyle = 'impressionist';
        document.querySelectorAll('.style-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.style === 'impressionist');
        });
    }
    
    handleVideoInput(e) {
        this.loadVideoFiles(e.target.files);
    }
    
    async loadVideoFiles(files) {
        const fileArray = Array.from(files);
        const videoFile = fileArray.find(f => f.type.startsWith('video/'));
        const imageFiles = fileArray.filter(f => f.type.startsWith('image/'));
        
        if (videoFile) {
            this.showLoading('正在解析视频帧...');
            await this.extractVideoFrames(videoFile);
        } else if (imageFiles.length > 0) {
            this.showLoading('正在加载帧序列...');
            await this.loadImageSequence(imageFiles);
        } else {
            alert('请上传视频文件或PNG/JPG帧序列');
            return;
        }
    }
    
    async extractVideoFrames(videoFile) {
        return new Promise((resolve, reject) => {
            const video = document.createElement('video');
            video.muted = true;
            video.playsInline = true;
            
            video.onloadedmetadata = async () => {
                const duration = video.duration;
                const frameRate = 10;
                const maxFrames = 30;
                const numFrames = Math.min(maxFrames, Math.floor(duration * frameRate));
                
                this.videoFrames = [];
                this.processedVideoFrames = [];
                this.opticalFlowFields = [];
                
                for (let i = 0; i < numFrames; i++) {
                    const time = (i / numFrames) * duration;
                    video.currentTime = time;
                    
                    await new Promise(res => {
                        video.onseeked = () => {
                            const canvas = document.createElement('canvas');
                            const maxSize = 1280;
                            const scale = Math.min(1, maxSize / video.videoWidth);
                            canvas.width = video.videoWidth * scale;
                            canvas.height = video.videoHeight * scale;
                            const ctx = canvas.getContext('2d');
                            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                            
                            this.videoFrames.push(canvas);
                            res();
                        };
                    });
                    
                    this.loadingText.textContent = `正在提取帧 ${i + 1}/${numFrames}...`;
                }
                
                this.updateVideoUI();
                this.hideLoading();
                resolve();
            };
            
            video.onerror = () => {
                this.hideLoading();
                reject(new Error('视频加载失败'));
            };
            
            video.src = URL.createObjectURL(videoFile);
        });
    }
    
    async loadImageSequence(imageFiles) {
        this.videoFrames = [];
        this.processedVideoFrames = [];
        this.opticalFlowFields = [];
        
        const sortedFiles = Array.from(imageFiles).sort((a, b) => a.name.localeCompare(b.name));
        
        for (let i = 0; i < Math.min(sortedFiles.length, 30); i++) {
            const file = sortedFiles[i];
            
            await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = new Image();
                    img.onload = () => {
                        const canvas = document.createElement('canvas');
                        const maxSize = 1280;
                        const scale = Math.min(1, maxSize / img.width);
                        canvas.width = img.width * scale;
                        canvas.height = img.height * scale;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                        
                        this.videoFrames.push(canvas);
                        resolve();
                    };
                    img.onerror = reject;
                    img.src = e.target.result;
                };
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
            
            this.loadingText.textContent = `正在加载帧 ${i + 1}/${Math.min(imageFiles.length, 30)}...`;
        }
        
        this.updateVideoUI();
        this.hideLoading();
    }
    
    updateVideoUI() {
        this.videoFramesEl.innerHTML = '';
        
        for (let i = 0; i < this.videoFrames.length; i++) {
            const thumb = document.createElement('img');
            thumb.src = this.videoFrames[i].toDataURL('image/jpeg', 0.3);
            thumb.className = 'video-thumb';
            thumb.addEventListener('click', () => {
                this.showVideoFrame(i);
            });
            this.videoFramesEl.appendChild(thumb);
        }
        
        this.videoFrameCount.textContent = this.videoFrames.length;
        this.videoCurrentFrame.textContent = '1';
        this.videoFrameSize.textContent = `${this.videoFrames[0].width} × ${this.videoFrames[0].height}`;
        this.videoInfo.hidden = false;
        this.processVideoBtn.disabled = false;
        
        this.showVideoFrame(0);
    }
    
    showVideoFrame(index) {
        if (index < 0 || index >= this.videoFrames.length) return;
        
        this.currentVideoFrame = index;
        this.videoCurrentFrame.textContent = (index + 1).toString();
        
        document.querySelectorAll('.video-thumb').forEach((t, i) => {
            t.classList.toggle('active', i === index);
        });
        
        const frame = this.videoFrames[index];
        this.originalImage = frame;
        this.originalWidth = frame.width;
        this.originalHeight = frame.height;
        
        this.originalSizeEl.textContent = `${frame.width} × ${frame.height}`;
        this.updateOutputSize();
        
        this.noImagePlaceholder.style.display = 'none';
        this.renderBtn.disabled = false;
        
        this.setupCanvasDimensions();
        this.displayImageOnCanvas(frame, this.originalCanvas, this.originalCtx);
        
        if (this.processedVideoFrames[index]) {
            this.processedCtx.putImageData(this.processedVideoFrames[index], 0, 0);
            this.processedImageData = this.processedVideoFrames[index];
        } else {
            this.processedCtx.clearRect(0, 0, this.processedCanvas.width, this.processedCanvas.height);
            this.processedImageData = null;
        }
        
        this.switchTab('original');
    }
    
    async processVideoStyleTransfer() {
        if (this.videoFrames.length === 0) return;
        
        this.isRendering = true;
        this.showLoading('正在处理视频风格迁移...');
        
        const temporalConsistency = parseFloat(this.temporalConsistencySlider.value);
        const enableOpticalFlow = this.enableOpticalFlowCheckbox.checked;
        
        try {
            for (let i = 0; i < this.videoFrames.length; i++) {
                this.loadingText.textContent = `处理帧 ${i + 1}/${this.videoFrames.length}...`;
                
                const frame = this.videoFrames[i];
                this.originalImage = frame;
                this.originalWidth = frame.width;
                this.originalHeight = frame.height;
                
                const width = frame.width;
                const height = frame.height;
                
                await this.sleep(50);
                this.superpixels = this.computeSuperpixels(width, height);
                
                await this.sleep(50);
                this.gradientField = this.computeGradientField(width, height);
                
                let processedData;
                if (enableOpticalFlow && i > 0 && this.opticalFlowFields[i - 1]) {
                    processedData = this.applyTemporalConsistentRendering(
                        width, height, i, temporalConsistency
                    );
                } else {
                    processedData = this.applyBrushRendering(width, height);
                }
                
                this.processedVideoFrames[i] = processedData;
                
                if (enableOpticalFlow && i < this.videoFrames.length - 1) {
                    this.loadingText.textContent = `计算光流 ${i + 1}/${this.videoFrames.length}...`;
                    this.opticalFlowFields[i] = this.computeOpticalFlow(
                        this.videoFrames[i], this.videoFrames[i + 1]
                    );
                }
                
                if (i === this.currentVideoFrame) {
                    this.processedCtx.putImageData(processedData, 0, 0);
                    this.processedImageData = processedData;
                }
            }
            
            this.exportVideoBtn.disabled = false;
            this.switchTab('processed');
            
        } catch (error) {
            console.error('视频处理错误:', error);
            alert('视频处理失败: ' + error.message);
        } finally {
            this.isRendering = false;
            this.hideLoading();
        }
    }
    
    computeOpticalFlow(frame1, frame2) {
        const width = frame1.width;
        const height = frame1.height;
        const step = 8;
        
        const ctx1 = frame1.getContext('2d');
        const ctx2 = frame2.getContext('2d');
        
        const data1 = ctx1.getImageData(0, 0, width, height).data;
        const data2 = ctx2.getImageData(0, 0, width, height).data;
        
        const flowField = {
            u: new Float32Array(Math.ceil(width / step) * Math.ceil(height / step)),
            v: new Float32Array(Math.ceil(width / step) * Math.ceil(height / step)),
            width: Math.ceil(width / step),
            height: Math.ceil(height / step),
            step
        };
        
        const sobelX = [-1, 0, 1, -2, 0, 2, -1, 0, 1];
        const sobelY = [-1, -2, -1, 0, 0, 0, 1, 2, 1];
        
        let idx = 0;
        for (let y = 0; y < height; y += step) {
            for (let x = 0; x < width; x += step) {
                let Ix = 0, Iy = 0, It = 0;
                
                for (let ky = -1; ky <= 1; ky++) {
                    for (let kx = -1; kx <= 1; kx++) {
                        const px = Math.max(0, Math.min(width - 1, x + kx));
                        const py = Math.max(0, Math.min(height - 1, y + ky));
                        const pixelIdx = (py * width + px) * 4;
                        
                        const l1 = 0.299 * data1[pixelIdx] + 0.587 * data1[pixelIdx + 1] + 0.114 * data1[pixelIdx + 2];
                        const l2 = 0.299 * data2[pixelIdx] + 0.587 * data2[pixelIdx + 1] + 0.114 * data2[pixelIdx + 2];
                        
                        const kidx = (ky + 1) * 3 + (kx + 1);
                        Ix += l1 * sobelX[kidx];
                        Iy += l1 * sobelY[kidx];
                        It += (l2 - l1);
                    }
                }
                
                const denom = Ix * Ix + Iy * Iy + 0.001;
                flowField.u[idx] = -(Ix * It) / denom;
                flowField.v[idx] = -(Iy * It) / denom;
                idx++;
            }
        }
        
        return flowField;
    }
    
    applyTemporalConsistentRendering(width, height, frameIndex, temporalStrength) {
        const styleConfig = this.styleConfigs[this.currentStyle];
        const prevProcessed = this.processedVideoFrames[frameIndex - 1];
        const flowField = this.opticalFlowFields[frameIndex - 1];
        
        const currentResult = this.applyBrushRendering(width, height);
        
        if (!prevProcessed || !flowField || temporalStrength < 0.1) {
            return currentResult;
        }
        
        const result = new ImageData(width, height);
        const currData = currentResult.data;
        const prevData = prevProcessed.data;
        const outData = result.data;
        
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const idx = (y * width + x) * 4;
                
                const flowX = Math.floor(x / flowField.step);
                const flowY = Math.floor(y / flowField.step);
                const flowIdx = flowY * flowField.width + flowX;
                
                const u = flowField.u[flowIdx] || 0;
                const v = flowField.v[flowIdx] || 0;
                
                const prevX = Math.round(x + u);
                const prevY = Math.round(y + v);
                
                if (prevX >= 0 && prevX < width && prevY >= 0 && prevY < height) {
                    const prevIdx = (prevY * width + prevX) * 4;
                    
                    const blend = temporalStrength * 0.4;
                    outData[idx] = this.lerp(currData[idx], prevData[prevIdx], blend);
                    outData[idx + 1] = this.lerp(currData[idx + 1], prevData[prevIdx + 1], blend);
                    outData[idx + 2] = this.lerp(currData[idx + 2], prevData[prevIdx + 2], blend);
                    outData[idx + 3] = 255;
                } else {
                    outData[idx] = currData[idx];
                    outData[idx + 1] = currData[idx + 1];
                    outData[idx + 2] = currData[idx + 2];
                    outData[idx + 3] = 255;
                }
            }
        }
        
        return result;
    }
    
    async exportVideo() {
        if (this.processedVideoFrames.length === 0) {
            alert('请先处理视频风格迁移');
            return;
        }
        
        this.showLoading('正在生成视频...');
        
        try {
            const width = this.processedVideoFrames[0].width;
            const height = this.processedVideoFrames[0].height;
            
            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext('2d');
            
            const fps = 10;
            const stream = canvas.captureStream(fps);
            const mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'video/webm;codecs=vp9',
                videoBitsPerSecond: 5000000
            });
            
            const chunks = [];
            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) chunks.push(e.data);
            };
            
            mediaRecorder.start();
            
            for (let i = 0; i < this.processedVideoFrames.length; i++) {
                const frame = this.processedVideoFrames[i];
                ctx.putImageData(frame, 0, 0);
                
                this.loadingText.textContent = `写入帧 ${i + 1}/${this.processedVideoFrames.length}...`;
                await this.sleep(1000 / fps);
            }
            
            mediaRecorder.stop();
            
            await new Promise((resolve) => {
                mediaRecorder.onstop = resolve;
            });
            
            const blob = new Blob(chunks, { type: 'video/webm' });
            const url = URL.createObjectURL(blob);
            
            const link = document.createElement('a');
            link.href = url;
            link.download = `oil_painting_video_${Date.now()}.webm`;
            link.click();
            
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            
        } catch (error) {
            console.error('视频导出错误:', error);
            alert('视频导出失败: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }
    
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new OilPaintingApp();
});
