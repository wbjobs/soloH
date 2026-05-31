# Halo Analysis Tool - C++ + Python Hybrid

A comprehensive tool for analyzing cosmological N-body simulation snapshots, featuring:
- Gadget-2 format snapshot reading
- Friends-of-Friends (FoF) halo finding
- Merger tree construction across multiple snapshots
- Subhalo identification
- Spin parameter and formation redshift calculation
- Mass function computation
- Graphviz merger tree visualization
- Mass and redshift range filtering

## Project Structure

```
h33/
├── cpp/                          # C++ core implementation
│   ├── include/
│   │   ├── common.hpp           # Common types and utilities
│   │   ├── gadget_reader.hpp    # Gadget-2 format reader
│   │   ├── fof.hpp              # Friends-of-Friends halo finder
│   │   └── merger_tree.hpp      # Merger tree builder
│   ├── src/
│   │   ├── gadget_reader.cpp
│   │   ├── fof.cpp
│   │   ├── merger_tree.cpp
│   │   └── pybindings.cpp       # pybind11 bindings
│   └── CMakeLists.txt
├── python/
│   └── halo_analysis/           # Python package
│       ├── __init__.py
│       ├── core.py              # Numba JIT fallback implementation
│       ├── analysis.py          # Analysis functions (mass function, etc.)
│       ├── visualization.py     # Graphviz and matplotlib visualization
│       └── cli.py               # Command-line interface
├── scripts/
│   ├── generate_test_data.py    # Synthetic Gadget-2 snapshot generator
│   └── run_pipeline.py          # End-to-end test script
├── CMakeLists.txt               # Top-level CMake build file
└── README.md
```

## Key Features

### 1. Gadget-2 Snapshot Reader
- Reads standard Gadget-2 binary format with block markers
- Supports both 32-bit and 64-bit particle IDs
- Handles variable mass particles
- Reads positions, velocities, IDs, and masses

### 2. Friends-of-Friends (FoF) Halo Finder
- Spatial hash grid for efficient neighbor searching
- Link length = 0.2 × mean inter-particle spacing (default, configurable)
- Union-Find data structure for group membership
- Computes halo properties:
  - Mass
  - Center of mass
  - Mean velocity
  - Velocity dispersion
  - Spin parameter (λ = L / (√2 M σ R_vir))
  - Virial radius

### 3. Merger Tree Construction
- Tracks halos across snapshots using particle sharing ratio
- Links halos if >50% of particles are shared (configurable)
- Builds directed acyclic graph of mergers
- Computes formation redshift (when halo reaches 50% of final mass)

### 4. Subhalo Identification
- Identifies subhalos within larger halos
- Based on mass ratio (<10% of host, configurable) and proximity (<2 R_vir)

### 5. Analysis Functions
- **Halo mass function**: dn/dlogM vs. M
- **Subhalo mass function**
- **Spin parameter distribution**
- **Formation redshift distribution**
- **Merger history tracing** for individual halos

### 6. Visualization
- **Merger tree**: Directed graph using Graphviz
  - Nodes show halo ID, mass, redshift, spin, formation redshift
  - Solid arrows: progenitor → descendant
  - Dashed arrows: subhalo → host
  - Color-coded by mass
  - Grouped by snapshot
- **Mass function**: Log-log plot
- **Spin distribution**: Histogram and binned distribution
- **Formation redshift**: Histogram with statistics

### 7. Filtering
- Mass range filtering (--min-mass, --max-mass)
- Redshift range filtering (--min-redshift, --max-redshift)

## Installation & Building

### Prerequisites

**Python packages** (already installed):
```bash
pip install numpy numba h5py graphviz pydot pybind11 matplotlib
```

**System tools**:
- C++17 compiler (g++, clang++, or MSVC)
- CMake 3.15+
- Graphviz (for visualization)

### Building the C++ Extension

```bash
mkdir build && cd build
cmake ..
cmake --build . --config Release
```

This will build the `halo_analysis_cpp` Python extension module and place it in
`python/halo_analysis/`.

**If no C++ compiler is available**, the tool will automatically fall back to
the Numba JIT Python implementation, which provides comparable performance.

## Usage

### Quick Start

```bash
# 1. Generate test data
python scripts/generate_test_data.py --output-dir test_snapshots --n-snapshots 5

# 2. Run full analysis pipeline
python python/halo_analysis/cli.py run \
    --input "test_snapshots/*.dat" \
    --output results \
    --plot-merger-tree \
    --plot-summary \
    --print-stats \
    --verbose
```

### Command-Line Interface

```bash
# Show help
python python/halo_analysis/cli.py --help

# Show tool info
python python/halo_analysis/cli.py info

# Basic analysis
python python/halo_analysis/cli.py run \
    --input "snapshots/*.dat" \
    --output results

# With filtering
python python/halo_analysis/cli.py run \
    --input "snapshots/*.dat" \
    --output results \
    --min-mass 1e12 \
    --max-mass 1e15 \
    --min-redshift 0 \
    --max-redshift 5

# Analyze specific halo
python python/halo_analysis/cli.py run \
    --input "snapshots/*.dat" \
    --output results \
    --halo-id 12345 \
    --plot-merger-tree \
    --print-stats

# Custom FoF parameters
python python/halo_analysis/cli.py run \
    --input "snapshots/*.dat" \
    --output results \
    --link-length 0.2 \
    --min-particles 30 \
    --share-threshold 0.5
```

### Python API

```python
import sys
sys.path.insert(0, 'python')

import halo_analysis as ha
from halo_analysis.core import Snapshot
from halo_analysis.analysis import (
    get_merger_history, save_halo_catalog, compute_mass_function
)
from halo_analysis.visualization import (
    save_merger_tree_graphviz, plot_mass_function
)

# Check implementation
print(f"Using {'C++' if ha.CPP_AVAILABLE else 'Python/Numba'} implementation")

# Read snapshots
reader = ha.GadgetReader()
snapshots = []
for i, fname in enumerate(sorted(glob.glob("snapshots/*.dat"))):
    snap = Snapshot()
    reader.read(fname, snap, i)
    snapshots.append(snap)

# Find halos with FoF
fof = ha.FoFFinder(link_length_ratio=0.2, min_particles=20)
for snap in snapshots:
    fof.find_halos(snap)

# Build merger trees
builder = ha.MergerTreeBuilder(particle_share_threshold=0.5)
builder.build_trees(snapshots)
builder.compute_formation_redshifts(snapshots)
builder.identify_subhalos(snapshots)

# Analyze
all_halos = [h for s in snapshots for h in s.halos]
bin_centers, mass_func, counts = compute_mass_function(
    all_halos, snapshots[0].box_size
)

# Get merger history for a specific halo
target_halo = all_halos[-1]
history = get_merger_history(target_halo.halo_id, builder, snapshots)

# Save results
save_halo_catalog(snapshots, builder, "halo_catalog.json")

# Visualize
save_merger_tree_graphviz(builder, "merger_tree", format="png")
plot_mass_function(all_halos, snapshots[0].box_size, "mass_function.png")
```

## Output Files

When running the CLI, the following files are generated in the output directory:

- `halo_catalog.json` - Complete halo catalog with all properties
- `merger_history_{id}.json` - Detailed merger history for specified halo
- `merger_tree.{png,pdf,svg}` - Merger tree visualization
- `plots/` - Summary plots:
  - `mass_function.png` - Halo mass function
  - `spin_distribution.png` - Spin parameter distribution
  - `formation_redshift.png` - Formation redshift distribution

## Running Tests

```bash
# Run full end-to-end test suite
python scripts/run_pipeline.py
```

This will:
1. Test Python imports
2. Verify core functions
3. Generate synthetic test data
4. Run the full analysis pipeline
5. Test the CLI
6. Verify all outputs

## Algorithm Details

### Friends-of-Friends Algorithm
1. Compute mean inter-particle spacing: `d_mean = L / N^(1/3)`
2. Set linking length: `b = 0.2 * d_mean`
3. Build spatial hash grid with cell size = b
4. For each particle, check distance to particles in 3×3×3 neighboring cells
5. Union-Find to group linked particles
6. Groups with ≥20 particles are halos

### Merger Tree Construction
1. Sort snapshots by redshift (high → low)
2. For each halo at redshift z, find the halo at z-Δz with the highest
   particle sharing ratio
3. Link if sharing ratio > 50%
4. Formation redshift = redshift when halo first reaches 50% of its final mass

### Spin Parameter
λ = |L| / (√2 * M * σ * R_vir)
- L = total angular momentum
- M = total mass
- σ = velocity dispersion
- R_vir = virial radius (Δ=200 overdensity)

## Performance

- **C++**: Fastest, recommended for large simulations (>1M particles)
- **Numba JIT**: ~50-80% of C++ speed, no compilation needed
- **Pure Python**: For testing/debugging only

## Dependencies

- C++17 compiler (optional, for C++ extension)
- CMake 3.15+ (optional, for building)
- Python 3.8+
- numpy
- numba
- h5py
- graphviz (Python package + system Graphviz)
- pydot
- pybind11 (optional, for C++ bindings)
- matplotlib (optional, for plotting)

## License

MIT License

## References

1. Davis et al. (1985) - FoF algorithm
2. Springel et al. (2001) - Gadget-2 code
3. Bullock et al. (2001) - Spin parameter statistics
4. Fakhouri et al. (2010) - Merger tree algorithms
