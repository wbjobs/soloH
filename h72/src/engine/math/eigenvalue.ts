import { Matrix } from './matrix';

export interface EigenResult {
  eigenvalues: number[];
  eigenvectors: number[][];
}

export function qrAlgorithm(
  matrix: Matrix,
  maxIterations: number = 100,
  tolerance: number = 1e-10
): EigenResult {
  const n = matrix.rows;
  let A = matrix.clone();
  const QTotal = Matrix.identity(n);

  for (let iter = 0; iter < maxIterations; iter++) {
    const { Q, R } = qrDecomposition(A);
    
    A = R.multiplyMatrix(Q);
    QTotal.multiplyMatrix(Q);

    let converged = true;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        if (i !== j && Math.abs(A.get(i, j)) > tolerance) {
          converged = false;
          break;
        }
      }
      if (!converged) break;
    }

    if (converged) break;
  }

  const eigenvalues: number[] = [];
  for (let i = 0; i < n; i++) {
    eigenvalues.push(A.get(i, i));
  }

  const sortedIndices = eigenvalues
    .map((val, idx) => ({ val, idx }))
    .sort((a, b) => a.val - b.val)
    .map(item => item.idx);

  const sortedEigenvalues = sortedIndices.map(i => eigenvalues[i]);
  const sortedEigenvectors: number[][] = [];

  for (const idx of sortedIndices) {
    const eigenvector: number[] = [];
    for (let i = 0; i < n; i++) {
      eigenvector.push(QTotal.get(i, idx));
    }
    sortedEigenvectors.push(eigenvector);
  }

  return {
    eigenvalues: sortedEigenvalues,
    eigenvectors: sortedEigenvectors,
  };
}

export function qrDecomposition(A: Matrix): { Q: Matrix; R: Matrix } {
  const n = A.rows;
  let Q = Matrix.identity(n);
  let R = A.clone();

  for (let k = 0; k < n - 1; k++) {
    const alpha = R.get(k, k);
    let sigma = 0;
    for (let i = k + 1; i < n; i++) {
      sigma += R.get(i, k) * R.get(i, k);
    }
    
    if (Math.abs(sigma) < 1e-15) continue;
    
    const sign = alpha >= 0 ? 1 : -1;
    const v = new Float64Array(n - k);
    const s = Math.sqrt(alpha * alpha + sigma);
    v[0] = alpha + sign * s;
    
    for (let i = 1; i < n - k; i++) {
      v[i] = R.get(k + i, k);
    }
    
    const vNorm = Math.sqrt(v[0] * v[0] + sigma);
    for (let i = 0; i < n - k; i++) {
      v[i] /= vNorm;
    }

    const H = Matrix.identity(n);
    for (let i = 0; i < n - k; i++) {
      for (let j = 0; j < n - k; j++) {
        H.set(k + i, k + j, (i === j ? 1 : 0) - 2 * v[i] * v[j]);
      }
    }

    R = H.multiplyMatrix(R);
    Q = Q.multiplyMatrix(H);
  }

  return { Q, R };
}

export function jacobiMethod(
  matrix: Matrix,
  maxIterations: number = 100,
  tolerance: number = 1e-10
): EigenResult {
  const n = matrix.rows;
  let A = matrix.clone();
  const V = Matrix.identity(n);

  for (let iter = 0; iter < maxIterations; iter++) {
    let maxOffDiag = 0;
    let p = 0;
    let q = 0;

    for (let i = 0; i < n - 1; i++) {
      for (let j = i + 1; j < n; j++) {
        const absVal = Math.abs(A.get(i, j));
        if (absVal > maxOffDiag) {
          maxOffDiag = absVal;
          p = i;
          q = j;
        }
      }
    }

    if (maxOffDiag < tolerance) break;

    const app = A.get(p, p);
    const aqq = A.get(q, q);
    const apq = A.get(p, q);

    const theta = (aqq - app) / (2 * apq);
    const t = theta >= 0 
      ? 1 / (theta + Math.sqrt(theta * theta + 1))
      : 1 / (theta - Math.sqrt(theta * theta + 1));
    const c = 1 / Math.sqrt(1 + t * t);
    const s = t * c;

    const J = Matrix.identity(n);
    J.set(p, p, c);
    J.set(q, q, c);
    J.set(p, q, s);
    J.set(q, p, -s);

    A = J.transpose().multiplyMatrix(A).multiplyMatrix(J);
    V.multiplyMatrix(J);
  }

  const eigenvalues: number[] = [];
  for (let i = 0; i < n; i++) {
    eigenvalues.push(A.get(i, i));
  }

  const sortedIndices = eigenvalues
    .map((val, idx) => ({ val, idx }))
    .sort((a, b) => a.val - b.val)
    .map(item => item.idx);

  const sortedEigenvalues = sortedIndices.map(i => eigenvalues[i]);
  const sortedEigenvectors: number[][] = [];

  for (const idx of sortedIndices) {
    const eigenvector: number[] = [];
    for (let i = 0; i < n; i++) {
      eigenvector.push(V.get(i, idx));
    }
    sortedEigenvectors.push(eigenvector);
  }

  return {
    eigenvalues: sortedEigenvalues,
    eigenvectors: sortedEigenvectors,
  };
}

export function solveTridiagonalEigen(
  diagonal: Float64Array,
  offDiagonal: Float64Array,
  numEigenvalues: number = 10
): EigenResult {
  const n = diagonal.length;
  const H = new Matrix(n, n);

  for (let i = 0; i < n; i++) {
    H.set(i, i, diagonal[i]);
    if (i < n - 1) {
      H.set(i, i + 1, offDiagonal[i]);
      H.set(i + 1, i, offDiagonal[i]);
    }
  }

  return jacobiMethod(H, 100, 1e-12);
}
