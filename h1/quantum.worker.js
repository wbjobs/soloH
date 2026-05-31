class Complex {
    constructor(re = 0, im = 0) {
        this.re = re;
        this.im = im;
        this._cleanup();
    }

    static get EPSILON() { return 1e-12; }

    _cleanup() {
        if (Math.abs(this.re) < Complex.EPSILON) this.re = 0;
        if (Math.abs(this.im) < Complex.EPSILON) this.im = 0;
    }

    add(other) {
        const result = new Complex(
            this.re + other.re,
            this.im + other.im
        );
        result._cleanup();
        return result;
    }

    sub(other) {
        const result = new Complex(
            this.re - other.re,
            this.im - other.im
        );
        result._cleanup();
        return result;
    }

    mul(other) {
        const result = new Complex(
            this.re * other.re - this.im * other.im,
            this.re * other.im + this.im * other.re
        );
        result._cleanup();
        return result;
    }

    scale(s) {
        const result = new Complex(
            this.re * s,
            this.im * s
        );
        result._cleanup();
        return result;
    }

    abs2() {
        const val = this.re * this.re + this.im * this.im;
        return val < Complex.EPSILON ? 0 : val;
    }

    abs() {
        const val = this.abs2();
        return val < Complex.EPSILON ? 0 : Math.sqrt(val);
    }

    conj() {
        return new Complex(this.re, -this.im);
    }

    phase() {
        if (this.abs2() < Complex.EPSILON) return 0;
        const re = Math.abs(this.re) < Complex.EPSILON ? 0 : this.re;
        const im = Math.abs(this.im) < Complex.EPSILON ? 0 : this.im;
        if (re === 0 && im === 0) return 0;
        return Math.atan2(im, re);
    }

    clone() {
        return new Complex(this.re, this.im);
    }

    toString(precision = 3) {
        const re = this.re.toFixed(precision);
        const im = Math.abs(this.im).toFixed(precision);
        const sign = this.im >= 0 ? '+' : '-';
        if (Math.abs(this.im) < 1e-10) return `${re}`;
        if (Math.abs(this.re) < 1e-10) return `${this.im >= 0 ? '' : '-'}${im}i`;
        return `${re} ${sign} ${im}i`;
    }
}

class QuantumMath {
    static validateNumber(n) {
        if (isNaN(n) || !isFinite(n)) return 0;
        return n;
    }

    static matrixMul(matrix, vector) {
        const result = [new Complex(0, 0), new Complex(0, 0)];
        for (let i = 0; i < 2; i++) {
            for (let j = 0; j < 2; j++) {
                result[i] = result[i].add(matrix[i][j].mul(vector[j]));
            }
        }
        return result;
    }

    static normalize(vector) {
        let norm = Math.sqrt(vector[0].abs2() + vector[1].abs2());
        if (norm < 1e-10 || isNaN(norm) || !isFinite(norm)) {
            return [new Complex(1, 0), new Complex(0, 0)];
        }
        norm = Math.min(Math.max(norm, 1e-10), 1e10);
        return [vector[0].scale(1 / norm), vector[1].scale(1 / norm)];
    }

    static blochToState(theta, phi) {
        let thetaRad = theta * Math.PI / 180;
        let phiRad = phi * Math.PI / 180;

        thetaRad = this.validateNumber(thetaRad);
        phiRad = this.validateNumber(phiRad);

        const cosT2 = Math.max(-1, Math.min(1, Math.cos(thetaRad / 2)));
        const sinT2 = Math.max(-1, Math.min(1, Math.sin(thetaRad / 2)));
        const cosP = Math.max(-1, Math.min(1, Math.cos(phiRad)));
        const sinP = Math.max(-1, Math.min(1, Math.sin(phiRad)));

        const alpha = new Complex(cosT2, 0);
        const beta = new Complex(
            sinT2 * cosP,
            sinT2 * sinP
        );
        return [alpha, beta];
    }

    static stateToBloch(state) {
        const [alpha, beta] = state;
        let theta = 2 * Math.acos(Math.min(1, Math.max(0, alpha.abs())));
        theta = this.validateNumber(theta);

        const betaNorm = beta.abs();
        let phi = 0;
        if (betaNorm > 1e-10) {
            phi = beta.phase();
            phi = this.validateNumber(phi);
        }

        theta = Math.max(0, Math.min(Math.PI, theta));
        if (phi > Math.PI) phi -= 2 * Math.PI;
        if (phi < -Math.PI) phi += 2 * Math.PI;

        return {
            theta: theta * 180 / Math.PI,
            phi: phi * 180 / Math.PI
        };
    }

    static blochToCartesian(theta, phi) {
        let thetaRad = theta * Math.PI / 180;
        let phiRad = phi * Math.PI / 180;

        thetaRad = this.validateNumber(thetaRad);
        phiRad = this.validateNumber(phiRad);

        let x = Math.sin(thetaRad) * Math.cos(phiRad);
        let y = Math.sin(thetaRad) * Math.sin(phiRad);
        let z = Math.cos(thetaRad);

        x = this.validateNumber(x);
        y = this.validateNumber(y);
        z = this.validateNumber(z);

        const len = Math.sqrt(x * x + y * y + z * z);
        if (len > 1e-10) {
            x /= len;
            y /= len;
            z /= len;
        } else {
            x = 0;
            y = 0;
            z = 1;
        }

        return { x, y, z };
    }

    static slerp(v1, v2, t) {
        t = Math.max(0, Math.min(1, t));

        let dot = Math.min(1, Math.max(-1,
            v1[0].conj().mul(v2[0]).add(v1[1].conj().mul(v2[1])).re
        ));
        dot = this.validateNumber(dot);

        if (dot > 0.9995) {
            return QuantumMath.normalize([
                new Complex(v1[0].re + t * (v2[0].re - v1[0].re),
                           v1[0].im + t * (v2[0].im - v1[0].im)),
                new Complex(v1[1].re + t * (v2[1].re - v1[1].re),
                           v1[1].im + t * (v2[1].im - v1[1].im))
            ]);
        }

        let omega = Math.acos(dot);
        omega = this.validateNumber(omega);
        const sinOmega = Math.max(1e-10, Math.sin(omega));
        const a = Math.sin((1 - t) * omega) / sinOmega;
        const b = Math.sin(t * omega) / sinOmega;

        return QuantumMath.normalize([
            v1[0].scale(a).add(v2[0].scale(b)),
            v1[1].scale(a).add(v2[1].scale(b))
        ]);
    }

    static tensorProduct(state1, state2) {
        const n1 = state1.length;
        const n2 = state2.length;
        const result = new Array(n1 * n2);
        for (let i = 0; i < n1; i++) {
            for (let j = 0; j < n2; j++) {
                result[i * n2 + j] = state1[i].mul(state2[j]);
            }
        }
        return result;
    }

    static matrixVectorMul(matrix, vector) {
        const n = matrix.length;
        const m = vector.length;
        const result = new Array(n);
        for (let i = 0; i < n; i++) {
            result[i] = new Complex(0, 0);
            for (let j = 0; j < m; j++) {
                result[i] = result[i].add(matrix[i][j].mul(vector[j]));
            }
        }
        return result;
    }

    static matrixMatrixMul(m1, m2) {
        const n = m1.length;
        const m = m2[0].length;
        const p = m2.length;
        const result = new Array(n);
        for (let i = 0; i < n; i++) {
            result[i] = new Array(m);
            for (let j = 0; j < m; j++) {
                result[i][j] = new Complex(0, 0);
                for (let k = 0; k < p; k++) {
                    result[i][j] = result[i][j].add(m1[i][k].mul(m2[k][j]));
                }
            }
        }
        return result;
    }

    static kron(m1, m2) {
        const n1 = m1.length;
        const n2 = m1[0].length;
        const m1r = m2.length;
        const m2r = m2[0].length;
        const result = new Array(n1 * m1r);
        for (let i = 0; i < n1 * m1r; i++) {
            result[i] = new Array(n2 * m2r);
            for (let j = 0; j < n2 * m2r; j++) {
                const a = Math.floor(i / m1r);
                const b = i % m1r;
                const c = Math.floor(j / m2r);
                const d = j % m2r;
                result[i][j] = m1[a][c].mul(m2[b][d]);
            }
        }
        return result;
    }

    static applySingleQubitGate(state, gate, qubit, totalQubits) {
        const dim = Math.pow(2, totalQubits);
        let fullGate = [[new Complex(1, 0)]];
        
        for (let i = 0; i < totalQubits; i++) {
            if (i === qubit) {
                fullGate = this.kron(fullGate, gate);
            } else {
                fullGate = this.kron(fullGate, [
                    [new Complex(1, 0), new Complex(0, 0)],
                    [new Complex(0, 0), new Complex(1, 0)]
                ]);
            }
        }
        
        return this.matrixVectorMul(fullGate, state);
    }

    static applyCNOT(state, control, target, totalQubits) {
        const dim = Math.pow(2, totalQubits);
        const cnot = [
            [new Complex(1, 0), new Complex(0, 0), new Complex(0, 0), new Complex(0, 0)],
            [new Complex(0, 0), new Complex(1, 0), new Complex(0, 0), new Complex(0, 0)],
            [new Complex(0, 0), new Complex(0, 0), new Complex(0, 0), new Complex(1, 0)],
            [new Complex(0, 0), new Complex(0, 0), new Complex(1, 0), new Complex(0, 0)]
        ];

        let permuted = this.permuteQubits(state, [control, target], totalQubits);

        let fullGate = [[new Complex(1, 0)]];
        for (let i = 0; i < totalQubits - 2; i++) {
            fullGate = this.kron(fullGate, [
                [new Complex(1, 0), new Complex(0, 0)],
                [new Complex(0, 0), new Complex(1, 0)]
            ]);
        }
        fullGate = this.kron(cnot, fullGate);

        const result = this.matrixVectorMul(fullGate, permuted);
        
        return this.permuteQubits(result, this.inversePermutation([control, target], totalQubits), totalQubits);
    }

    static permuteQubits(state, order, totalQubits) {
        const dim = Math.pow(2, totalQubits);
        const result = new Array(dim);
        for (let i = 0; i < dim; i++) {
            let newIdx = 0;
            for (let j = 0; j < totalQubits; j++) {
                const bit = (i >> (totalQubits - 1 - j)) & 1;
                newIdx |= bit << (totalQubits - 1 - order[j]);
            }
            result[newIdx] = state[i].clone();
        }
        return result;
    }

    static inversePermutation(order, totalQubits) {
        const inv = new Array(totalQubits);
        const otherQubits = [];
        for (let i = 0; i < totalQubits; i++) {
            if (!order.includes(i)) otherQubits.push(i);
        }
        const fullOrder = [...order, ...otherQubits];
        for (let i = 0; i < totalQubits; i++) {
            inv[fullOrder[i]] = i;
        }
        return inv;
    }

    static normalizeState(state) {
        let norm = 0;
        for (const amp of state) {
            norm += amp.abs2();
        }
        norm = Math.sqrt(norm);
        if (norm < 1e-10) return state;
        return state.map(amp => amp.scale(1 / norm));
    }

    static expectationValue(state, observable) {
        const applied = this.matrixVectorMul(observable, state);
        let expectation = new Complex(0, 0);
        for (let i = 0; i < state.length; i++) {
            expectation = expectation.add(state[i].conj().mul(applied[i]));
        }
        return expectation.re;
    }

    static getBellState(index = 0) {
        const sqrt2 = 1 / Math.sqrt(2);
        switch (index) {
            case 0:
                return [
                    new Complex(sqrt2, 0), new Complex(0, 0),
                    new Complex(0, 0), new Complex(sqrt2, 0)
                ];
            case 1:
                return [
                    new Complex(sqrt2, 0), new Complex(0, 0),
                    new Complex(0, 0), new Complex(-sqrt2, 0)
                ];
            case 2:
                return [
                    new Complex(0, 0), new Complex(sqrt2, 0),
                    new Complex(sqrt2, 0), new Complex(0, 0)
                ];
            case 3:
                return [
                    new Complex(0, 0), new Complex(sqrt2, 0),
                    new Complex(-sqrt2, 0), new Complex(0, 0)
                ];
            default:
                return this.getBellState(0);
        }
    }

    static rotateBasis(angle, axis) {
        const half = angle / 2;
        const cos = Math.cos(half);
        const sin = Math.sin(half);
        
        switch (axis) {
            case 'x':
                return [
                    [new Complex(cos, 0), new Complex(0, -sin)],
                    [new Complex(0, -sin), new Complex(cos, 0)]
                ];
            case 'y':
                return [
                    [new Complex(cos, 0), new Complex(-sin, 0)],
                    [new Complex(sin, 0), new Complex(cos, 0)]
                ];
            case 'z':
            default:
                return [
                    [new Complex(cos, -sin), new Complex(0, 0)],
                    [new Complex(0, 0), new Complex(cos, sin)]
                ];
        }
    }

    static measureQubit(state, qubit, totalQubits) {
        const dim = Math.pow(2, totalQubits);
        let prob0 = 0;
        let prob1 = 0;
        
        for (let i = 0; i < dim; i++) {
            const bit = (i >> (totalQubits - 1 - qubit)) & 1;
            if (bit === 0) prob0 += state[i].abs2();
            else prob1 += state[i].abs2();
        }
        
        return { prob0, prob1 };
    }

    static densityMatrixReduced(state, keepQubit, totalQubits) {
        const dim = Math.pow(2, totalQubits);
        const rho = [[new Complex(0, 0), new Complex(0, 0)], [new Complex(0, 0), new Complex(0, 0)]];
        
        for (let i = 0; i < dim; i++) {
            for (let j = 0; j < dim; j++) {
                const bitI = (i >> (totalQubits - 1 - keepQubit)) & 1;
                const bitJ = (j >> (totalQubits - 1 - keepQubit)) & 1;
                
                const otherBitsEqual = (i & ~(1 << (totalQubits - 1 - keepQubit))) === 
                                      (j & ~(1 << (totalQubits - 1 - keepQubit)));
                
                if (otherBitsEqual) {
                    rho[bitI][bitJ] = rho[bitI][bitJ].add(state[i].mul(state[j].conj()));
                }
            }
        }
        
        return rho;
    }

    static blochVectorFromRho(rho) {
        const x = 2 * rho[0][1].re;
        const y = 2 * rho[0][1].im;
        const z = rho[0][0].re - rho[1][1].re;
        return { x, y, z };
    }
}

const Gates = {
    H: [
        [new Complex(1 / Math.sqrt(2), 0), new Complex(1 / Math.sqrt(2), 0)],
        [new Complex(1 / Math.sqrt(2), 0), new Complex(-1 / Math.sqrt(2), 0)]
    ],
    X: [
        [new Complex(0, 0), new Complex(1, 0)],
        [new Complex(1, 0), new Complex(0, 0)]
    ],
    Y: [
        [new Complex(0, 0), new Complex(0, -1)],
        [new Complex(0, 1), new Complex(0, 0)]
    ],
    Z: [
        [new Complex(1, 0), new Complex(0, 0)],
        [new Complex(0, 0), new Complex(-1, 0)]
    ],
    S: [
        [new Complex(1, 0), new Complex(0, 0)],
        [new Complex(0, 0), new Complex(0, 1)]
    ],
    T: [
        [new Complex(1, 0), new Complex(0, 0)],
        [new Complex(0, 0), new Complex(Math.SQRT1_2, Math.SQRT1_2)]
    ]
};

let currentState = [new Complex(1, 0), new Complex(0, 0)];
let twoQubitState = null;
let customGates = {};
let gateSequence = [];
let recordedSequence = [];

function stateToJSONFull(state) {
    const EPSILON = 1e-12;
    const clean = (v) => {
        if (isNaN(v) || !isFinite(v)) return 0;
        return Math.abs(v) < EPSILON ? 0 : v;
    };
    return state.map(c => ({ re: clean(c.re), im: clean(c.im) }));
}

function parseCSVMatrix(csvText) {
    const lines = csvText.trim().split('\n').filter(line => line.trim());
    const matrix = [];
    
    for (const line of lines) {
        const parts = line.split(/[,;\t|]/).map(p => p.trim()).filter(p => p);
        const row = [];
        
        for (const part of parts) {
            let re = 0, im = 0;
            const match = part.match(/^([+-]?[\d.]+(?:e[+-]?\d+)?)\s*([+-]?\s*[\d.]+(?:e[+-]?\d+)?)?\s*[ji]?$/i);
            
            if (match) {
                re = parseFloat(match[1]) || 0;
                if (match[2]) {
                    const imStr = match[2].replace(/\s+/g, '');
                    im = parseFloat(imStr) || 0;
                }
            } else {
                const imMatch = part.match(/^([+-]?\s*[\d.]+(?:e[+-]?\d+)?)\s*[ji]$/i);
                if (imMatch) {
                    im = parseFloat(imMatch[1].replace(/\s+/g, '')) || 0;
                } else {
                    re = parseFloat(part) || 0;
                }
            }
            
            row.push(new Complex(re, im));
        }
        
        if (row.length > 0) matrix.push(row);
    }
    
    return matrix;
}

function isUnitary(matrix, tolerance = 1e-6) {
    const n = matrix.length;
    const identity = new Array(n);
    for (let i = 0; i < n; i++) {
        identity[i] = new Array(n);
        for (let j = 0; j < n; j++) {
            identity[i][j] = new Complex(i === j ? 1 : 0, 0);
        }
    }
    
    const conjTranspose = new Array(n);
    for (let i = 0; i < n; i++) {
        conjTranspose[i] = new Array(n);
        for (let j = 0; j < n; j++) {
            conjTranspose[i][j] = matrix[j][i].conj();
        }
    }
    
    const product = QuantumMath.matrixMatrixMul(conjTranspose, matrix);
    
    for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
            const diff = product[i][j].sub(identity[i][j]);
            if (diff.abs() > tolerance) return false;
        }
    }
    
    return true;
}

function computeCHSH(state, angles) {
    const { a1, a2, b1, b2 } = angles;
    
    const pauliZ = [
        [new Complex(1, 0), new Complex(0, 0)],
        [new Complex(0, 0), new Complex(-1, 0)]
    ];
    
    function rotatedPauli(angle, qubit) {
        const rot = QuantumMath.rotateBasis(-angle, 'y');
        const rotConj = [
            [rot[0][0].conj(), rot[1][0].conj()],
            [rot[0][1].conj(), rot[1][1].conj()]
        ];
        const rotated = QuantumMath.matrixMatrixMul(QuantumMath.matrixMatrixMul(rot, pauliZ), rotConj);
        
        const identity = [
            [new Complex(1, 0), new Complex(0, 0)],
            [new Complex(0, 0), new Complex(1, 0)]
        ];
        
        if (qubit === 0) {
            return QuantumMath.kron(rotated, identity);
        } else {
            return QuantumMath.kron(identity, rotated);
        }
    }
    
    function tensorObservable(A, B) {
        return QuantumMath.matrixMatrixMul(A, B);
    }
    
    const A1 = rotatedPauli(a1, 0);
    const A2 = rotatedPauli(a2, 0);
    const B1 = rotatedPauli(b1, 1);
    const B2 = rotatedPauli(b2, 1);
    
    const E11 = QuantumMath.expectationValue(state, tensorObservable(A1, B1));
    const E12 = QuantumMath.expectationValue(state, tensorObservable(A1, B2));
    const E21 = QuantumMath.expectationValue(state, tensorObservable(A2, B1));
    const E22 = QuantumMath.expectationValue(state, tensorObservable(A2, B2));
    
    const S1 = E11 + E12 + E21 - E22;
    const S2 = E11 + E12 - E21 + E22;
    const S3 = E11 - E12 + E21 + E22;
    const S4 = -E11 + E12 + E21 + E22;
    
    const S = Math.max(Math.abs(S1), Math.abs(S2), Math.abs(S3), Math.abs(S4));
    
    return {
        S,
        S_values: [S1, S2, S3, S4],
        correlations: { E11, E12, E21, E22 },
        angles: { a1, a2, b1, b2 },
        violatesCHSH: S > 2,
        classicalLimit: 2,
        quantumLimit: 2 * Math.sqrt(2)
    };
}

function handleMessage(e) {
    const { type, data } = e.data;

    switch (type) {
        case 'applyGate': {
            const gate = Gates[data.gate];
            if (gate) {
                const newState = QuantumMath.matrixMul(gate, currentState);
                currentState = QuantumMath.normalize(newState);
                const bloch = QuantumMath.stateToBloch(currentState);
                postResult('stateUpdate', {
                    state: stateToJSON(currentState),
                    bloch,
                    cartesian: QuantumMath.blochToCartesian(bloch.theta, bloch.phi)
                });
            }
            break;
        }

        case 'setBloch': {
            const { theta, phi } = data;
            currentState = QuantumMath.blochToState(theta, phi);
            postResult('stateUpdate', {
                state: stateToJSON(currentState),
                bloch: { theta, phi },
                cartesian: QuantumMath.blochToCartesian(theta, phi)
            });
            break;
        }

        case 'getState': {
            const bloch = QuantumMath.stateToBloch(currentState);
            postResult('stateUpdate', {
                state: stateToJSON(currentState),
                bloch,
                cartesian: QuantumMath.blochToCartesian(bloch.theta, bloch.phi)
            });
            break;
        }

        case 'reset': {
            currentState = [new Complex(1, 0), new Complex(0, 0)];
            postResult('stateUpdate', {
                state: stateToJSON(currentState),
                bloch: { theta: 0, phi: 0 },
                cartesian: { x: 0, y: 0, z: 1 }
            });
            break;
        }

        case 'animate': {
            const { gate, steps = 60 } = data;
            const gateMatrix = Gates[gate];
            if (!gateMatrix) return;

            const startState = currentState.map(c => c.clone());
            const targetState = QuantumMath.normalize(
                QuantumMath.matrixMul(gateMatrix, startState)
            );

            const frameCount = steps + 1;
            const floatsPerFrame = 9;
            const trajectory = new Float64Array(frameCount * floatsPerFrame);

            for (let i = 0; i < frameCount; i++) {
                const t = i / steps;
                const interpState = QuantumMath.slerp(startState, targetState, t);
                const bloch = QuantumMath.stateToBloch(interpState);
                const cartesian = QuantumMath.blochToCartesian(bloch.theta, bloch.phi);

                const idx = i * floatsPerFrame;
                trajectory[idx]     = interpState[0].re;
                trajectory[idx + 1] = interpState[0].im;
                trajectory[idx + 2] = interpState[1].re;
                trajectory[idx + 3] = interpState[1].im;
                trajectory[idx + 4] = bloch.theta;
                trajectory[idx + 5] = bloch.phi;
                trajectory[idx + 6] = cartesian.x;
                trajectory[idx + 7] = cartesian.y;
                trajectory[idx + 8] = cartesian.z;
            }

            currentState = targetState;
            postResult('animationData', {
                trajectory: trajectory.buffer,
                steps: frameCount,
                gate
            }, [trajectory.buffer]);
            break;
        }
    }
}

function stateToJSON(state) {
    const EPSILON = 1e-12;
    const clean = (v) => {
        if (isNaN(v) || !isFinite(v)) return 0;
        return Math.abs(v) < EPSILON ? 0 : v;
    };
    return {
        alpha: { re: clean(state[0].re), im: clean(state[0].im) },
        beta: { re: clean(state[1].re), im: clean(state[1].im) }
    };
}

function postResult(type, data, transfer = undefined) {
    const message = { type, data };
    try {
        if (transfer) {
            self.postMessage(message, transfer);
        } else {
            self.postMessage(message);
        }
    } catch (e) {
        console.error('Worker postMessage error:', e);
        const fallback = {
            type,
            data: JSON.parse(JSON.stringify(data))
        };
        self.postMessage(fallback);
    }
}

self.addEventListener('message', handleMessage);

postResult('ready', {});
