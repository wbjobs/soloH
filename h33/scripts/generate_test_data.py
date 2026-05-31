#!/usr/bin/env python3
"""Generate synthetic Gadget-2 format snapshots for testing.

Creates multiple snapshots with halos that merge over time,
to test the halo finder and merger tree builder.
"""

import numpy as np
import struct
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def write_gadget_header(f, npart, massarr, redshift, box_size, time):
    header_format = (
        '6I'    # npart[6]
        '6d'    # massarr[6]
        'd'     # time
        'd'     # redshift
        '2i'    # flag_sfr, flag_feedback
        '6I'    # npartTotal[6]
        '2i'    # flag_cooling, num_files
        '4d'    # BoxSize, Omega0, OmegaLambda, HubbleParam
        '2i'    # flag_stellarage, flag_metals
        '6I'    # npartTotalHighWord[6]
        'i'     # flag_entropy_instead_u
        '60s'   # fill
    )

    header_data = struct.pack(
        header_format,
        *npart,
        *massarr,
        time,
        redshift,
        0, 0,
        *npart,
        0, 1,
        box_size, 0.3, 0.7, 0.7,
        0, 0,
        *([0]*6),
        0,
        b'\x00' * 60
    )

    header_size = struct.calcsize(header_format)
    f.write(struct.pack('i', header_size))
    f.write(header_data)
    f.write(struct.pack('i', header_size))


def write_block(f, data):
    data_bytes = data.tobytes()
    size = len(data_bytes)
    f.write(struct.pack('i', size))
    f.write(data_bytes)
    f.write(struct.pack('i', size))


def generate_halo_particles(center, n_particles, mass, velocity, r_vir, box_size, rng):
    positions = rng.normal(center, r_vir * 0.5, (n_particles, 3))
    for i in range(3):
        positions[:, i] = np.mod(positions[:, i], box_size)

    velocities = rng.normal(velocity, 10.0, (n_particles, 3))

    masses = np.full(n_particles, mass, dtype=np.float32)

    return positions, velocities, masses


def generate_snapshot(output_file, redshift, n_halos, n_particles_per_halo,
                       box_size, particle_mass, halo_centers, halo_velocities,
                       halo_masses, halo_r_virs, rng, merge_events=None):
    if merge_events is None:
        merge_events = []

    total_particles = n_halos * n_particles_per_halo
    all_positions = np.zeros((total_particles, 3), dtype=np.float32)
    all_velocities = np.zeros((total_particles, 3), dtype=np.float32)
    all_masses = np.zeros(total_particles, dtype=np.float32)
    all_ids = np.arange(1, total_particles + 1, dtype=np.uint32)

    for i in range(n_halos):
        n_p = n_particles_per_halo
        start = i * n_particles_per_halo
        end = start + n_p

        pos, vel, masses = generate_halo_particles(
            halo_centers[i], n_p, particle_mass, halo_velocities[i],
            halo_r_virs[i], box_size, rng
        )

        all_positions[start:end] = pos
        all_velocities[start:end] = vel
        all_masses[start:end] = masses

    for target_idx, source_indices in merge_events.items():
        for source_idx in source_indices:
            n_p = n_particles_per_halo
            start = source_idx * n_particles_per_halo
            end = start + n_p

            displacement = halo_centers[target_idx] - halo_centers[source_idx]
            for k in range(3):
                displacement[k] -= box_size * np.round(displacement[k] / box_size)

            all_positions[start:end] = np.mod(
                all_positions[start:end] + displacement * 0.8,
                box_size
            )
            all_velocities[start:end] = halo_velocities[target_idx] + rng.normal(0, 5.0, (n_p, 3))

    with open(output_file, 'wb') as f:
        npart = [0, total_particles, 0, 0, 0, 0]
        massarr = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        time = 1.0 / (1.0 + redshift)

        write_gadget_header(f, npart, massarr, redshift, box_size, time)
        write_block(f, all_positions.astype(np.float32))
        write_block(f, all_velocities.astype(np.float32))
        write_block(f, all_ids)
        write_block(f, all_masses.astype(np.float32))


def evolve_halos(halo_centers, halo_velocities, box_size, dt, rng):
    for i in range(len(halo_centers)):
        halo_centers[i] = np.mod(
            halo_centers[i] + halo_velocities[i] * dt,
            box_size
        )
        halo_velocities[i] += rng.normal(0, 0.5, 3)


def main():
    parser = argparse.ArgumentParser(description='Generate synthetic Gadget-2 test snapshots')
    parser.add_argument('--output-dir', '-o', default='test_snapshots',
                       help='Output directory for snapshots')
    parser.add_argument('--n-snapshots', type=int, default=5,
                       help='Number of snapshots to generate')
    parser.add_argument('--n-halos', type=int, default=3,
                       help='Number of initial halos')
    parser.add_argument('--n-particles', type=int, default=100,
                       help='Particles per halo')
    parser.add_argument('--box-size', type=float, default=100.0,
                       help='Simulation box size (Mpc/h)')
    parser.add_argument('--particle-mass', type=float, default=1e10,
                       help='Particle mass (Msun/h)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed')
    parser.add_argument('--redshift-start', type=float, default=5.0,
                       help='Starting redshift')
    parser.add_argument('--redshift-end', type=float, default=0.0,
                       help='Ending redshift')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    rng = np.random.default_rng(args.seed)

    halo_centers = [rng.uniform(0, args.box_size, 3) for _ in range(args.n_halos)]
    halo_velocities = [rng.uniform(-5, 5, 3) for _ in range(args.n_halos)]
    halo_r_virs = [rng.uniform(3, 8) for _ in range(args.n_halos)]
    halo_masses = [args.n_particles * args.particle_mass for _ in range(args.n_halos)]

    redshifts = np.linspace(args.redshift_start, args.redshift_end, args.n_snapshots)

    merge_events = [{} for _ in range(args.n_snapshots)]
    if args.n_snapshots >= 3 and args.n_halos >= 2:
        merge_events[args.n_snapshots // 2] = {0: [1]}

    for snap_idx in range(args.n_snapshots):
        z = redshifts[snap_idx]

        if snap_idx > 0:
            evolve_halos(halo_centers, halo_velocities, args.box_size, 0.5, rng)

        output_file = os.path.join(args.output_dir, f'snapshot_{snap_idx:03d}.dat')

        generate_snapshot(
            output_file, z, args.n_halos, args.n_particles,
            args.box_size, args.particle_mass,
            halo_centers, halo_velocities, halo_masses, halo_r_virs,
            rng, merge_events[snap_idx]
        )

        print(f"Generated {output_file}: z={z:.2f}, "
              f"{args.n_halos * args.n_particles} particles")

    print(f"\nGenerated {args.n_snapshots} snapshots in {args.output_dir}/")
    print("\nTo run analysis:")
    print(f"  python python/halo_analysis/cli.py run "
          f"--input '{args.output_dir}/snapshot_*.dat' "
          f"--output test_results "
          f"--plot-merger-tree --print-stats --verbose")


if __name__ == '__main__':
    main()
