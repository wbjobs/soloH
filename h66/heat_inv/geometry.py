"""
Geometry handling module for STL import and mesh generation.
"""

import os
import numpy as np
import trimesh
from dolfin import *
import meshio


class GeometryHandler:
    """Handles STL geometry import and FEniCS mesh generation."""

    def __init__(self, stl_file=None, mesh_file=None, mesh_resolution=1.0):
        """
        Initialize geometry handler.

        Parameters
        ----------
        stl_file : str, optional
            Path to STL file
        mesh_file : str, optional
            Path to existing mesh file (XDmf or XML)
        mesh_resolution : float, optional
            Mesh resolution parameter
        """
        self.stl_file = stl_file
        self.mesh_file = mesh_file
        self.mesh_resolution = mesh_resolution
        self.mesh = None
        self.boundary_mesh = None
        self.subdomains = None
        self.boundaries = None

    def load_stl(self, stl_file=None):
        """
        Load STL file and inspect geometry.

        Parameters
        ----------
        stl_file : str, optional
            Path to STL file

        Returns
        -------
        trimesh.Trimesh
            Loaded mesh object
        """
        if stl_file is not None:
            self.stl_file = stl_file
        if self.stl_file is None:
            raise ValueError("STL file path not provided")

        print(f"Loading STL file: {self.stl_file}")
        mesh = trimesh.load(self.stl_file)
        print(f"STL mesh loaded: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
        print(f"Bounding box: {mesh.bounds}")

        return mesh

    def create_box_mesh(self, nx=20, ny=20, nz=1, length=1.0, width=1.0, height=0.1):
        """
        Create a simple box mesh for testing without STL.

        Parameters
        ----------
        nx, ny, nz : int
            Number of elements in each direction
        length, width, height : float
            Dimensions of the box

        Returns
        -------
        dolfin.Mesh
            Generated FEniCS mesh
        """
        print(f"Creating box mesh: {length}x{width}x{height}, {nx}x{ny}x{nz} elements")

        if nz > 1:
            self.mesh = BoxMesh(Point(0, 0, 0), Point(length, width, height), nx, ny, nz)
        else:
            self.mesh = RectangleMesh(Point(0, 0), Point(length, width), nx, ny)

        self._setup_boundaries()
        return self.mesh

    def generate_mesh_from_stl(self, output_dir="output", max_cell_size=None):
        """
        Generate volumetric mesh from STL using gmsh.

        Parameters
        ----------
        output_dir : str
            Directory to save mesh files
        max_cell_size : float, optional
            Maximum cell size for mesh generation

        Returns
        -------
        dolfin.Mesh
            Generated FEniCS mesh
        """
        import subprocess
        import tempfile

        if max_cell_size is None:
            max_cell_size = self.mesh_resolution

        stl_mesh = self.load_stl()
        os.makedirs(output_dir, exist_ok=True)

        geo_file = os.path.join(output_dir, "geometry.geo")
        msh_file = os.path.join(output_dir, "mesh.msh")
        xdmf_file = os.path.join(output_dir, "mesh.xdmf")

        bounds = stl_mesh.bounds
        center = np.mean(bounds, axis=0)
        scale = np.max(bounds[1] - bounds[0])

        with open(geo_file, "w") as f:
            f.write(f'Merge "{os.path.abspath(self.stl_file)}";\n')
            f.write("Surface Loop(1) = {1};\n")
            f.write("Volume(1) = {1};\n")
            f.write(f"Characteristic Length {{1}} = {max_cell_size};\n")

        print(f"Generating mesh with gmsh, max cell size: {max_cell_size}")
        subprocess.run(["gmsh", "-3", geo_file, "-o", msh_file], check=True)

        msh = meshio.read(msh_file)
        tetra_cells = None
        for cell_block in msh.cells:
            if cell_block.type == "tetra":
                tetra_cells = cell_block
                break

        if tetra_cells is None:
            raise ValueError("No tetrahedral cells found in mesh")

        tetra_mesh = meshio.Mesh(
            points=msh.points,
            cells=[("tetra", tetra_cells.data)],
        )
        meshio.write(xdmf_file, tetra_mesh)

        self.mesh = Mesh()
        with XDMFFile(xdmf_file) as f:
            f.read(self.mesh)

        print(f"Mesh generated: {self.mesh.num_vertices()} vertices, {self.mesh.num_cells()} cells")
        self.mesh_file = xdmf_file
        self._setup_boundaries()

        return self.mesh

    def _setup_boundaries(self):
        """Set up boundary markers for the mesh."""
        if self.mesh is None:
            raise ValueError("Mesh not created yet")

        facet_dim = self.mesh.topology().dim() - 1
        self.boundaries = MeshFunction("size_t", self.mesh, facet_dim)
        self.boundaries.set_all(0)

        class AllBoundary(SubDomain):
            def inside(self, x, on_boundary):
                return on_boundary

        AllBoundary().mark(self.boundaries, 1)

        self.ds = Measure("ds", domain=self.mesh, subdomain_data=self.boundaries)
        self.dx = Measure("dx", domain=self.mesh)

    def load_mesh(self, mesh_file=None):
        """
        Load existing mesh from file.

        Parameters
        ----------
        mesh_file : str, optional
            Path to mesh file (XDMF format)

        Returns
        -------
        dolfin.Mesh
            Loaded FEniCS mesh
        """
        if mesh_file is not None:
            self.mesh_file = mesh_file
        if self.mesh_file is None:
            raise ValueError("Mesh file path not provided")

        print(f"Loading mesh from: {self.mesh_file}")
        self.mesh = Mesh()
        with XDMFFile(self.mesh_file) as f:
            f.read(self.mesh)

        print(f"Mesh loaded: {self.mesh.num_vertices()} vertices, {self.mesh.num_cells()} cells")
        self._setup_boundaries()

        return self.mesh

    def get_function_space(self, degree=1, family="CG"):
        """
        Create function space on the mesh.

        Parameters
        ----------
        degree : int
            Polynomial degree
        family : str
            Finite element family

        Returns
        -------
        dolfin.FunctionSpace
            Function space
        """
        if self.mesh is None:
            raise ValueError("Mesh not created yet")

        return FunctionSpace(self.mesh, family, degree)

    def get_vector_function_space(self, degree=1, family="CG"):
        """
        Create vector function space for gradient fields.

        Parameters
        ----------
        degree : int
            Polynomial degree
        family : str
            Finite element family

        Returns
        -------
        dolfin.VectorFunctionSpace
            Vector function space
        """
        if self.mesh is None:
            raise ValueError("Mesh not created yet")

        return VectorFunctionSpace(self.mesh, family, degree)

    def save_mesh(self, output_file):
        """
        Save mesh to XDMF file.

        Parameters
        ----------
        output_file : str
            Output file path
        """
        if self.mesh is None:
            raise ValueError("No mesh to save")

        with XDMFFile(output_file) as f:
            f.write(self.mesh)
        print(f"Mesh saved to: {output_file}")
