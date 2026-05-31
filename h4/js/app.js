import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

let scene, camera, renderer, controls;
let solver = null;
let useWASM = false;

const wires = [];
const fieldLines = [];
let currentWirePoints = [];
let isDrawing = false;
let drawingPlane = null;
let raycaster = new THREE.Raycaster();
let mouse = new THREE.Vector2();

let heatmapMesh = null;
let heatmapCanvas = null;
let heatmapContext = null;
let efieldMesh = null;
let efieldArrows = [];

const config = {
    current: 1.0,
    lineDensity: 8,
    tolerance: 1e-4,
    heatmapResolution: 64,
    showHeatmap: true,
    slicePlane: 'xy',
    drawMode: true,
    maxRefinement: 3,
    errorTolerance: 1e-3,
    timeVarying: false,
    currentFrequency: 1.0,
    showEField: false,
    animateTime: false,
    vtkResolution: 20
};

let simulationTime = 0;
let lastTimeStamp = 0;
let eFieldMaterial = null;
let refinementColorMaterials = [];

let wireMaterialPositive, wireMaterialNegative;
let fieldLineMaterial;

function estimateErrors() {
    if (!solver || wires.length === 0) {
        alert('请先绘制至少一条导线');
        return;
    }
    
    if (useWASM) {
        solver.setRefinementParameters(config.maxRefinement, config.errorTolerance);
    } else {
        solver.setRefinementParameters(config.maxRefinement, config.errorTolerance);
    }
    
    const errors = solver.estimateAllErrors();
    const errorArray = useWASM ? 
        Array.from({ length: errors.size() }, (_, i) => errors.get(i)) :
        errors;
    
    const avgError = errorArray.reduce((a, b) => a + b, 0) / errorArray.length;
    const maxError = Math.max(...errorArray);
    
    const totalSegs = useWASM ? solver.getTotalSegments() : solver.getTotalSegments();
    document.getElementById('mesh-info').textContent = 
        `分段数: ${totalSegs}, 平均误差: ${avgError.toExponential(2)}, 最大误差: ${maxError.toExponential(2)}`;
    
    const levels = useWASM ? solver.getRefinementLevels() : solver.getRefinementLevels();
    updateWireColorsWithRefinement(levels);
}

function refineMesh() {
    if (!solver || wires.length === 0) {
        alert('请先绘制至少一条导线');
        return;
    }
    
    if (useWASM) {
        solver.setRefinementParameters(config.maxRefinement, config.errorTolerance);
    } else {
        solver.setRefinementParameters(config.maxRefinement, config.errorTolerance);
    }
    
    const refinedCount = solver.adaptiveRefinement();
    const totalSegs = useWASM ? solver.getTotalSegments() : solver.getTotalSegments();
    
    const levels = useWASM ? solver.getRefinementLevels() : solver.getRefinementLevels();
    updateWireColorsWithRefinement(levels);
    
    document.getElementById('mesh-info').textContent = 
        `已加密 ${refinedCount} 段, 总分段数: ${totalSegs}`;
    
    if (fieldLines.length > 0) {
        generateFieldLines();
    }
    
    if (config.showHeatmap) {
        updateHeatmap();
    }
}

function updateWireColorsWithRefinement(levels) {
    for (const wire of wires) {
        scene.remove(wire.mesh);
        if (wire.segmentMeshes) {
            for (const seg of wire.segmentMeshes) {
                scene.remove(seg);
            }
        }
    }
    
    const levelsLength = useWASM ? levels.size() : levels.length;
    
    let segmentIndex = 0;
    for (const wire of wires) {
        const wireSegments = [];
        const points = wire.points;
        
        for (let i = 0; i < points.length - 1; i++) {
            const level = segmentIndex < levelsLength ? 
                (useWASM ? levels.get(segmentIndex) : levels[segmentIndex]) : 0;
            const colorIndex = Math.min(level, refinementColorMaterials.length - 1);
            
            const geometry = new THREE.BufferGeometry().setFromPoints([points[i], points[i + 1]]);
            const line = new THREE.Line(geometry, refinementColorMaterials[colorIndex]);
            line.renderOrder = 0;
            scene.add(line);
            wireSegments.push(line);
            
            segmentIndex++;
        }
        
        wire.segmentMeshes = wireSegments;
    }
}

function updateTimeDependence() {
    if (!solver) return;
    
    const wireCount = useWASM ? solver.getWireCount() : solver.getWireCount();
    for (let i = 0; i < wireCount; i++) {
        const phase = i * Math.PI * 0.5;
        if (config.timeVarying) {
            solver.setWireTimeDependence(i, config.currentFrequency, phase);
        } else {
            solver.setWireTimeDependence(i, 0, 0);
        }
    }
}

function updateTimeDependentField() {
    if (!solver || wires.length === 0) return;
    
    if (config.showHeatmap) {
        updateHeatmapTime(simulationTime);
    }
    
    if (config.showEField) {
        updateEFieldVisualization();
    }
    
    if (fieldLines.length > 0) {
        updateFieldLinesTime(simulationTime);
    }
}

function updateHeatmapTime(time) {
    if (!solver || wires.length === 0 || !config.showHeatmap) return;
    
    if (heatmapMesh) {
        scene.remove(heatmapMesh);
    }
    
    const size = 10;
    const resolution = config.heatmapResolution;
    
    let origin, normal;
    switch (config.slicePlane) {
        case 'xy':
            origin = useWASM ? new Module.Vec3(0, 0, 0) : new Vec3(0, 0, 0);
            normal = useWASM ? new Module.Vec3(0, 0, 1) : new Vec3(0, 0, 1);
            break;
        case 'xz':
            origin = useWASM ? new Module.Vec3(0, 0, 0) : new Vec3(0, 0, 0);
            normal = useWASM ? new Module.Vec3(0, 1, 0) : new Vec3(0, 1, 0);
            break;
        case 'yz':
            origin = useWASM ? new Module.Vec3(0, 0, 0) : new Vec3(0, 0, 0);
            normal = useWASM ? new Module.Vec3(1, 0, 0) : new Vec3(1, 0, 0);
            break;
    }
    
    const data = useWASM ?
        solver.computeHeatmapSliceTime(origin, normal, size, resolution, time) :
        solver.computeHeatmapSliceTime(origin, normal, size, resolution, time);
    
    let maxMag = 0;
    const dataArray = useWASM ?
        Array.from({ length: data.size() }, (_, i) => data.get(i)) :
        data;
    
    for (const val of dataArray) {
        if (val > maxMag) maxMag = val;
    }
    
    heatmapCanvas.width = resolution;
    heatmapCanvas.height = resolution;
    
    const imageData = heatmapContext.createImageData(resolution, resolution);
    
    for (let i = 0; i < resolution; i++) {
        for (let j = 0; j < resolution; j++) {
            const idx = i * resolution + j;
            const magnitude = dataArray[idx];
            const normalized = maxMag > 0 ? Math.min(magnitude / maxMag, 1) : 0;
            
            const color = getHeatmapColor(normalized);
            const pixelIdx = (j * resolution + i) * 4;
            
            imageData.data[pixelIdx] = color.r;
            imageData.data[pixelIdx + 1] = color.g;
            imageData.data[pixelIdx + 2] = color.b;
            imageData.data[pixelIdx + 3] = 180;
        }
    }
    
    heatmapContext.putImageData(imageData, 0, 0);
    
    const texture = new THREE.CanvasTexture(heatmapCanvas);
    texture.needsUpdate = true;
    
    const geometry = new THREE.PlaneGeometry(size, size);
    const material = new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true,
        opacity: 0.7,
        side: THREE.DoubleSide,
        depthWrite: false,
        depthTest: true
    });
    
    heatmapMesh = new THREE.Mesh(geometry, material);
    heatmapMesh.visible = config.showHeatmap;
    heatmapMesh.renderOrder = 2;
    
    switch (config.slicePlane) {
        case 'xy':
            heatmapMesh.rotation.x = 0;
            break;
        case 'xz':
            heatmapMesh.rotation.x = -Math.PI / 2;
            break;
        case 'yz':
            heatmapMesh.rotation.y = Math.PI / 2;
            break;
    }
    
    scene.add(heatmapMesh);
}

function updateFieldLinesTime(time) {
    if (!solver || wires.length === 0) return;
    
    clearFieldLines();
    
    const seedPoints = generateSeedPoints();
    const maxStepSize = 0.1;
    const maxSteps = 500;
    
    for (const seed of seedPoints) {
        try {
            const start = useWASM ?
                new Module.Vec3(seed.x, seed.y, seed.z) :
                new Vec3(seed.x, seed.y, seed.z);
            
            let allPoints;
            if (useWASM) {
                const backward = solver.traceFieldLineTime(start, maxStepSize, config.tolerance, maxSteps, false, time);
                const forward = solver.traceFieldLineTime(start, maxStepSize, config.tolerance, maxSteps, true, time);
                
                allPoints = [];
                for (let i = backward.size() - 1; i >= 0; i--) {
                    const p = backward.get(i);
                    allPoints.push(new THREE.Vector3(p.x, p.y, p.z));
                }
                for (let i = 0; i < forward.size(); i++) {
                    const p = forward.get(i);
                    allPoints.push(new THREE.Vector3(p.x, p.y, p.z));
                }
            } else {
                const [backward, forward] = [
                    solver.traceFieldLineTime(start, maxStepSize, config.tolerance, maxSteps, false, time),
                    solver.traceFieldLineTime(start, maxStepSize, config.tolerance, maxSteps, true, time)
                ];
                
                allPoints = [...backward.reverse(), ...forward].map(
                    p => new THREE.Vector3(p.x, p.y, p.z)
                );
            }
            
            if (allPoints.length >= 2) {
                const geometry = new THREE.BufferGeometry().setFromPoints(allPoints);
                const line = new THREE.Line(geometry, fieldLineMaterial);
                line.renderOrder = 1;
                scene.add(line);
                fieldLines.push(line);
            }
        } catch (e) {
            console.error('Error tracing field line:', e);
        }
    }
}

function updateEFieldVisualization() {
    if (!solver || wires.length === 0) {
        clearEFieldVisualization();
        return;
    }
    
    clearEFieldVisualization();
    
    const size = 8;
    const gridSize = 5;
    const arrowScale = 0.5;
    
    for (let i = -gridSize; i <= gridSize; i++) {
        for (let j = -gridSize; j <= gridSize; j++) {
            for (let k = -1; k <= 1; k++) {
                let point;
                if (config.slicePlane === 'xy') {
                    point = new THREE.Vector3(
                        (i / gridSize) * size,
                        (j / gridSize) * size,
                        k * 0.5
                    );
                } else if (config.slicePlane === 'xz') {
                    point = new THREE.Vector3(
                        (i / gridSize) * size,
                        k * 0.5,
                        (j / gridSize) * size
                    );
                } else {
                    point = new THREE.Vector3(
                        k * 0.5,
                        (i / gridSize) * size,
                        (j / gridSize) * size
                    );
                }
                
                const p = useWASM ?
                    new Module.Vec3(point.x, point.y, point.z) :
                    new Vec3(point.x, point.y, point.z);
                
                const E = solver.computeVortexElectricField(p, simulationTime);
                
                const eVec = useWASM ?
                    new THREE.Vector3(E.x, E.y, E.z) :
                    new THREE.Vector3(E.x, E.y, E.z);
                
                if (eVec.length() > 1e-15) {
                    const normalizedE = eVec.clone().normalize();
                    const length = Math.min(eVec.length() * 1e5, 2.0) * arrowScale;
                    
                    const arrow = new THREE.ArrowHelper(
                        normalizedE,
                        point,
                        length,
                        0xffaa00,
                        length * 0.3,
                        length * 0.2
                    );
                    arrow.renderOrder = 1;
                    scene.add(arrow);
                    efieldArrows.push(arrow);
                }
            }
        }
    }
}

function clearEFieldVisualization() {
    for (const arrow of efieldArrows) {
        scene.remove(arrow);
    }
    efieldArrows = [];
}

function exportVTK() {
    if (!solver || wires.length === 0) {
        alert('请先绘制至少一条导线');
        return;
    }
    
    const res = config.vtkResolution;
    const min = useWASM ?
        new Module.Vec3(-5, -5, -5) :
        new Vec3(-5, -5, -5);
    const max = useWASM ?
        new Module.Vec3(5, 5, 5) :
        new Vec3(5, 5, 5);
    
    const vtkData = solver.exportVTK(min, max, res, res, res, simulationTime);
    
    const blob = new Blob([vtkData], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `magnetic_field_${res}x${res}x${res}_t${simulationTime.toFixed(2)}s.vtk`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    document.getElementById('mesh-info').textContent = 
        `已导出VTK: ${res}x${res}x${res}, 时间=${simulationTime.toFixed(2)}s`;
}

function init() {
    const container = document.getElementById('canvas-container');
    const width = container.clientWidth;
    const height = container.clientHeight;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a1a);

    camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    camera.position.set(5, 5, 8);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.sortObjects = true;
    container.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 10, 7);
    scene.add(directionalLight);

    const gridHelper = new THREE.GridHelper(20, 20, 0x1a1a3a, 0x0f0f2f);
    scene.add(gridHelper);

    const axesHelper = new THREE.AxesHelper(5);
    scene.add(axesHelper);

    drawingPlane = new THREE.Mesh(
        new THREE.PlaneGeometry(20, 20),
        new THREE.MeshBasicMaterial({ visible: false })
    );
    scene.add(drawingPlane);

    wireMaterialPositive = new THREE.LineBasicMaterial({ color: 0xff4444, linewidth: 3 });
    wireMaterialNegative = new THREE.LineBasicMaterial({ color: 0x4444ff, linewidth: 3 });
    fieldLineMaterial = new THREE.LineBasicMaterial({ color: 0x00ff88, linewidth: 1, transparent: true, opacity: 0.8, depthWrite: false });
    eFieldMaterial = new THREE.LineBasicMaterial({ color: 0xffaa00, linewidth: 2, transparent: true, opacity: 0.8, depthWrite: false });
    
    refinementColorMaterials = [
        new THREE.LineBasicMaterial({ color: 0x4444ff, linewidth: 2 }),
        new THREE.LineBasicMaterial({ color: 0x44ff44, linewidth: 2 }),
        new THREE.LineBasicMaterial({ color: 0xffff44, linewidth: 2 }),
        new THREE.LineBasicMaterial({ color: 0xff8844, linewidth: 2 }),
        new THREE.LineBasicMaterial({ color: 0xff4444, linewidth: 2 }),
        new THREE.LineBasicMaterial({ color: 0xff44ff, linewidth: 2 })
    ];

    heatmapCanvas = document.createElement('canvas');
    heatmapContext = heatmapCanvas.getContext('2d');

    setupEventListeners();
    initSolver();

    animate();
}

async function initSolver() {
    const wasmStatus = document.getElementById('wasm-status');

    try {
        if (typeof Module !== 'undefined' && Module.MagneticFieldSolver) {
            solver = new Module.MagneticFieldSolver();
            useWASM = true;
            wasmStatus.textContent = 'WASM已加载 (C++加速)';
            wasmStatus.className = 'loaded';
        } else {
            throw new Error('WASM module not available');
        }
    } catch (e) {
        console.log('WASM not available, using JS fallback:', e);
        solver = new MagneticFieldSolverJS();
        useWASM = false;
        wasmStatus.textContent = '使用JavaScript实现 (WASM未加载)';
        wasmStatus.className = 'error';
    }
}

function setupEventListeners() {
    const container = document.getElementById('canvas-container');

    container.addEventListener('mousedown', onMouseDown);
    container.addEventListener('mousemove', onMouseMove);
    container.addEventListener('mouseup', onMouseUp);
    container.addEventListener('mouseleave', onMouseUp);

    window.addEventListener('resize', onWindowResize);

    document.getElementById('draw-mode').addEventListener('change', (e) => {
        config.drawMode = e.target.checked;
        controls.enabled = !config.drawMode;
    });

    document.getElementById('current-slider').addEventListener('input', (e) => {
        config.current = parseFloat(e.target.value);
        document.getElementById('current-value').textContent = config.current.toFixed(1) + ' A';
        updateColorIndicator();
    });

    document.getElementById('line-density').addEventListener('input', (e) => {
        config.lineDensity = parseInt(e.target.value);
        document.getElementById('density-value').textContent = config.lineDensity;
    });

    document.getElementById('tolerance').addEventListener('input', (e) => {
        config.tolerance = Math.pow(10, parseFloat(e.target.value));
        document.getElementById('tolerance-value').textContent = '1e' + e.target.value;
    });

    document.getElementById('show-heatmap').addEventListener('change', (e) => {
        config.showHeatmap = e.target.checked;
        if (heatmapMesh) {
            heatmapMesh.visible = config.showHeatmap;
        }
        if (config.showHeatmap && wires.length > 0) {
            updateHeatmap();
        }
    });

    document.getElementById('heatmap-resolution').addEventListener('input', (e) => {
        config.heatmapResolution = parseInt(e.target.value);
        document.getElementById('resolution-value').textContent = config.heatmapResolution;
        if (wires.length > 0) {
            updateHeatmap();
        }
    });

    document.getElementById('slice-plane').addEventListener('change', (e) => {
        config.slicePlane = e.target.value;
        if (wires.length > 0) {
            updateHeatmap();
        }
    });

    document.getElementById('clear-wires').addEventListener('click', clearAllWires);
    document.getElementById('clear-field-lines').addEventListener('click', clearFieldLines);
    document.getElementById('generate-lines').addEventListener('click', generateFieldLines);
    
    document.getElementById('max-refinement').addEventListener('input', (e) => {
        config.maxRefinement = parseInt(e.target.value);
        document.getElementById('refinement-value').textContent = config.maxRefinement;
        if (solver && wires.length > 0) {
            if (useWASM) {
                solver.setRefinementParameters(config.maxRefinement, config.errorTolerance);
            } else {
                solver.setRefinementParameters(config.maxRefinement, config.errorTolerance);
            }
        }
    });
    
    document.getElementById('error-tolerance').addEventListener('input', (e) => {
        config.errorTolerance = Math.pow(10, parseFloat(e.target.value));
        document.getElementById('error-value').textContent = '1e' + e.target.value;
        if (solver && wires.length > 0) {
            if (useWASM) {
                solver.setRefinementParameters(config.maxRefinement, config.errorTolerance);
            } else {
                solver.setRefinementParameters(config.maxRefinement, config.errorTolerance);
            }
        }
    });
    
    document.getElementById('estimate-errors').addEventListener('click', estimateErrors);
    document.getElementById('refine-mesh').addEventListener('click', refineMesh);
    
    document.getElementById('time-varying').addEventListener('change', (e) => {
        config.timeVarying = e.target.checked;
        if (solver && wires.length > 0) {
            updateTimeDependence();
        }
    });
    
    document.getElementById('current-frequency').addEventListener('input', (e) => {
        config.currentFrequency = parseFloat(e.target.value);
        document.getElementById('freq-value').textContent = config.currentFrequency.toFixed(1) + ' Hz';
        if (solver && wires.length > 0 && config.timeVarying) {
            updateTimeDependence();
        }
    });
    
    document.getElementById('show-efield').addEventListener('change', (e) => {
        config.showEField = e.target.checked;
        if (config.showEField) {
            updateEFieldVisualization();
        } else {
            clearEFieldVisualization();
        }
    });
    
    document.getElementById('animate-time').addEventListener('change', (e) => {
        config.animateTime = e.target.checked;
        if (!config.animateTime) {
            simulationTime = 0;
            document.getElementById('time-value').textContent = '时间: 0.00s';
        }
    });
    
    document.getElementById('vtk-resolution').addEventListener('input', (e) => {
        config.vtkResolution = parseInt(e.target.value);
        document.getElementById('vtk-res-value').textContent = config.vtkResolution;
    });
    
    document.getElementById('export-vtk').addEventListener('click', exportVTK);

    updateColorIndicator();
}

function updateColorIndicator() {
    const indicator = document.getElementById('color-indicator');
    const directionText = document.getElementById('current-direction');

    if (config.current >= 0) {
        indicator.style.background = '#ff4444';
        indicator.style.boxShadow = '0 0 10px rgba(255, 68, 68, 0.5)';
        directionText.textContent = '电流方向: 正向';
    } else {
        indicator.style.background = '#4444ff';
        indicator.style.boxShadow = '0 0 10px rgba(68, 68, 255, 0.5)';
        directionText.textContent = '电流方向: 反向';
    }
}

function getIntersectionPoint(event) {
    const container = document.getElementById('canvas-container');
    const rect = container.getBoundingClientRect();

    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    const intersects = raycaster.intersectObject(drawingPlane);
    if (intersects.length > 0) {
        return intersects[0].point;
    }
    return null;
}

function onMouseDown(event) {
    if (!config.drawMode || event.button !== 0) return;

    const point = getIntersectionPoint(event);
    if (point) {
        isDrawing = true;
        currentWirePoints = [point.clone()];
    }
}

function onMouseMove(event) {
    if (!isDrawing || !config.drawMode) return;

    const point = getIntersectionPoint(event);
    if (point) {
        const lastPoint = currentWirePoints[currentWirePoints.length - 1];
        if (lastPoint.distanceTo(point) > 0.1) {
            currentWirePoints.push(point.clone());
            updateCurrentWirePreview();
        }
    }

    if (solver && wires.length > 0) {
        const worldPoint = getIntersectionPoint(event);
        if (worldPoint) {
            const p = useWASM ?
                new Module.Vec3(worldPoint.x, worldPoint.y, worldPoint.z) :
                new Vec3(worldPoint.x, worldPoint.y, worldPoint.z);

            const magnitude = solver.getFieldMagnitude(p);
            document.getElementById('field-info').textContent =
                '磁场强度: ' + magnitude.toExponential(2) + ' T';
        }
    }
}

function onMouseUp(event) {
    if (!isDrawing || !config.drawMode) return;
    isDrawing = false;

    if (currentWirePoints.length >= 2) {
        createWireFromPoints(currentWirePoints, config.current);
    }

    currentWirePoints = [];
    updateCurrentWirePreview();
}

function updateCurrentWirePreview() {
    const existingPreview = scene.getObjectByName('currentWirePreview');
    if (existingPreview) {
        scene.remove(existingPreview);
    }

    if (currentWirePoints.length < 2) return;

    const geometry = new THREE.BufferGeometry().setFromPoints(currentWirePoints);
    const material = config.current >= 0 ? wireMaterialPositive : wireMaterialNegative;
    const line = new THREE.Line(geometry, material);
    line.name = 'currentWirePreview';
    line.renderOrder = 0;
    scene.add(line);
}

function createWireFromPoints(points, current) {
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = current >= 0 ? wireMaterialPositive : wireMaterialNegative;
    const line = new THREE.Line(geometry, material);
    line.renderOrder = 0;
    scene.add(line);

    const wireData = {
        points: points,
        current: current,
        mesh: line
    };
    wires.push(wireData);

    if (solver) {
        for (let i = 0; i < points.length - 1; i++) {
            const start = points[i];
            const end = points[i + 1];

            if (useWASM) {
                solver.addWireSegment(
                    new Module.Vec3(start.x, start.y, start.z),
                    new Module.Vec3(end.x, end.y, end.z),
                    current
                );
            } else {
                solver.addWireSegment(
                    new Vec3(start.x, start.y, start.z),
                    new Vec3(end.x, end.y, end.z),
                    current
                );
            }
        }
    }

    if (config.showHeatmap) {
        updateHeatmap();
    }
    
    const totalSegs = useWASM ? solver.getTotalSegments() : solver.getTotalSegments();
    document.getElementById('mesh-info').textContent = `分段数: ${totalSegs}`;
}

function clearAllWires() {
    for (const wire of wires) {
        scene.remove(wire.mesh);
        if (wire.segmentMeshes) {
            for (const seg of wire.segmentMeshes) {
                scene.remove(seg);
            }
        }
    }
    wires.length = 0;

    if (solver) {
        solver.clearWires();
    }

    clearFieldLines();
    clearEFieldVisualization();

    if (heatmapMesh) {
        scene.remove(heatmapMesh);
        heatmapMesh = null;
    }
    
    if (efieldMesh) {
        scene.remove(efieldMesh);
        efieldMesh = null;
    }

    document.getElementById('field-info').textContent = '磁场强度: --';
    document.getElementById('mesh-info').textContent = '分段数: --';
}

function clearFieldLines() {
    for (const line of fieldLines) {
        scene.remove(line);
    }
    fieldLines.length = 0;
}

function generateFieldLines() {
    if (!solver || wires.length === 0) {
        alert('请先绘制至少一条导线');
        return;
    }

    clearFieldLines();

    const seedPoints = generateSeedPoints();
    const maxStepSize = 0.1;
    const maxSteps = 500;

    for (const seed of seedPoints) {
        try {
            const start = useWASM ?
                new Module.Vec3(seed.x, seed.y, seed.z) :
                new Vec3(seed.x, seed.y, seed.z);

            const result = solver.traceFieldLines(start, maxStepSize, config.tolerance, maxSteps);

            if (useWASM) {
                const backward = result.get(0);
                const forward = result.get(1);

                const allPoints = [];
                for (let i = 0; i < backward.size(); i++) {
                    const p = backward.get(i);
                    allPoints.push(new THREE.Vector3(p.x, p.y, p.z));
                }
                for (let i = 0; i < forward.size(); i++) {
                    const p = forward.get(i);
                    allPoints.push(new THREE.Vector3(p.x, p.y, p.z));
                }

                if (allPoints.length >= 2) {
                    const geometry = new THREE.BufferGeometry().setFromPoints(allPoints);
                    const line = new THREE.Line(geometry, fieldLineMaterial);
                    line.renderOrder = 1;
                    scene.add(line);
                    fieldLines.push(line);
                }
            } else {
                const [backward, forward] = result;
                const allPoints = [...backward, ...forward];

                const threePoints = allPoints.map(p => new THREE.Vector3(p.x, p.y, p.z));

                if (threePoints.length >= 2) {
                    const geometry = new THREE.BufferGeometry().setFromPoints(threePoints);
                    const line = new THREE.Line(geometry, fieldLineMaterial);
                    line.renderOrder = 1;
                    scene.add(line);
                    fieldLines.push(line);
                }
            }
        } catch (e) {
            console.error('Error tracing field line:', e);
        }
    }

    if (config.showHeatmap) {
        updateHeatmap();
    }
}

function generateSeedPoints() {
    const seeds = [];

    for (const wire of wires) {
        const points = wire.points;
        const numSeeds = Math.min(config.lineDensity, points.length - 1);

        for (let i = 0; i < numSeeds; i++) {
            const idx = Math.floor((i + 0.5) * (points.length - 1) / numSeeds);
            const p = points[idx];

            const tangent = new THREE.Vector3();
            if (idx > 0) {
                tangent.subVectors(points[idx + 1] || points[idx], points[idx - 1] || points[idx]).normalize();
            } else if (points.length > 1) {
                tangent.subVectors(points[1], points[0]).normalize();
            } else {
                tangent.set(1, 0, 0);
            }

            const normal1 = new THREE.Vector3();
            if (Math.abs(tangent.y) < 0.9) {
                normal1.set(0, 1, 0);
            } else {
                normal1.set(1, 0, 0);
            }
            normal1.cross(tangent).normalize();

            const normal2 = new THREE.Vector3().crossVectors(tangent, normal1).normalize();

            const offset = 0.3;
            seeds.push(p.clone().add(normal1.multiplyScalar(offset)));
            seeds.push(p.clone().add(normal2.multiplyScalar(offset)));
            seeds.push(p.clone().add(normal1.multiplyScalar(-offset)));
            seeds.push(p.clone().add(normal2.multiplyScalar(-offset)));
        }
    }

    return seeds;
}

function updateHeatmap() {
    if (!solver || wires.length === 0) return;

    if (heatmapMesh) {
        scene.remove(heatmapMesh);
    }

    const size = 10;
    const resolution = config.heatmapResolution;

    let origin, normal;
    switch (config.slicePlane) {
        case 'xy':
            origin = useWASM ? new Module.Vec3(0, 0, 0) : new Vec3(0, 0, 0);
            normal = useWASM ? new Module.Vec3(0, 0, 1) : new Vec3(0, 0, 1);
            break;
        case 'xz':
            origin = useWASM ? new Module.Vec3(0, 0, 0) : new Vec3(0, 0, 0);
            normal = useWASM ? new Module.Vec3(0, 1, 0) : new Vec3(0, 1, 0);
            break;
        case 'yz':
            origin = useWASM ? new Module.Vec3(0, 0, 0) : new Vec3(0, 0, 0);
            normal = useWASM ? new Module.Vec3(1, 0, 0) : new Vec3(1, 0, 0);
            break;
    }

    const data = solver.computeHeatmapSlice(origin, normal, size, resolution);

    let maxMag = 0;
    const dataArray = useWASM ?
        Array.from({ length: data.size() }, (_, i) => data.get(i)) :
        data;

    for (const val of dataArray) {
        if (val > maxMag) maxMag = val;
    }

    heatmapCanvas.width = resolution;
    heatmapCanvas.height = resolution;

    const imageData = heatmapContext.createImageData(resolution, resolution);

    for (let i = 0; i < resolution; i++) {
        for (let j = 0; j < resolution; j++) {
            const idx = i * resolution + j;
            const magnitude = dataArray[idx];
            const normalized = maxMag > 0 ? Math.min(magnitude / maxMag, 1) : 0;

            const color = getHeatmapColor(normalized);
            const pixelIdx = (j * resolution + i) * 4;

            imageData.data[pixelIdx] = color.r;
            imageData.data[pixelIdx + 1] = color.g;
            imageData.data[pixelIdx + 2] = color.b;
            imageData.data[pixelIdx + 3] = 180;
        }
    }

    heatmapContext.putImageData(imageData, 0, 0);

    const texture = new THREE.CanvasTexture(heatmapCanvas);
    texture.needsUpdate = true;

    const geometry = new THREE.PlaneGeometry(size, size);
    const material = new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true,
        opacity: 0.7,
        side: THREE.DoubleSide,
        depthWrite: false,
        depthTest: true
    });

    heatmapMesh = new THREE.Mesh(geometry, material);
    heatmapMesh.visible = config.showHeatmap;
    heatmapMesh.renderOrder = 2;

    switch (config.slicePlane) {
        case 'xy':
            heatmapMesh.rotation.x = 0;
            break;
        case 'xz':
            heatmapMesh.rotation.x = -Math.PI / 2;
            break;
        case 'yz':
            heatmapMesh.rotation.y = Math.PI / 2;
            break;
    }

    scene.add(heatmapMesh);
}

function getHeatmapColor(t) {
    const colors = [
        { t: 0.0, r: 0, g: 0, b: 255 },
        { t: 0.2, r: 0, g: 100, b: 255 },
        { t: 0.4, r: 0, g: 200, b: 200 },
        { t: 0.6, r: 100, g: 255, b: 100 },
        { t: 0.8, r: 255, g: 200, b: 0 },
        { t: 1.0, r: 255, g: 0, b: 0 }
    ];

    for (let i = 0; i < colors.length - 1; i++) {
        if (t <= colors[i + 1].t) {
            const f = (t - colors[i].t) / (colors[i + 1].t - colors[i].t);
            return {
                r: Math.round(colors[i].r + f * (colors[i + 1].r - colors[i].r)),
                g: Math.round(colors[i].g + f * (colors[i + 1].g - colors[i].g)),
                b: Math.round(colors[i].b + f * (colors[i + 1].b - colors[i].b))
            };
        }
    }

    return { r: 255, g: 0, b: 0 };
}

function onWindowResize() {
    const container = document.getElementById('canvas-container');
    const width = container.clientWidth;
    const height = container.clientHeight;

    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
}

function animate(currentTime) {
    requestAnimationFrame(animate);
    
    if (config.animateTime && currentTime !== undefined) {
        const deltaTime = lastTimeStamp === 0 ? 0 : (currentTime - lastTimeStamp) / 1000;
        lastTimeStamp = currentTime;
        
        simulationTime += deltaTime;
        document.getElementById('time-value').textContent = '时间: ' + simulationTime.toFixed(2) + 's';
        
        if (wires.length > 0) {
            updateTimeDependentField();
        }
    } else {
        lastTimeStamp = currentTime || 0;
    }
    
    controls.update();
    renderer.render(scene, camera);
}

init();
