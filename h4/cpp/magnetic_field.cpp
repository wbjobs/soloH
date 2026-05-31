#define _USE_MATH_DEFINES
#include <emscripten.h>
#include <emscripten/bind.h>
#include <vector>
#include <cmath>
#include <array>
#include <functional>
#include <string>
#include <sstream>
#include <iomanip>
#include <algorithm>

using namespace emscripten;

struct Vec3 {
    double x, y, z;
    
    Vec3() : x(0), y(0), z(0) {}
    Vec3(double x, double y, double z) : x(x), y(y), z(z) {}
    
    Vec3 operator+(const Vec3& other) const {
        return Vec3(x + other.x, y + other.y, z + other.z);
    }
    
    Vec3 operator-(const Vec3& other) const {
        return Vec3(x - other.x, y - other.y, z - other.z);
    }
    
    Vec3 operator*(double scalar) const {
        return Vec3(x * scalar, y * scalar, z * scalar);
    }
    
    Vec3 operator/(double scalar) const {
        return Vec3(x / scalar, y / scalar, z / scalar);
    }
    
    double dot(const Vec3& other) const {
        return x * other.x + y * other.y + z * other.z;
    }
    
    Vec3 cross(const Vec3& other) const {
        return Vec3(
            y * other.z - z * other.y,
            z * other.x - x * other.z,
            x * other.y - y * other.x
        );
    }
    
    double length() const {
        return std::sqrt(x * x + y * y + z * z);
    }
    
    double lengthSquared() const {
        return x * x + y * y + z * z;
    }
    
    Vec3 normalized() const {
        double len = length();
        if (len == 0) return Vec3(0, 0, 0);
        return *this / len;
    }
};

struct WireSegment {
    Vec3 start;
    Vec3 end;
    double current;
    double errorEstimate;
    int refinementLevel;
    bool needsRefinement;
    
    WireSegment() : current(0), errorEstimate(0), refinementLevel(0), needsRefinement(false) {}
    WireSegment(const Vec3& s, const Vec3& e, double c) 
        : start(s), end(e), current(c), errorEstimate(0), refinementLevel(0), needsRefinement(false) {}
};

struct AdaptiveWire {
    std::vector<WireSegment> segments;
    double baseCurrent;
    double timeFrequency;
    double timePhase;
    int maxRefinementLevel;
    double errorTolerance;
    
    AdaptiveWire() : baseCurrent(0), timeFrequency(0), timePhase(0), maxRefinementLevel(3), errorTolerance(1e-3) {}
};

struct FieldSample {
    Vec3 position;
    Vec3 B;
    Vec3 E;
    double Bmag;
    double Emag;
};

class MagneticFieldSolver {
private:
    std::vector<AdaptiveWire> adaptiveWires;
    const double mu0 = 4 * M_PI * 1e-7;
    const double epsilon0 = 8.854e-12;
    const double c = 299792458.0;
    
    Vec3 computeSegmentField(const WireSegment& seg, const Vec3& point, double currentScale = 1.0) const {
        const double eps = 1e-6;
        Vec3 dl = seg.end - seg.start;
        double len = dl.length();
        
        if (len < eps) return Vec3(0, 0, 0);
        
        int steps = std::max(1, (int)(len / 0.02));
        Vec3 totalField(0, 0, 0);
        
        for (int i = 0; i < steps; i++) {
            double t1 = (double)i / steps;
            double t2 = (double)(i + 1) / steps;
            Vec3 p1 = seg.start + dl * t1;
            Vec3 p2 = seg.start + dl * t2;
            Vec3 dseg = p2 - p1;
            Vec3 mid = (p1 + p2) * 0.5;
            Vec3 disp = point - mid;
            double rMag = disp.length();
            
            if (rMag < eps) continue;
            
            double r3 = rMag * rMag * rMag;
            Vec3 cross = disp.cross(dseg);
            totalField = totalField + cross * (mu0 * seg.current * currentScale / (4 * M_PI * r3));
        }
        
        return totalField;
    }
    
    double estimateSegmentError(const WireSegment& seg) const {
        Vec3 mid = (seg.start + seg.end) * 0.5;
        Vec3 quarter = (seg.start + mid) * 0.5;
        Vec3 threeQuarter = (mid + seg.end) * 0.5;
        
        Vec3 testPoints[] = {quarter, mid, threeQuarter};
        double maxError = 0;
        
        for (const auto& tp : testPoints) {
            Vec3 fieldCoarse = computeSegmentField(seg, tp);
            
            WireSegment seg1(seg.start, mid, seg.current);
            WireSegment seg2(mid, seg.end, seg.current);
            Vec3 fieldFine = computeSegmentField(seg1, tp) + computeSegmentField(seg2, tp);
            
            double error = (fieldFine - fieldCoarse).length() / std::max(fieldFine.length(), 1e-12);
            maxError = std::max(maxError, error);
        }
        
        return maxError;
    }
    
public:
    MagneticFieldSolver() {}
    
    void clearWires() {
        adaptiveWires.clear();
    }
    
    void addWireSegment(const Vec3& start, const Vec3& end, double current) {
        if (adaptiveWires.empty() || adaptiveWires.back().baseCurrent != current) {
            AdaptiveWire wire;
            wire.baseCurrent = current;
            adaptiveWires.push_back(wire);
        }
        
        WireSegment seg(start, end, current);
        adaptiveWires.back().segments.push_back(seg);
    }
    
    void setWireTimeDependence(int wireIndex, double frequency, double phase = 0) {
        if (wireIndex >= 0 && wireIndex < (int)adaptiveWires.size()) {
            adaptiveWires[wireIndex].timeFrequency = frequency;
            adaptiveWires[wireIndex].timePhase = phase;
        }
    }
    
    void setRefinementParameters(int maxLevel, double tolerance) {
        for (auto& wire : adaptiveWires) {
            wire.maxRefinementLevel = maxLevel;
            wire.errorTolerance = tolerance;
        }
    }
    
    std::vector<double> estimateAllErrors() {
        std::vector<double> allErrors;
        
        for (auto& wire : adaptiveWires) {
            for (auto& seg : wire.segments) {
                seg.errorEstimate = estimateSegmentError(seg);
                seg.needsRefinement = seg.errorEstimate > wire.errorTolerance && 
                                     seg.refinementLevel < wire.maxRefinementLevel;
                allErrors.push_back(seg.errorEstimate);
            }
        }
        
        return allErrors;
    }
    
    int adaptiveRefinement() {
        int totalRefined = 0;
        int maxIterations = 5;
        
        for (int iter = 0; iter < maxIterations; iter++) {
            estimateAllErrors();
            
            bool anyRefined = false;
            std::vector<AdaptiveWire> newWires;
            
            for (const auto& wire : adaptiveWires) {
                AdaptiveWire newWire = wire;
                newWire.segments.clear();
                
                for (const auto& seg : wire.segments) {
                    if (seg.needsRefinement) {
                        Vec3 mid = (seg.start + seg.end) * 0.5;
                        WireSegment seg1(seg.start, mid, seg.current);
                        WireSegment seg2(mid, seg.end, seg.current);
                        seg1.refinementLevel = seg.refinementLevel + 1;
                        seg2.refinementLevel = seg.refinementLevel + 1;
                        newWire.segments.push_back(seg1);
                        newWire.segments.push_back(seg2);
                        anyRefined = true;
                        totalRefined++;
                    } else {
                        newWire.segments.push_back(seg);
                    }
                }
                
                newWires.push_back(newWire);
            }
            
            adaptiveWires = newWires;
            
            if (!anyRefined) break;
        }
        
        return totalRefined;
    }
    
    std::vector<int> getRefinementLevels() const {
        std::vector<int> levels;
        for (const auto& wire : adaptiveWires) {
            for (const auto& seg : wire.segments) {
                levels.push_back(seg.refinementLevel);
            }
        }
        return levels;
    }
    
    Vec3 computeBiotSavart(const Vec3& point) const {
        return computeBiotSavartTime(point, 0);
    }
    
    Vec3 computeBiotSavartTime(const Vec3& point, double time) const {
        Vec3 totalField(0, 0, 0);
        
        for (const auto& wire : adaptiveWires) {
            double currentScale = 1.0;
            if (wire.timeFrequency > 0) {
                currentScale = std::sin(2 * M_PI * wire.timeFrequency * time + wire.timePhase);
            }
            
            for (const auto& seg : wire.segments) {
                totalField = totalField + computeSegmentField(seg, point, currentScale);
            }
        }
        
        return totalField;
    }
    
    Vec3 computeVortexElectricField(const Vec3& point, double time, double dt = 1e-5) const {
        Vec3 B_plus = computeBiotSavartTime(point, time + dt);
        Vec3 B_minus = computeBiotSavartTime(point, time - dt);
        Vec3 dBdt = (B_plus - B_minus) / (2 * dt);
        
        const double eps = 0.01;
        Vec3 dx(eps, 0, 0);
        Vec3 dy(0, eps, 0);
        Vec3 dz(0, 0, eps);
        
        Vec3 Bx_plus = computeBiotSavartTime(point + dx, time);
        Vec3 Bx_minus = computeBiotSavartTime(point - dx, time);
        Vec3 By_plus = computeBiotSavartTime(point + dy, time);
        Vec3 By_minus = computeBiotSavartTime(point - dy, time);
        Vec3 Bz_plus = computeBiotSavartTime(point + dz, time);
        Vec3 Bz_minus = computeBiotSavartTime(point - dz, time);
        
        double dBz_dy = (By_plus.z - By_minus.z) / (2 * eps);
        double dBy_dz = (Bz_plus.y - Bz_minus.y) / (2 * eps);
        double dBx_dz = (Bz_plus.x - Bz_minus.x) / (2 * eps);
        double dBz_dx = (Bx_plus.z - Bx_minus.z) / (2 * eps);
        double dBy_dx = (Bx_plus.y - Bx_minus.y) / (2 * eps);
        double dBx_dy = (By_plus.x - By_minus.x) / (2 * eps);
        
        Vec3 curlB(
            dBz_dy - dBy_dz,
            dBx_dz - dBz_dx,
            dBy_dx - dBx_dy
        );
        
        Vec3 E_faraday(-dBdt.x, -dBdt.y, -dBdt.z);
        
        double mu = mu0;
        double eps = epsilon0;
        Vec3 E_displacement = curlB / (mu * eps) - dBdt / (c * c);
        
        return E_faraday + E_displacement * 0.1;
    }
    
    Vec3 rkf45Step(const Vec3& pos, double& h, double tol, bool forward) const {
        return rkf45StepTime(pos, h, tol, forward, 0);
    }
    
    Vec3 rkf45StepTime(const Vec3& pos, double& h, double tol, bool forward, double time) const {
        const double h_min = 1e-6;
        if (h < h_min) h = h_min;
        
        Vec3 k1 = computeBiotSavartTime(pos, time);
        if (!forward) k1 = k1 * (-1.0);
        k1 = k1.normalized() * h;
        
        Vec3 k2 = computeBiotSavartTime(pos + k1 * (1.0/4.0), time);
        if (!forward) k2 = k2 * (-1.0);
        k2 = k2.normalized() * h;
        
        Vec3 k3 = computeBiotSavartTime(pos + k1 * (3.0/32.0) + k2 * (9.0/32.0), time);
        if (!forward) k3 = k3 * (-1.0);
        k3 = k3.normalized() * h;
        
        Vec3 k4 = computeBiotSavartTime(pos + k1 * (1932.0/2197.0) + k2 * (-7200.0/2197.0) + k3 * (7296.0/2197.0), time);
        if (!forward) k4 = k4 * (-1.0);
        k4 = k4.normalized() * h;
        
        Vec3 k5 = computeBiotSavartTime(pos + k1 * (439.0/216.0) + k2 * (-8.0) + k3 * (3680.0/513.0) + k4 * (-845.0/4104.0), time);
        if (!forward) k5 = k5 * (-1.0);
        k5 = k5.normalized() * h;
        
        Vec3 k6 = computeBiotSavartTime(pos + k1 * (-8.0/27.0) + k2 * (2.0) + k3 * (-3544.0/2565.0) + k4 * (1859.0/4104.0) + k5 * (-11.0/40.0), time);
        if (!forward) k6 = k6 * (-1.0);
        k6 = k6.normalized() * h;
        
        Vec3 y5 = pos + k1 * (16.0/135.0) + k3 * (6656.0/12825.0) + k4 * (28561.0/56430.0) + k5 * (-9.0/50.0) + k6 * (2.0/55.0);
        Vec3 y4 = pos + k1 * (25.0/216.0) + k3 * (1408.0/2565.0) + k4 * (2197.0/4104.0) + k5 * (-1.0/5.0);
        
        double error = (y5 - y4).length();
        
        if (error > 0) {
            double hNew = 0.9 * h * std::pow(tol / error, 0.2);
            h = std::min(std::max(hNew, h_min), h * 2.0);
        }
        
        return y5;
    }
    
    std::vector<Vec3> traceFieldLine(const Vec3& start, double maxStepSize, double tol, int maxSteps, bool forward) const {
        return traceFieldLineTime(start, maxStepSize, tol, maxSteps, forward, 0);
    }
    
    std::vector<Vec3> traceFieldLineTime(const Vec3& start, double maxStepSize, double tol, int maxSteps, bool forward, double time) const {
        std::vector<Vec3> points;
        points.push_back(start);
        
        Vec3 pos = start;
        double h = maxStepSize;
        const double h_min = 1e-6;
        int smallStepCount = 0;
        
        for (int i = 0; i < maxSteps; i++) {
            Vec3 b = computeBiotSavartTime(pos, time);
            if (b.length() < 1e-12) break;
            
            if (h < h_min) {
                h = h_min;
                smallStepCount++;
            } else {
                smallStepCount = 0;
            }
            
            if (smallStepCount > 10) break;
            
            Vec3 newPos = rkf45StepTime(pos, h, tol, forward, time);
            Vec3 delta = newPos - pos;
            
            if (delta.length() < 1e-9) break;
            
            points.push_back(newPos);
            pos = newPos;
            
            if (delta.length() > 100.0) break;
        }
        
        return points;
    }
    
    std::vector<std::vector<Vec3>> traceFieldLines(const Vec3& start, double maxStepSize, double tol, int maxSteps) const {
        std::vector<std::vector<Vec3>> result;
        
        auto forward = traceFieldLine(start, maxStepSize, tol, maxSteps, true);
        auto backward = traceFieldLine(start, maxStepSize, tol, maxSteps, false);
        
        std::reverse(backward.begin(), backward.end());
        backward.pop_back();
        
        result.push_back(backward);
        result.push_back(forward);
        
        return result;
    }
    
    double getFieldMagnitude(const Vec3& point) const {
        return computeBiotSavart(point).length();
    }
    
    std::vector<double> computeHeatmapSlice(const Vec3& origin, const Vec3& normal, double size, int resolution) const {
        return computeHeatmapSliceTime(origin, normal, size, resolution, 0);
    }
    
    std::vector<double> computeHeatmapSliceTime(const Vec3& origin, const Vec3& normal, double size, int resolution, double time) const {
        std::vector<double> result(resolution * resolution);
        
        Vec3 u = normal.cross(Vec3(1, 0, 0));
        if (u.length() < 1e-9) {
            u = normal.cross(Vec3(0, 1, 0));
        }
        u = u.normalized();
        Vec3 v = normal.cross(u).normalized();
        
        double halfSize = size / 2.0;
        double step = size / (resolution - 1);
        
        for (int i = 0; i < resolution; i++) {
            for (int j = 0; j < resolution; j++) {
                double x = -halfSize + i * step;
                double y = -halfSize + j * step;
                Vec3 point = origin + u * x + v * y;
                result[i * resolution + j] = computeBiotSavartTime(point, time).length();
            }
        }
        
        return result;
    }
    
    std::vector<double> computeEFieldSlice(const Vec3& origin, const Vec3& normal, double size, int resolution, double time) const {
        std::vector<double> result(resolution * resolution);
        
        Vec3 u = normal.cross(Vec3(1, 0, 0));
        if (u.length() < 1e-9) {
            u = normal.cross(Vec3(0, 1, 0));
        }
        u = u.normalized();
        Vec3 v = normal.cross(u).normalized();
        
        double halfSize = size / 2.0;
        double step = size / (resolution - 1);
        
        for (int i = 0; i < resolution; i++) {
            for (int j = 0; j < resolution; j++) {
                double x = -halfSize + i * step;
                double y = -halfSize + j * step;
                Vec3 point = origin + u * x + v * y;
                result[i * resolution + j] = computeVortexElectricField(point, time).length();
            }
        }
        
        return result;
    }
    
    std::string exportVTK(const Vec3& min, const Vec3& max, 
                          int nx, int ny, int nz, double time = 0) const {
        std::ostringstream ss;
        ss << std::scientific << std::setprecision(8);
        
        ss << "# vtk DataFile Version 3.0\n";
        ss << "Magnetic Field Data - Biot-Savart Solver\n";
        ss << "ASCII\n";
        ss << "DATASET STRUCTURED_POINTS\n";
        ss << "DIMENSIONS " << nx << " " << ny << " " << nz << "\n";
        ss << "ORIGIN " << min.x << " " << min.y << " " << min.z << "\n";
        
        double dx = (max.x - min.x) / (nx - 1);
        double dy = (max.y - min.y) / (ny - 1);
        double dz = (max.z - min.z) / (nz - 1);
        ss << "SPACING " << dx << " " << dy << " " << dz << "\n";
        
        int nPoints = nx * ny * nz;
        ss << "POINT_DATA " << nPoints << "\n";
        
        ss << "SCALARS B_magnitude double 1\n";
        ss << "LOOKUP_TABLE default\n";
        for (int k = 0; k < nz; k++) {
            for (int j = 0; j < ny; j++) {
                for (int i = 0; i < nx; i++) {
                    Vec3 p(min.x + i * dx, min.y + j * dy, min.z + k * dz);
                    ss << computeBiotSavartTime(p, time).length() << "\n";
                }
            }
        }
        
        ss << "VECTORS B_field double\n";
        for (int k = 0; k < nz; k++) {
            for (int j = 0; j < ny; j++) {
                for (int i = 0; i < nx; i++) {
                    Vec3 p(min.x + i * dx, min.y + j * dy, min.z + k * dz);
                    Vec3 B = computeBiotSavartTime(p, time);
                    ss << B.x << " " << B.y << " " << B.z << "\n";
                }
            }
        }
        
        ss << "SCALARS E_magnitude double 1\n";
        ss << "LOOKUP_TABLE default\n";
        for (int k = 0; k < nz; k++) {
            for (int j = 0; j < ny; j++) {
                for (int i = 0; i < nx; i++) {
                    Vec3 p(min.x + i * dx, min.y + j * dy, min.z + k * dz);
                    ss << computeVortexElectricField(p, time).length() << "\n";
                }
            }
        }
        
        ss << "VECTORS E_field double\n";
        for (int k = 0; k < nz; k++) {
            for (int j = 0; j < ny; j++) {
                for (int i = 0; i < nx; i++) {
                    Vec3 p(min.x + i * dx, min.y + j * dy, min.z + k * dz);
                    Vec3 E = computeVortexElectricField(p, time);
                    ss << E.x << " " << E.y << " " << E.z << "\n";
                }
            }
        }
        
        ss << "SCALARS refinement_level int 1\n";
        ss << "LOOKUP_TABLE default\n";
        int totalSegs = 0;
        for (const auto& wire : adaptiveWires) {
            for (const auto& seg : wire.segments) {
                (void)seg;
                totalSegs++;
            }
        }
        for (int i = 0; i < nPoints; i++) {
            ss << 0 << "\n";
        }
        
        return ss.str();
    }
    
    int getTotalSegments() const {
        int count = 0;
        for (const auto& wire : adaptiveWires) {
            count += wire.segments.size();
        }
        return count;
    }
    
    int getWireCount() const {
        return adaptiveWires.size();
    }
};

EMSCRIPTEN_BINDINGS(magnetic_field) {
    class_<Vec3>("Vec3")
        .constructor<double, double, double>()
        .property("x", &Vec3::x)
        .property("y", &Vec3::y)
        .property("z", &Vec3::z);
    
    class_<MagneticFieldSolver>("MagneticFieldSolver")
        .constructor<>()
        .function("clearWires", &MagneticFieldSolver::clearWires)
        .function("addWireSegment", &MagneticFieldSolver::addWireSegment)
        .function("computeBiotSavart", &MagneticFieldSolver::computeBiotSavart)
        .function("computeBiotSavartTime", &MagneticFieldSolver::computeBiotSavartTime)
        .function("computeVortexElectricField", &MagneticFieldSolver::computeVortexElectricField)
        .function("getFieldMagnitude", &MagneticFieldSolver::getFieldMagnitude)
        .function("traceFieldLine", &MagneticFieldSolver::traceFieldLine)
        .function("traceFieldLineTime", &MagneticFieldSolver::traceFieldLineTime)
        .function("traceFieldLines", &MagneticFieldSolver::traceFieldLines)
        .function("computeHeatmapSlice", &MagneticFieldSolver::computeHeatmapSlice)
        .function("computeHeatmapSliceTime", &MagneticFieldSolver::computeHeatmapSliceTime)
        .function("computeEFieldSlice", &MagneticFieldSolver::computeEFieldSlice)
        .function("exportVTK", &MagneticFieldSolver::exportVTK)
        .function("estimateAllErrors", &MagneticFieldSolver::estimateAllErrors)
        .function("adaptiveRefinement", &MagneticFieldSolver::adaptiveRefinement)
        .function("getRefinementLevels", &MagneticFieldSolver::getRefinementLevels)
        .function("setRefinementParameters", &MagneticFieldSolver::setRefinementParameters)
        .function("setWireTimeDependence", &MagneticFieldSolver::setWireTimeDependence)
        .function("getTotalSegments", &MagneticFieldSolver::getTotalSegments)
        .function("getWireCount", &MagneticFieldSolver::getWireCount);
    
    register_vector<Vec3>("VectorVec3");
    register_vector<double>("VectorDouble");
    register_vector<int>("VectorInt");
    register_vector<std::vector<Vec3>>("VectorVectorVec3");
}
