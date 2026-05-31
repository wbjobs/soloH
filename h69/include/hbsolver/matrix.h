#ifndef HBSOLVER_MATRIX_H
#define HBSOLVER_MATRIX_H

#include "hbsolver/types.h"
#include <stdexcept>

namespace hbsolver {

class MatrixOps {
public:
    static ComplexMat multiply(const ComplexMat& A, const ComplexMat& B);
    static ComplexVec multiply(const ComplexMat& A, const ComplexVec& x);
    static ComplexMat multiply(const ComplexMat& A, double s);
    static ComplexMat add(const ComplexMat& A, const ComplexMat& B);
    static ComplexMat subtract(const ComplexMat& A, const ComplexMat& B);
    static ComplexMat transpose(const ComplexMat& A);
    static ComplexMat conjugate(const ComplexMat& A);
    static ComplexMat identity(int n);
    static ComplexMat zeros(int rows, int cols);

    static bool solveLinearSystem(const ComplexMat& A, const ComplexVec& b, ComplexVec& x);
    static bool gaussElimination(ComplexMat& A, ComplexVec& b);

    static double norm(const ComplexVec& v);
    static double dotProduct(const ComplexVec& a, const ComplexVec& b);

private:
    static bool luDecomposition(const ComplexMat& A, ComplexMat& L, ComplexMat& U, IntVec& pivot);
    static void forwardSubstitution(const ComplexMat& L, const ComplexVec& b, ComplexVec& y, const IntVec& pivot);
    static void backwardSubstitution(const ComplexMat& U, const ComplexVec& y, ComplexVec& x);
};

}

#endif
