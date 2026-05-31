import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

class BlochSphere {
    constructor() {
        this.container = document.getElementById('scene-container');
        this.worker = null;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.sphere = null;
        this.stateVector = null;
        this.trail = null;
        this.trailPoints = [];
        this.currentState = null;
        this.animationQueue = [];
        this.isAnimating = false;
        this.frameCount = 0;
        this.lastFpsUpdate = performance.now();
        this.showLabels = true;
        this.showTrail = true;
        this.showPhase = true;
        this.labels = [];

        this.init();
    }

    init() {
        this.initWorker();
        this.initScene();
        this.initSphere();
        this.initStateVector();
        this.initTrail();
        this.initControls();
        this.initEventListeners();
        this.animate();
    }

    initWorker() {
        this.worker = new Worker('quantum.worker.js');
        this.worker.addEventListener('message', (e) => {
            this.handleWorkerMessage(e.data);
        });
    }

    handleWorkerMessage(data) {
        const { type, data: payload } = data;

        switch (type) {
            case 'ready':
                this.worker.postMessage({ type: 'getState' });
                break;
            case 'stateUpdate':
                const cleanedPayload = this.validateData(payload);
                this.updateState(cleanedPayload);
                break;
            case 'animationData':
                const trajectory = this.parseTrajectoryData(payload);
                this.playAnimation(trajectory);
                break;
        }
    }

    validateData(data) {
        const EPSILON = 1e-10;
        const clean = (v) => {
            if (v === null || v === undefined || isNaN(v) || !isFinite(v)) return 0;
            return Math.abs(v) < EPSILON ? 0 : v;
        };

        if (!data) return { cartesian: { x: 0, y: 0, z: 1 }, state: { alpha: { re: 1, im: 0 }, beta: { re: 0, im: 0 } }, bloch: { theta: 0, phi: 0 } };

        return {
            cartesian: {
                x: clean(data.cartesian?.x),
                y: clean(data.cartesian?.y),
                z: clean(data.cartesian?.z)
            },
            state: {
                alpha: {
                    re: clean(data.state?.alpha?.re),
                    im: clean(data.state?.alpha?.im)
                },
                beta: {
                    re: clean(data.state?.beta?.re),
                    im: clean(data.state?.beta?.im)
                }
            },
            bloch: {
                theta: clean(data.bloch?.theta),
                phi: clean(data.bloch?.phi)
            }
        };
    }

    parseTrajectoryData(payload) {
        const { trajectory: buffer, steps } = payload;
        const trajectory = [];
        const floatsPerFrame = 9;

        if (buffer instanceof ArrayBuffer) {
            const floatData = new Float64Array(buffer);
            const EPSILON = 1e-10;

            for (let i = 0; i < steps; i++) {
                const idx = i * floatsPerFrame;
                
                if (idx + 8 >= floatData.length) break;

                const alphaRe = isNaN(floatData[idx]) ? 0 : floatData[idx];
                const alphaIm = isNaN(floatData[idx + 1]) ? 0 : floatData[idx + 1];
                const betaRe = isNaN(floatData[idx + 2]) ? 0 : floatData[idx + 2];
                const betaIm = isNaN(floatData[idx + 3]) ? 0 : floatData[idx + 3];
                let theta = isNaN(floatData[idx + 4]) ? 0 : floatData[idx + 4];
                let phi = isNaN(floatData[idx + 5]) ? 0 : floatData[idx + 5];
                let x = isNaN(floatData[idx + 6]) ? 0 : floatData[idx + 6];
                let y = isNaN(floatData[idx + 7]) ? 0 : floatData[idx + 7];
                let z = isNaN(floatData[idx + 8]) ? 0 : floatData[idx + 8];

                const len = Math.sqrt(x * x + y * y + z * z);
                if (len > EPSILON) {
                    x /= len;
                    y /= len;
                    z /= len;
                } else {
                    x = 0;
                    y = 0;
                    z = 1;
                }

                theta = Math.max(0, Math.min(180, theta));

                trajectory.push({
                    state: {
                        alpha: { re: alphaRe, im: alphaIm },
                        beta: { re: betaRe, im: betaIm }
                    },
                    bloch: { theta, phi },
                    cartesian: { x, y, z }
                });
            }
        }

        if (trajectory.length === 0) {
            trajectory.push({
                state: { alpha: { re: 1, im: 0 }, beta: { re: 0, im: 0 } },
                bloch: { theta: 0, phi: 0 },
                cartesian: { x: 0, y: 0, z: 1 }
            });
        }

        return trajectory;
    }

    initScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0a0f);

        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        this.camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
        this.camera.position.set(3, 2, 3);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.container.appendChild(this.renderer.domElement);

        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);

        const pointLight1 = new THREE.PointLight(0x4fc3f7, 1);
        pointLight1.position.set(5, 5, 5);
        this.scene.add(pointLight1);

        const pointLight2 = new THREE.PointLight(0xb388ff, 0.5);
        pointLight2.position.set(-5, -5, 5);
        this.scene.add(pointLight2);

        this.initAxes();
        this.initLabels();

        window.addEventListener('resize', () => this.onWindowResize());
    }

    initAxes() {
        const axisLength = 1.8;
        const axisMaterial = new THREE.LineBasicMaterial({ linewidth: 2 });

        const xAxisGeom = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(axisLength, 0, 0)
        ]);
        const xAxis = new THREE.Line(xAxisGeom, axisMaterial.clone());
        xAxis.material.color.setHex(0xff5252);
        this.scene.add(xAxis);

        const yAxisGeom = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(0, axisLength, 0)
        ]);
        const yAxis = new THREE.Line(yAxisGeom, axisMaterial.clone());
        yAxis.material.color.setHex(0x69f0ae);
        this.scene.add(yAxis);

        const zAxisGeom = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(0, 0, axisLength)
        ]);
        const zAxis = new THREE.Line(zAxisGeom, axisMaterial.clone());
        zAxis.material.color.setHex(0x4fc3f7);
        this.scene.add(zAxis);

        const arrowSize = 0.08;
        this.createArrow(new THREE.Vector3(axisLength, 0, 0), new THREE.Vector3(1, 0, 0), 0xff5252, arrowSize);
        this.createArrow(new THREE.Vector3(0, axisLength, 0), new THREE.Vector3(0, 1, 0), 0x69f0ae, arrowSize);
        this.createArrow(new THREE.Vector3(0, 0, axisLength), new THREE.Vector3(0, 0, 1), 0x4fc3f7, arrowSize);

        this.createEquator();
    }

    createArrow(position, direction, color, size) {
        const arrowGeom = new THREE.ConeGeometry(size * 0.3, size, 8);
        const arrowMat = new THREE.MeshBasicMaterial({ color });
        const arrow = new THREE.Mesh(arrowGeom, arrowMat);
        arrow.position.copy(position);
        arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.clone().normalize());
        this.scene.add(arrow);
    }

    createEquator() {
        const equatorGeom = new THREE.RingGeometry(0.98, 1.02, 64);
        const equatorMat = new THREE.MeshBasicMaterial({
            color: 0x2a2a3e,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.5
        });
        const equator = new THREE.Mesh(equatorGeom, equatorMat);
        equator.rotation.x = Math.PI / 2;
        this.scene.add(equator);

        const meridianGeom = new THREE.RingGeometry(0.98, 1.02, 64);
        const meridianMat = equatorMat.clone();
        const meridian1 = new THREE.Mesh(meridianGeom, meridianMat);
        this.scene.add(meridian1);

        const meridian2 = new THREE.Mesh(meridianGeom, meridianMat.clone());
        meridian2.rotation.y = Math.PI / 2;
        this.scene.add(meridian2);
    }

    initLabels() {
        this.addLabel('|0⟩', new THREE.Vector3(0, 0, 1.2), 0x4fc3f7);
        this.addLabel('|1⟩', new THREE.Vector3(0, 0, -1.2), 0xff80ab);
        this.addLabel('|+⟩', new THREE.Vector3(1.3, 0, 0), 0x69f0ae);
        this.addLabel('|-⟩', new THREE.Vector3(-1.3, 0, 0), 0xffab40);
        this.addLabel('|+i⟩', new THREE.Vector3(0, 1.3, 0), 0xb388ff);
        this.addLabel('|-i⟩', new THREE.Vector3(0, -1.3, 0), 0x00bcd4);
        this.addLabel('x', new THREE.Vector3(2.0, 0, 0), 0xff5252);
        this.addLabel('y', new THREE.Vector3(0, 2.0, 0), 0x69f0ae);
        this.addLabel('z', new THREE.Vector3(0, 0, 2.0), 0x4fc3f7);
    }

    addLabel(text, position, color) {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = 128;
        canvas.height = 128;

        context.fillStyle = 'transparent';
        context.fillRect(0, 0, canvas.width, canvas.height);

        context.font = 'bold 48px Arial';
        context.fillStyle = '#' + color.toString(16).padStart(6, '0');
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText(text, canvas.width / 2, canvas.height / 2);

        const texture = new THREE.CanvasTexture(canvas);
        const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
        const sprite = new THREE.Sprite(material);
        sprite.position.copy(position);
        sprite.scale.set(0.4, 0.4, 0.4);
        this.scene.add(sprite);
        this.labels.push(sprite);
    }

    initSphere() {
        const sphereGeom = new THREE.SphereGeometry(1, 64, 64);
        const sphereMat = new THREE.MeshPhongMaterial({
            color: 0x1a1a2e,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide,
            shininess: 100
        });
        this.sphere = new THREE.Mesh(sphereGeom, sphereMat);
        this.scene.add(this.sphere);

        const wireframeGeom = new THREE.WireframeGeometry(new THREE.SphereGeometry(1.001, 16, 16));
        const wireframeMat = new THREE.LineBasicMaterial({
            color: 0x2a2a3e,
            transparent: true,
            opacity: 0.3
        });
        const wireframe = new THREE.LineSegments(wireframeGeom, wireframeMat);
        this.scene.add(wireframe);

        this.createPhaseShader();
    }

    createPhaseShader() {
        const shaderGeom = new THREE.SphereGeometry(1.002, 64, 64);
        const shaderMat = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                showPhase: { value: 1.0 }
            },
            vertexShader: `
                varying vec3 vNormal;
                varying vec3 vPosition;
                void main() {
                    vNormal = normalize(normalMatrix * normal);
                    vPosition = position;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform float time;
                uniform float showPhase;
                varying vec3 vNormal;
                varying vec3 vPosition;

                vec3 hsv2rgb(vec3 c) {
                    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
                    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
                    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
                }

                void main() {
                    float phi = atan(vPosition.y, vPosition.x);
                    float theta = acos(vPosition.z);

                    float phase = phi / (2.0 * 3.14159265359) + 0.5;
                    float amplitude = sin(theta);

                    vec3 phaseColor = hsv2rgb(vec3(phase, 0.8, 0.6));
                    vec3 baseColor = vec3(0.1, 0.1, 0.18);

                    vec3 finalColor = mix(baseColor, phaseColor, showPhase * amplitude * 0.6);

                    float rim = pow(1.0 - max(0.0, dot(vNormal, vec3(0.0, 0.0, 1.0))), 2.0);
                    finalColor += rim * 0.1;

                    gl_FragColor = vec4(finalColor, 0.4 * showPhase + 0.1);
                }
            `,
            transparent: true,
            side: THREE.BackSide,
            depthWrite: false
        });

        this.phaseShader = new THREE.Mesh(shaderGeom, shaderMat);
        this.scene.add(this.phaseShader);
    }

    initStateVector() {
        const arrowGeom = new THREE.CylinderGeometry(0.02, 0.02, 1, 8);
        const arrowMat = new THREE.MeshPhongMaterial({
            color: 0x4fc3f7,
            emissive: 0x4fc3f7,
            emissiveIntensity: 0.3,
            transparent: true,
            opacity: 0.9
        });
        this.arrowShaft = new THREE.Mesh(arrowGeom, arrowMat);

        const headGeom = new THREE.ConeGeometry(0.06, 0.15, 16);
        const headMat = arrowMat.clone();
        this.arrowHead = new THREE.Mesh(headGeom, headMat);

        this.stateVector = new THREE.Group();
        this.stateVector.add(this.arrowShaft);
        this.stateVector.add(this.arrowHead);
        this.scene.add(this.stateVector);

        const glowGeom = new THREE.SphereGeometry(0.08, 16, 16);
        const glowMat = new THREE.MeshBasicMaterial({
            color: 0x4fc3f7,
            transparent: true,
            opacity: 0.8
        });
        this.stateGlow = new THREE.Mesh(glowGeom, glowMat);
        this.scene.add(this.stateGlow);
    }

    initTrail() {
        const trailGeom = new THREE.BufferGeometry();
        const trailMat = new THREE.LineBasicMaterial({
            color: 0xb388ff,
            transparent: true,
            opacity: 0.8,
            linewidth: 2,
            vertexColors: true
        });
        this.trail = new THREE.Line(trailGeom, trailMat);
        this.scene.add(this.trail);
    }

    initControls() {
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.minDistance = 2;
        this.controls.maxDistance = 10;
        this.controls.enablePan = false;
    }

    initEventListeners() {
        document.getElementById('theta').addEventListener('input', (e) => {
            const theta = parseFloat(e.target.value);
            document.getElementById('theta-value').textContent = theta.toFixed(1) + '°';
            const phi = parseFloat(document.getElementById('phi').value);
            this.worker.postMessage({ type: 'setBloch', data: { theta, phi } });
        });

        document.getElementById('phi').addEventListener('input', (e) => {
            const phi = parseFloat(e.target.value);
            document.getElementById('phi-value').textContent = phi.toFixed(1) + '°';
            const theta = parseFloat(document.getElementById('theta').value);
            this.worker.postMessage({ type: 'setBloch', data: { theta, phi } });
        });

        document.querySelectorAll('.gate-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const gate = btn.dataset.gate;
                this.applyGate(gate);
                btn.classList.add('animating');
                setTimeout(() => btn.classList.remove('animating'), 500);
            });
        });

        document.getElementById('reset-btn').addEventListener('click', () => {
            this.resetState();
        });

        document.getElementById('animate-btn').addEventListener('click', () => {
            this.startGateSequence();
        });

        document.getElementById('show-labels').addEventListener('change', (e) => {
            this.showLabels = e.target.checked;
            this.labels.forEach(label => label.visible = this.showLabels);
        });

        document.getElementById('show-trail').addEventListener('change', (e) => {
            this.showTrail = e.target.checked;
            this.trail.visible = this.showTrail;
        });

        document.getElementById('show-phase').addEventListener('change', (e) => {
            this.showPhase = e.target.checked;
            this.phaseShader.material.uniforms.showPhase.value = this.showPhase ? 1.0 : 0.0;
        });
    }

    applyGate(gate) {
        if (this.isAnimating) return;
        this.worker.postMessage({ type: 'animate', data: { gate, steps: 60 } });
    }

    resetState() {
        this.trailPoints = [];
        this.updateTrail();
        this.worker.postMessage({ type: 'reset' });
        document.getElementById('theta').value = 0;
        document.getElementById('theta-value').textContent = '0°';
        document.getElementById('phi').value = 0;
        document.getElementById('phi-value').textContent = '0°';
    }

    startGateSequence() {
        if (this.isAnimating) return;
        const sequence = ['H', 'X', 'Y', 'Z', 'H'];
        let index = 0;

        const applyNext = () => {
            if (index >= sequence.length || this.isAnimating) {
                this.isAnimating = false;
                return;
            }
            const gate = sequence[index];
            document.querySelectorAll('.gate-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.gate === gate);
            });
            this.worker.postMessage({
                type: 'animate',
                data: { gate, steps: 60, sequence: true }
            });
            index++;
        };

        this._sequenceCallback = applyNext;
        applyNext();
    }

    playAnimation(trajectory) {
        this.isAnimating = true;
        this.animationQueue = trajectory;
        this.animationIndex = 0;
        this.animationStartTime = performance.now();
    }

    updateAnimation() {
        if (!this.isAnimating || this.animationQueue.length === 0) return;

        const now = performance.now();
        const elapsed = now - this.animationStartTime;
        const frameDuration = 1000 / 60;
        const targetIndex = Math.min(
            Math.floor(elapsed / frameDuration),
            this.animationQueue.length - 1
        );

        if (targetIndex > this.animationIndex) {
            this.animationIndex = targetIndex;
            const frame = this.animationQueue[this.animationIndex];
            this.updateState(frame);
        }

        if (this.animationIndex >= this.animationQueue.length - 1) {
            this.isAnimating = false;
            this.animationQueue = [];
            document.querySelectorAll('.gate-btn').forEach(btn => btn.classList.remove('active'));

            if (this._sequenceCallback) {
                const callback = this._sequenceCallback;
                this._sequenceCallback = null;
                setTimeout(callback, 300);
            }
        }
    }

    setArrowQuaternion(mesh, targetDir) {
        const EPSILON = 1e-6;
        const up = new THREE.Vector3(0, 1, 0);
        const dot = up.dot(targetDir);

        if (Math.abs(dot - (-1.0)) < EPSILON) {
            mesh.quaternion.setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI);
        } else if (Math.abs(dot - 1.0) < EPSILON) {
            mesh.quaternion.identity();
        } else {
            const angle = Math.acos(dot);
            const axis = new THREE.Vector3().crossVectors(up, targetDir).normalize();
            mesh.quaternion.setFromAxisAngle(axis, angle);
        }
    }

    updateState(data) {
        this.currentState = data;
        const { cartesian, state, bloch } = data;

        const EPSILON = 1e-6;
        let x = isNaN(cartesian.x) ? 0 : cartesian.x;
        let y = isNaN(cartesian.y) ? 0 : cartesian.y;
        let z = isNaN(cartesian.z) ? 0 : cartesian.z;

        const direction = new THREE.Vector3(x, y, z);
        let length = direction.length();
        if (length < EPSILON) {
            length = EPSILON;
            direction.set(0, 1, 0);
        }
        const normalized = direction.clone().normalize();

        const shaftLength = Math.min(Math.max(length, 0.1), 1.0) * 0.85;

        this.arrowShaft.position.copy(normalized.clone().multiplyScalar(shaftLength / 2));
        this.arrowShaft.scale.set(1, shaftLength, 1);
        this.arrowShaft.visible = true;
        this.setArrowQuaternion(this.arrowShaft, normalized);

        this.arrowHead.position.copy(normalized.clone().multiplyScalar(shaftLength + 0.075));
        this.arrowHead.visible = true;
        this.setArrowQuaternion(this.arrowHead, normalized);

        this.stateGlow.position.copy(direction);
        this.stateGlow.visible = true;

        if (this.showTrail) {
            this.trailPoints.push(new THREE.Vector3(x, y, z));
            if (this.trailPoints.length > 100) {
                this.trailPoints.shift();
            }
            this.updateTrail();
        }

        this.updateUI(data);
    }

    updateTrail() {
        if (this.trailPoints.length < 2) {
            const positions = new Float32Array(6);
            this.trail.geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            return;
        }

        const positions = new Float32Array(this.trailPoints.length * 3);
        for (let i = 0; i < this.trailPoints.length; i++) {
            positions[i * 3] = this.trailPoints[i].x;
            positions[i * 3 + 1] = this.trailPoints[i].y;
            positions[i * 3 + 2] = this.trailPoints[i].z;
        }

        this.trail.geometry.setAttribute(
            'position',
            new THREE.BufferAttribute(positions, 3)
        );
        this.trail.geometry.computeBoundingSphere();

        const colors = new Float32Array(this.trailPoints.length * 3);
        for (let i = 0; i < this.trailPoints.length; i++) {
            const t = i / this.trailPoints.length;
            colors[i * 3] = 0.7 + t * 0.3;
            colors[i * 3 + 1] = 0.5 + t * 0.3;
            colors[i * 3 + 2] = 1.0;
        }
        this.trail.geometry.setAttribute(
            'color',
            new THREE.BufferAttribute(colors, 3)
        );
    }

    updateUI(data) {
        const { state, bloch } = data;
        const EPSILON = 1e-10;

        const cleanRe = (val) => Math.abs(val) < EPSILON ? 0 : val;
        const cleanIm = (val) => Math.abs(val) < EPSILON ? 0 : val;

        const alphaRe = cleanRe(state.alpha.re);
        const alphaIm = cleanIm(state.alpha.im);
        const betaRe = cleanRe(state.beta.re);
        const betaIm = cleanIm(state.beta.im);

        const alphaStr = this.formatComplex(alphaRe, alphaIm);
        const betaStr = this.formatComplex(betaRe, betaIm);

        document.getElementById('alpha-value').textContent = alphaStr;
        document.getElementById('beta-value').textContent = betaStr;

        const probZero = alphaRe * alphaRe + alphaIm * alphaIm;
        const probOne = betaRe * betaRe + betaIm * betaIm;

        document.getElementById('prob-zero').textContent = probZero.toFixed(3);
        document.getElementById('prob-one').textContent = probOne.toFixed(3);

        const stateVec = this.formatStateVector(state);
        document.getElementById('state-vector').textContent = stateVec;

        if (!this.isAnimating) {
            document.getElementById('theta').value = bloch.theta.toFixed(1);
            document.getElementById('theta-value').textContent = bloch.theta.toFixed(1) + '°';
            document.getElementById('phi').value = bloch.phi.toFixed(1);
            document.getElementById('phi-value').textContent = bloch.phi.toFixed(1) + '°';
        }

        const betaMagSq = betaRe * betaRe + betaIm * betaIm;
        let phase = this._lastPhase !== undefined ? this._lastPhase : 0;
        
        if (betaMagSq > EPSILON) {
            const rawPhase = Math.atan2(betaIm, betaRe);
            if (Math.abs(rawPhase - Math.PI) < 0.01) {
                phase = Math.PI;
            } else if (Math.abs(rawPhase + Math.PI) < 0.01) {
                phase = -Math.PI;
            } else {
                phase = rawPhase;
            }
            this._lastPhase = phase;
        }

        const hue = (phase / (2 * Math.PI) + 0.5) * 360;
        const hueClamped = Math.max(0, Math.min(360, hue));
        
        this.arrowShaft.material.color.setHSL(hueClamped / 360, 0.8, 0.6);
        this.arrowShaft.material.emissive.setHSL(hueClamped / 360, 0.8, 0.3);
        this.arrowHead.material.color.setHSL(hueClamped / 360, 0.8, 0.6);
        this.arrowHead.material.emissive.setHSL(hueClamped / 360, 0.8, 0.3);
        this.stateGlow.material.color.setHSL(hueClamped / 360, 0.8, 0.6);
    }

    formatComplex(re, im) {
        const EPSILON = 1e-10;
        const reStr = re.toFixed(3);
        const imAbs = Math.abs(im).toFixed(3);
        const sign = im >= 0 ? '+' : '-';
        if (Math.abs(im) < EPSILON) return `${reStr}`;
        if (Math.abs(re) < EPSILON) return `${im >= 0 ? '' : '-'}${imAbs}i`;
        return `${reStr} ${sign} ${imAbs}i`;
    }

    formatStateVector(state) {
        const EPSILON = 1e-10;
        const alpha = state.alpha;
        const beta = state.beta;

        const alphaMag = Math.sqrt(alpha.re * alpha.re + alpha.im * alpha.im);
        const betaMag = Math.sqrt(beta.re * beta.re + beta.im * beta.im);

        let alphaPhase = 0;
        let betaPhase = 0;

        if (alphaMag > EPSILON) {
            const re = Math.abs(alpha.re) < EPSILON ? 0 : alpha.re;
            const im = Math.abs(alpha.im) < EPSILON ? 0 : alpha.im;
            alphaPhase = Math.atan2(im, re);
        }
        if (betaMag > EPSILON) {
            const re = Math.abs(beta.re) < EPSILON ? 0 : beta.re;
            const im = Math.abs(beta.im) < EPSILON ? 0 : beta.im;
            betaPhase = Math.atan2(im, re);
        }

        if (alphaMag > 0.99) return '|0⟩';
        if (betaMag > 0.99) return '|1⟩';

        let result = '';

        if (alphaMag > 0.01) {
            if (Math.abs(alphaPhase) < 0.01) {
                result += alphaMag < 0.99 ? `${alphaMag.toFixed(2)}·` : '';
            } else {
                const phaseStr = (alphaPhase / Math.PI).toFixed(2);
                result += `e^(${phaseStr}πi)·`;
            }
            result += '|0⟩';
        }

        if (betaMag > 0.01) {
            if (result) result += ' + ';
            const relPhase = betaPhase - alphaPhase;
            if (Math.abs(relPhase) < 0.01) {
                result += betaMag < 0.99 ? `${betaMag.toFixed(2)}·` : '';
            } else {
                const phaseStr = (relPhase / Math.PI).toFixed(2);
                result += `e^(${phaseStr}πi)·`;
            }
            result += '|1⟩';
        }

        return result;
    }

    onWindowResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    updateFps() {
        this.frameCount++;
        const now = performance.now();
        if (now - this.lastFpsUpdate >= 1000) {
            const fps = Math.round(this.frameCount * 1000 / (now - this.lastFpsUpdate));
            document.getElementById('fps-counter').textContent = fps;
            this.frameCount = 0;
            this.lastFpsUpdate = now;
        }
    }

    animate() {
        requestAnimationFrame(() => this.animate());

        this.updateAnimation();

        if (this.phaseShader) {
            this.phaseShader.material.uniforms.time.value = performance.now() * 0.001;
        }

        this.controls.update();
        this.renderer.render(this.scene, this.camera);
        this.updateFps();
    }
}

const blochSphere = new BlochSphere();
