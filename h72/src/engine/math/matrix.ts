export class Matrix {
  private data: Float64Array;
  readonly rows: number;
  readonly cols: number;

  constructor(rows: number, cols: number, initialValue: number = 0) {
    this.rows = rows;
    this.cols = cols;
    this.data = new Float64Array(rows * cols).fill(initialValue);
  }

  static fromArray(arr: number[][]): Matrix {
    const rows = arr.length;
    const cols = arr[0].length;
    const mat = new Matrix(rows, cols);
    for (let i = 0; i < rows; i++) {
      for (let j = 0; j < cols; j++) {
        mat.set(i, j, arr[i][j]);
      }
    }
    return mat;
  }

  static identity(size: number): Matrix {
    const mat = new Matrix(size, size);
    for (let i = 0; i < size; i++) {
      mat.set(i, i, 1);
    }
    return mat;
  }

  get(i: number, j: number): number {
    return this.data[i * this.cols + j];
  }

  set(i: number, j: number, value: number): void {
    this.data[i * this.cols + j] = value;
  }

  add(mat: Matrix): Matrix {
    if (this.rows !== mat.rows || this.cols !== mat.cols) {
      throw new Error('Matrix dimensions must match for addition');
    }
    const result = new Matrix(this.rows, this.cols);
    for (let i = 0; i < this.data.length; i++) {
      result.data[i] = this.data[i] + mat.data[i];
    }
    return result;
  }

  subtract(mat: Matrix): Matrix {
    if (this.rows !== mat.rows || this.cols !== mat.cols) {
      throw new Error('Matrix dimensions must match for subtraction');
    }
    const result = new Matrix(this.rows, this.cols);
    for (let i = 0; i < this.data.length; i++) {
      result.data[i] = this.data[i] - mat.data[i];
    }
    return result;
  }

  multiply(scalar: number): Matrix {
    const result = new Matrix(this.rows, this.cols);
    for (let i = 0; i < this.data.length; i++) {
      result.data[i] = this.data[i] * scalar;
    }
    return result;
  }

  multiplyMatrix(mat: Matrix): Matrix {
    if (this.cols !== mat.rows) {
      throw new Error('Matrix dimensions incompatible for multiplication');
    }
    const result = new Matrix(this.rows, mat.cols);
    for (let i = 0; i < this.rows; i++) {
      for (let j = 0; j < mat.cols; j++) {
        let sum = 0;
        for (let k = 0; k < this.cols; k++) {
          sum += this.get(i, k) * mat.get(k, j);
        }
        result.set(i, j, sum);
      }
    }
    return result;
  }

  multiplyVector(vec: Float64Array): Float64Array {
    if (this.cols !== vec.length) {
      throw new Error('Matrix and vector dimensions incompatible');
    }
    const result = new Float64Array(this.rows);
    for (let i = 0; i < this.rows; i++) {
      let sum = 0;
      for (let j = 0; j < this.cols; j++) {
        sum += this.get(i, j) * vec[j];
      }
      result[i] = sum;
    }
    return result;
  }

  transpose(): Matrix {
    const result = new Matrix(this.cols, this.rows);
    for (let i = 0; i < this.rows; i++) {
      for (let j = 0; j < this.cols; j++) {
        result.set(j, i, this.get(i, j));
      }
    }
    return result;
  }

  clone(): Matrix {
    const mat = new Matrix(this.rows, this.cols);
    mat.data.set(this.data);
    return mat;
  }

  toArray(): number[][] {
    const arr: number[][] = [];
    for (let i = 0; i < this.rows; i++) {
      const row: number[] = [];
      for (let j = 0; j < this.cols; j++) {
        row.push(this.get(i, j));
      }
      arr.push(row);
    }
    return arr;
  }
}

export function solveTridiagonal(
  a: Float64Array,
  b: Float64Array,
  c: Float64Array,
  d: Float64Array
): Float64Array {
  const n = b.length;
  const x = new Float64Array(n);
  const cPrime = new Float64Array(n);
  const dPrime = new Float64Array(n);

  cPrime[0] = c[0] / b[0];
  dPrime[0] = d[0] / b[0];

  for (let i = 1; i < n; i++) {
    const m = b[i] - a[i] * cPrime[i - 1];
    cPrime[i] = c[i] / m;
    dPrime[i] = (d[i] - a[i] * dPrime[i - 1]) / m;
  }

  x[n - 1] = dPrime[n - 1];
  for (let i = n - 2; i >= 0; i--) {
    x[i] = dPrime[i] - cPrime[i] * x[i + 1];
  }

  return x;
}

export function linspace(start: number, end: number, num: number): Float64Array {
  const result = new Float64Array(num);
  const step = (end - start) / (num - 1);
  for (let i = 0; i < num; i++) {
    result[i] = start + i * step;
  }
  return result;
}

export function trapz(y: Float64Array, x: Float64Array): number {
  let sum = 0;
  for (let i = 1; i < x.length; i++) {
    sum += (y[i] + y[i - 1]) * (x[i] - x[i - 1]) / 2;
  }
  return sum;
}

export function normalize(vector: Float64Array, dx: number): Float64Array {
  const squared = new Float64Array(vector.length);
  for (let i = 0; i < vector.length; i++) {
    squared[i] = vector[i] * vector[i];
  }
  const norm = Math.sqrt(trapz(squared, linspace(0, dx * (vector.length - 1), vector.length)));
  const result = new Float64Array(vector.length);
  for (let i = 0; i < vector.length; i++) {
    result[i] = vector[i] / norm;
  }
  return result;
}
