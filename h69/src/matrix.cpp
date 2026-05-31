#include "hbsolver/matrix.h"
#include <cmath>
#include <algorithm>

namespace hbsolver {

ComplexMat MatrixOps::multiply(const ComplexMat& A, const ComplexMat& B) {
    if (A.empty() || B.empty() || A[0].size() != B.size()) {
        throw std::invalid_argument("Invalid matrix dimensions for multiplication");
    }

    int m = static_cast<int>(A.size());
    int n = static_cast<int>(B[0].size());
    int k = static_cast<int>(A[0].size());

    ComplexMat C(m, ComplexVec(n, Complex(0.0, 0.0)));
    for (int i = 0; i < m; ++i) {
        for (int j = 0; j < n; ++j) {
            for (int l = 0; l < k; ++l) {
                C[i][j] += A[i][l] * B[l][j];
            }
        }
    }
    return C;
}

ComplexVec MatrixOps::multiply(const ComplexMat& A, const ComplexVec& x) {
    if (A.empty() || A[0].size() != x.size()) {
        throw std::invalid_argument("Invalid matrix-vector dimensions");
    }

    int m = static_cast<int>(A.size());
    int n = static_cast<int>(x.size());
    ComplexVec y(m, Complex(0.0, 0.0));
    for (int i = 0; i < m; ++i) {
        for (int j = 0; j < n; ++j) {
            y[i] += A[i][j] * x[j];
        }
    }
    return y;
}

ComplexMat MatrixOps::multiply(const ComplexMat& A, double s) {
    ComplexMat B = A;
    for (auto& row : B) {
        for (auto& elem : row) {
            elem *= s;
        }
    }
    return B;
}

ComplexMat MatrixOps::add(const ComplexMat& A, const ComplexMat& B) {
    if (A.size() != B.size() || A[0].size() != B[0].size()) {
        throw std::invalid_argument("Matrix dimensions do not match for addition");
    }
    ComplexMat C = A;
    for (size_t i = 0; i < A.size(); ++i) {
        for (size_t j = 0; j < A[0].size(); ++j) {
            C[i][j] += B[i][j];
        }
    }
    return C;
}

ComplexMat MatrixOps::subtract(const ComplexMat& A, const ComplexMat& B) {
    if (A.size() != B.size() || A[0].size() != B[0].size()) {
        throw std::invalid_argument("Matrix dimensions do not match for subtraction");
    }
    ComplexMat C = A;
    for (size_t i = 0; i < A.size(); ++i) {
        for (size_t j = 0; j < A[0].size(); ++j) {
            C[i][j] -= B[i][j];
        }
    }
    return C;
}

ComplexMat MatrixOps::transpose(const ComplexMat& A) {
    if (A.empty()) return A;
    int m = static_cast<int>(A.size());
    int n = static_cast<int>(A[0].size());
    ComplexMat B(n, ComplexVec(m));
    for (int i = 0; i < m; ++i) {
        for (int j = 0; j < n; ++j) {
            B[j][i] = A[i][j];
        }
    }
    return B;
}

ComplexMat MatrixOps::conjugate(const ComplexMat& A) {
    ComplexMat B = A;
    for (auto& row : B) {
        for (auto& elem : row) {
            elem = std::conj(elem);
        }
    }
    return B;
}

ComplexMat MatrixOps::identity(int n) {
    ComplexMat I(n, ComplexVec(n, Complex(0.0, 0.0)));
    for (int i = 0; i < n; ++i) {
        I[i][i] = Complex(1.0, 0.0);
    }
    return I;
}

ComplexMat MatrixOps::zeros(int rows, int cols) {
    return ComplexMat(rows, ComplexVec(cols, Complex(0.0, 0.0)));
}

double MatrixOps::norm(const ComplexVec& v) {
    double sum = 0.0;
    for (const auto& elem : v) {
        sum += std::norm(elem);
    }
    return std::sqrt(sum);
}

double MatrixOps::dotProduct(const ComplexVec& a, const ComplexVec& b) {
    if (a.size() != b.size()) {
        throw std::invalid_argument("Vector sizes do not match for dot product");
    }
    Complex sum(0.0, 0.0);
    for (size_t i = 0; i < a.size(); ++i) {
        sum += std::conj(a[i]) * b[i];
    }
    return std::real(sum);
}

bool MatrixOps::luDecomposition(const ComplexMat& A, ComplexMat& L, ComplexMat& U, IntVec& pivot) {
    int n = static_cast<int>(A.size());
    L = identity(n);
    U = A;
    pivot.resize(n);
    for (int i = 0; i < n; ++i) pivot[i] = i;

    for (int k = 0; k < n - 1; ++k) {
        int pivot_row = k;
        double max_val = std::abs(U[k][k]);
        for (int i = k + 1; i < n; ++i) {
            if (std::abs(U[i][k]) > max_val) {
                max_val = std::abs(U[i][k]);
                pivot_row = i;
            }
        }

        if (max_val < 1e-15) {
            return false;
        }

        if (pivot_row != k) {
            std::swap(U[k], U[pivot_row]);
            std::swap(pivot[k], pivot[pivot_row]);
            for (int j = 0; j < k; ++j) {
                std::swap(L[k][j], L[pivot_row][j]);
            }
        }

        Complex pivot_val = U[k][k];
        for (int i = k + 1; i < n; ++i) {
            L[i][k] = U[i][k] / pivot_val;
            for (int j = k; j < n; ++j) {
                U[i][j] -= L[i][k] * U[k][j];
            }
        }
    }
    return true;
}

void MatrixOps::forwardSubstitution(const ComplexMat& L, const ComplexVec& b, ComplexVec& y, const IntVec& pivot) {
    int n = static_cast<int>(L.size());
    y.resize(n);
    for (int i = 0; i < n; ++i) {
        y[i] = b[pivot[i]];
        for (int j = 0; j < i; ++j) {
            y[i] -= L[i][j] * y[j];
        }
    }
}

void MatrixOps::backwardSubstitution(const ComplexMat& U, const ComplexVec& y, ComplexVec& x) {
    int n = static_cast<int>(U.size());
    x.resize(n);
    for (int i = n - 1; i >= 0; --i) {
        x[i] = y[i];
        for (int j = i + 1; j < n; ++j) {
            x[i] -= U[i][j] * x[j];
        }
        x[i] /= U[i][i];
    }
}

bool MatrixOps::solveLinearSystem(const ComplexMat& A, const ComplexVec& b, ComplexVec& x) {
    int n = static_cast<int>(A.size());
    if (n != static_cast<int>(b.size()) || n != static_cast<int>(A[0].size())) {
        return false;
    }

    ComplexMat L, U;
    IntVec pivot;
    if (!luDecomposition(A, L, U, pivot)) {
        return false;
    }

    ComplexVec y;
    forwardSubstitution(L, b, y, pivot);
    backwardSubstitution(U, y, x);
    return true;
}

bool MatrixOps::gaussElimination(ComplexMat& A, ComplexVec& b) {
    int n = static_cast<int>(A.size());
    for (int k = 0; k < n; ++k) {
        int pivot_row = k;
        double max_val = std::abs(A[k][k]);
        for (int i = k + 1; i < n; ++i) {
            if (std::abs(A[i][k]) > max_val) {
                max_val = std::abs(A[i][k]);
                pivot_row = i;
            }
        }

        if (max_val < 1e-15) {
            return false;
        }

        if (pivot_row != k) {
            std::swap(A[k], A[pivot_row]);
            std::swap(b[k], b[pivot_row]);
        }

        Complex pivot_val = A[k][k];
        for (int i = k + 1; i < n; ++i) {
            Complex factor = A[i][k] / pivot_val;
            for (int j = k; j < n; ++j) {
                A[i][j] -= factor * A[k][j];
            }
            b[i] -= factor * b[k];
        }
    }

    for (int i = n - 1; i >= 0; --i) {
        for (int j = i + 1; j < n; ++j) {
            b[i] -= A[i][j] * b[j];
        }
        b[i] /= A[i][i];
    }
    return true;
}

}
