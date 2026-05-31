(function(global) {
    'use strict';

    class Vec3 {
        constructor(x = 0, y = 0, z = 0) {
            this.x = x;
            this.y = y;
            this.z = z;
        }

        add(v) {
            return new Vec3(this.x + v.x, this.y + v.y, this.z + v.z);
        }

        sub(v) {
            return new Vec3(this.x - v.x, this.y - v.y, this.z - v.z);
        }

        mul(s) {
            return new Vec3(this.x * s, this.y * s, this.z * s);
        }

        div(s) {
            return new Vec3(this.x / s, this.y / s, this.z / s);
        }

        dot(v) {
            return this.x * v.x + this.y * v.y + this.z * v.z;
        }

        cross(v) {
            return new Vec3(
                this.y * v.z - this.z * v.y,
                this.z * v.x - this.x * v.z,
                this.x * v.y - this.y * v.x
            );
        }

        length() {
            return Math.sqrt(this.x * this.x + this.y * this.y + this.z * this.z);
        }

        lengthSquared() {
            return this.x * this.x + this.y * this.y + this.z * this.z;
        }

        normalized() {
            const len = this.length();
            if (len === 0) return new Vec3(0, 0, 0);
            return this.div(len);
        }

        clone() {
            return new Vec3(this.x, this.y, this.z);
        }
    }

    class WireSegment {
        constructor(start, end, current) {
            this.start = start;
            this.end = end;
            this.current = current;
            this.errorEstimate = 0;
            this.refinementLevel = 0;
            this.needsRefinement = false;
        }
    }

    class AdaptiveWire {
        constructor() {
            this.segments = [];
            this.baseCurrent = 0;
            this.timeFrequency = 0;
            this.timePhase = 0;
            this.maxRefinementLevel = 3;
            this.errorTolerance = 1e-3;
        }
    }

    class MagneticFieldSolverJS {
        constructor() {
            this.adaptiveWires = [];
            this.mu0 = 4 * Math.PI * 1e-7;
            this.epsilon0 = 8.854e-12;
            this.c = 299792458.0;
        }

        clearWires() {
            this.adaptiveWires = [];
        }

        addWireSegment(start, end, current) {
            if (this.adaptiveWires.length === 0 || 
                this.adaptiveWires[this.adaptiveWires.length - 1].baseCurrent !== current) {
                const wire = new AdaptiveWire();
                wire.baseCurrent = current;
                this.adaptiveWires.push(wire);
            }

            const seg = new WireSegment(start, end, current);
            this.adaptiveWires[this.adaptiveWires.length - 1].segments.push(seg);
        }

        setWireTimeDependence(wireIndex, frequency, phase = 0) {
            if (wireIndex >= 0 && wireIndex < this.adaptiveWires.length) {
                this.adaptiveWires[wireIndex].timeFrequency = frequency;
                this.adaptiveWires[wireIndex].timePhase = phase;
            }
        }

        setRefinementParameters(maxLevel, tolerance) {
            for (const wire of this.adaptiveWires) {
                wire.maxRefinementLevel = maxLevel;
                wire.errorTolerance = tolerance;
            }
        }

        computeSegmentField(seg, point, currentScale = 1.0) {
            const eps = 1e-6;
            const dl = seg.end.sub(seg.start);
            const len = dl.length();

            if (len < eps) return new Vec3(0, 0, 0);

            const steps = Math.max(1, Math.floor(len / 0.02));
            let totalField = new Vec3(0, 0, 0);

            for (let i = 0; i < steps; i++) {
                const t1 = i / steps;
                const t2 = (i + 1) / steps;
                const p1 = seg.start.add(dl.mul(t1));
                const p2 = seg.start.add(dl.mul(t2));
                const dseg = p2.sub(p1);
                const mid = p1.add(p2).mul(0.5);
                const disp = point.sub(mid);
                const rMag = disp.length();

                if (rMag < eps) continue;

                const r3 = rMag * rMag * rMag;
                const cross = disp.cross(dseg);
                totalField = totalField.add(cross.mul(this.mu0 * seg.current * currentScale / (4 * Math.PI * r3)));
            }

            return totalField;
        }

        estimateSegmentError(seg) {
            const mid = seg.start.add(seg.end).mul(0.5);
            const quarter = seg.start.add(mid).mul(0.5);
            const threeQuarter = mid.add(seg.end).mul(0.5);

            const testPoints = [quarter, mid, threeQuarter];
            let maxError = 0;

            for (const tp of testPoints) {
                const fieldCoarse = this.computeSegmentField(seg, tp);

                const seg1 = new WireSegment(seg.start, mid, seg.current);
                const seg2 = new WireSegment(mid, seg.end, seg.current);
                const fieldFine = this.computeSegmentField(seg1, tp).add(this.computeSegmentField(seg2, tp));

                const error = fieldFine.sub(fieldCoarse).length() / Math.max(fieldFine.length(), 1e-12);
                maxError = Math.max(maxError, error);
            }

            return maxError;
        }

        estimateAllErrors() {
            const allErrors = [];

            for (const wire of this.adaptiveWires) {
                for (const seg of wire.segments) {
                    seg.errorEstimate = this.estimateSegmentError(seg);
                    seg.needsRefinement = seg.errorEstimate > wire.errorTolerance && 
                                         seg.refinementLevel < wire.maxRefinementLevel;
                    allErrors.push(seg.errorEstimate);
                }
            }

            return allErrors;
        }

        adaptiveRefinement() {
            let totalRefined = 0;
            const maxIterations = 5;

            for (let iter = 0; iter < maxIterations; iter++) {
                this.estimateAllErrors();

                let anyRefined = false;
                const newWires = [];

                for (const wire of this.adaptiveWires) {
                    const newWire = new AdaptiveWire();
                    Object.assign(newWire, wire);
                    newWire.segments = [];

                    for (const seg of wire.segments) {
                        if (seg.needsRefinement) {
                            const mid = seg.start.add(seg.end).mul(0.5);
                            const seg1 = new WireSegment(seg.start, mid, seg.current);
                            const seg2 = new WireSegment(mid, seg.end, seg.current);
                            seg1.refinementLevel = seg.refinementLevel + 1;
                            seg2.refinementLevel = seg.refinementLevel + 1;
                            newWire.segments.push(seg1);
                            newWire.segments.push(seg2);
                            anyRefined = true;
                            totalRefined++;
                        } else {
                            newWire.segments.push(seg);
                        }
                    }

                    newWires.push(newWire);
                }

                this.adaptiveWires = newWires;

                if (!anyRefined) break;
            }

            return totalRefined;
        }

        getRefinementLevels() {
            const levels = [];
            for (const wire of this.adaptiveWires) {
                for (const seg of wire.segments) {
                    levels.push(seg.refinementLevel);
                }
            }
            return levels;
        }

        computeBiotSavart(point) {
            return this.computeBiotSavartTime(point, 0);
        }

        computeBiotSavartTime(point, time) {
            let totalField = new Vec3(0, 0, 0);

            for (const wire of this.adaptiveWires) {
                let currentScale = 1.0;
                if (wire.timeFrequency > 0) {
                    currentScale = Math.sin(2 * Math.PI * wire.timeFrequency * time + wire.timePhase);
                }

                for (const seg of wire.segments) {
                    totalField = totalField.add(this.computeSegmentField(seg, point, currentScale));
                }
            }

            return totalField;
        }

        computeVortexElectricField(point, time, dt = 1e-5) {
            const B_plus = this.computeBiotSavartTime(point, time + dt);
            const B_minus = this.computeBiotSavartTime(point, time - dt);
            const dBdt = B_plus.sub(B_minus).div(2 * dt);

            const eps = 0.01;
            const dx = new Vec3(eps, 0, 0);
            const dy = new Vec3(0, eps, 0);
            const dz = new Vec3(0, 0, eps);

            const Bx_plus = this.computeBiotSavartTime(point.add(dx), time);
            const Bx_minus = this.computeBiotSavartTime(point.sub(dx), time);
            const By_plus = this.computeBiotSavartTime(point.add(dy), time);
            const By_minus = this.computeBiotSavartTime(point.sub(dy), time);
            const Bz_plus = this.computeBiotSavartTime(point.add(dz), time);
            const Bz_minus = this.computeBiotSavartTime(point.sub(dz), time);

            const dBz_dy = (By_plus.z - By_minus.z) / (2 * eps);
            const dBy_dz = (Bz_plus.y - Bz_minus.y) / (2 * eps);
            const dBx_dz = (Bz_plus.x - Bz_minus.x) / (2 * eps);
            const dBz_dx = (Bx_plus.z - Bx_minus.z) / (2 * eps);
            const dBy_dx = (Bx_plus.y - Bx_minus.y) / (2 * eps);
            const dBx_dy = (By_plus.x - By_minus.x) / (2 * eps);

            const curlB = new Vec3(
                dBz_dy - dBy_dz,
                dBx_dz - dBz_dx,
                dBy_dx - dBx_dy
            );

            const E_faraday = new Vec3(-dBdt.x, -dBdt.y, -dBdt.z);

            const mu = this.mu0;
            const eps0 = this.epsilon0;
            const E_displacement = curlB.div(mu * eps0).sub(dBdt.div(this.c * this.c));

            return E_faraday.add(E_displacement.mul(0.1));
        }

        rkf45Step(pos, hRef, tol, forward) {
            return this.rkf45StepTime(pos, hRef, tol, forward, 0);
        }

        rkf45StepTime(pos, hRef, tol, forward, time) {
            const h_min = 1e-6;
            if (hRef[0] < h_min) hRef[0] = h_min;
            let h = hRef[0];

            let k1 = this.computeBiotSavartTime(pos, time);
            if (!forward) k1 = k1.mul(-1);
            k1 = k1.normalized().mul(h);

            let k2 = this.computeBiotSavartTime(pos.add(k1.mul(1/4)), time);
            if (!forward) k2 = k2.mul(-1);
            k2 = k2.normalized().mul(h);

            let k3 = this.computeBiotSavartTime(pos.add(k1.mul(3/32)).add(k2.mul(9/32)), time);
            if (!forward) k3 = k3.mul(-1);
            k3 = k3.normalized().mul(h);

            let k4 = this.computeBiotSavartTime(pos.add(k1.mul(1932/2197)).add(k2.mul(-7200/2197)).add(k3.mul(7296/2197)), time);
            if (!forward) k4 = k4.mul(-1);
            k4 = k4.normalized().mul(h);

            let k5 = this.computeBiotSavartTime(pos.add(k1.mul(439/216)).add(k2.mul(-8)).add(k3.mul(3680/513)).add(k4.mul(-845/4104)), time);
            if (!forward) k5 = k5.mul(-1);
            k5 = k5.normalized().mul(h);

            let k6 = this.computeBiotSavartTime(pos.add(k1.mul(-8/27)).add(k2.mul(2)).add(k3.mul(-3544/2565)).add(k4.mul(1859/4104)).add(k5.mul(-11/40)), time);
            if (!forward) k6 = k6.mul(-1);
            k6 = k6.normalized().mul(h);

            const y5 = pos.add(k1.mul(16/135)).add(k3.mul(6656/12825)).add(k4.mul(28561/56430)).add(k5.mul(-9/50)).add(k6.mul(2/55));
            const y4 = pos.add(k1.mul(25/216)).add(k3.mul(1408/2565)).add(k4.mul(2197/4104)).add(k5.mul(-1/5));

            const error = y5.sub(y4).length();

            if (error > 0) {
                const hNew = 0.9 * h * Math.pow(tol / error, 0.2);
                hRef[0] = Math.min(Math.max(hNew, h_min), h * 2);
            }

            return y5;
        }

        traceFieldLine(start, maxStepSize, tol, maxSteps, forward) {
            return this.traceFieldLineTime(start, maxStepSize, tol, maxSteps, forward, 0);
        }

        traceFieldLineTime(start, maxStepSize, tol, maxSteps, forward, time) {
            const points = [start.clone()];
            let pos = start.clone();
            const hRef = [maxStepSize];
            const h_min = 1e-6;
            let smallStepCount = 0;

            for (let i = 0; i < maxSteps; i++) {
                const b = this.computeBiotSavartTime(pos, time);
                if (b.length() < 1e-12) break;

                if (hRef[0] < h_min) {
                    hRef[0] = h_min;
                    smallStepCount++;
                } else {
                    smallStepCount = 0;
                }

                if (smallStepCount > 10) break;

                const newPos = this.rkf45StepTime(pos, hRef, tol, forward, time);
                const delta = newPos.sub(pos);

                if (delta.length() < 1e-9) break;

                points.push(newPos);
                pos = newPos;

                if (delta.length() > 100) break;
            }

            return points;
        }

        traceFieldLines(start, maxStepSize, tol, maxSteps) {
            const forward = this.traceFieldLine(start, maxStepSize, tol, maxSteps, true);
            let backward = this.traceFieldLine(start, maxStepSize, tol, maxSteps, false);

            backward.reverse();
            backward.pop();

            return [backward, forward];
        }

        getFieldMagnitude(point) {
            return this.computeBiotSavart(point).length();
        }

        computeHeatmapSlice(origin, normal, size, resolution) {
            return this.computeHeatmapSliceTime(origin, normal, size, resolution, 0);
        }

        computeHeatmapSliceTime(origin, normal, size, resolution, time) {
            const result = new Array(resolution * resolution);

            let u = normal.cross(new Vec3(1, 0, 0));
            if (u.length() < 1e-9) {
                u = normal.cross(new Vec3(0, 1, 0));
            }
            u = u.normalized();
            const v = normal.cross(u).normalized();

            const halfSize = size / 2;
            const step = size / (resolution - 1);

            for (let i = 0; i < resolution; i++) {
                for (let j = 0; j < resolution; j++) {
                    const x = -halfSize + i * step;
                    const y = -halfSize + j * step;
                    const point = origin.add(u.mul(x)).add(v.mul(y));
                    result[i * resolution + j] = this.computeBiotSavartTime(point, time).length();
                }
            }

            return result;
        }

        computeEFieldSlice(origin, normal, size, resolution, time) {
            const result = new Array(resolution * resolution);

            let u = normal.cross(new Vec3(1, 0, 0));
            if (u.length() < 1e-9) {
                u = normal.cross(new Vec3(0, 1, 0));
            }
            u = u.normalized();
            const v = normal.cross(u).normalized();

            const halfSize = size / 2;
            const step = size / (resolution - 1);

            for (let i = 0; i < resolution; i++) {
                for (let j = 0; j < resolution; j++) {
                    const x = -halfSize + i * step;
                    const y = -halfSize + j * step;
                    const point = origin.add(u.mul(x)).add(v.mul(y));
                    result[i * resolution + j] = this.computeVortexElectricField(point, time).length();
                }
            }

            return result;
        }

        exportVTK(min, max, nx, ny, nz, time = 0) {
            let str = '';

            str += '# vtk DataFile Version 3.0\n';
            str += 'Magnetic Field Data - Biot-Savart Solver\n';
            str += 'ASCII\n';
            str += 'DATASET STRUCTURED_POINTS\n';
            str += 'DIMENSIONS ' + nx + ' ' + ny + ' ' + nz + '\n';
            str += 'ORIGIN ' + min.x + ' ' + min.y + ' ' + min.z + '\n';

            const dx = (max.x - min.x) / (nx - 1);
            const dy = (max.y - min.y) / (ny - 1);
            const dz = (max.z - min.z) / (nz - 1);
            str += 'SPACING ' + dx + ' ' + dy + ' ' + dz + '\n';

            const nPoints = nx * ny * nz;
            str += 'POINT_DATA ' + nPoints + '\n';

            str += 'SCALARS B_magnitude double 1\n';
            str += 'LOOKUP_TABLE default\n';
            for (let k = 0; k < nz; k++) {
                for (let j = 0; j < ny; j++) {
                    for (let i = 0; i < nx; i++) {
                        const p = new Vec3(min.x + i * dx, min.y + j * dy, min.z + k * dz);
                        str += this.computeBiotSavartTime(p, time).length().toExponential(8) + '\n';
                    }
                }
            }

            str += 'VECTORS B_field double\n';
            for (let k = 0; k < nz; k++) {
                for (let j = 0; j < ny; j++) {
                    for (let i = 0; i < nx; i++) {
                        const p = new Vec3(min.x + i * dx, min.y + j * dy, min.z + k * dz);
                        const B = this.computeBiotSavartTime(p, time);
                        str += B.x.toExponential(8) + ' ' + B.y.toExponential(8) + ' ' + B.z.toExponential(8) + '\n';
                    }
                }
            }

            str += 'SCALARS E_magnitude double 1\n';
            str += 'LOOKUP_TABLE default\n';
            for (let k = 0; k < nz; k++) {
                for (let j = 0; j < ny; j++) {
                    for (let i = 0; i < nx; i++) {
                        const p = new Vec3(min.x + i * dx, min.y + j * dy, min.z + k * dz);
                        str += this.computeVortexElectricField(p, time).length().toExponential(8) + '\n';
                    }
                }
            }

            str += 'VECTORS E_field double\n';
            for (let k = 0; k < nz; k++) {
                for (let j = 0; j < ny; j++) {
                    for (let i = 0; i < nx; i++) {
                        const p = new Vec3(min.x + i * dx, min.y + j * dy, min.z + k * dz);
                        const E = this.computeVortexElectricField(p, time);
                        str += E.x.toExponential(8) + ' ' + E.y.toExponential(8) + ' ' + E.z.toExponential(8) + '\n';
                    }
                }
            }

            str += 'SCALARS refinement_level int 1\n';
            str += 'LOOKUP_TABLE default\n';
            for (let i = 0; i < nPoints; i++) {
                str += '0\n';
            }

            return str;
        }

        getTotalSegments() {
            let count = 0;
            for (const wire of this.adaptiveWires) {
                count += wire.segments.length;
            }
            return count;
        }

        getWireCount() {
            return this.adaptiveWires.length;
        }
    }

    global.MagneticFieldSolverJS = MagneticFieldSolverJS;
    global.Vec3 = Vec3;

})(window);
