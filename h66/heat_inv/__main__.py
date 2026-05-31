"""
Main application entry point for heat inversion solver.
"""

import os
import sys
import argparse
import yaml
import numpy as np

from heat_inv.cli import solve_inverse_problem, load_config, setup_output_dir


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description='Thermal Conductivity Inverse Problem Solver',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with a configuration file
  python -m heat_inv config.yaml

  # Generate an example configuration
  heat-inv generate-config

  # Check configuration
  heat-inv check config.yaml
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    run_parser = subparsers.add_parser('run', help='Run inverse problem')
    run_parser.add_argument('config', help='Configuration file (YAML)')
    run_parser.add_argument('--output', '-o', help='Override output directory')

    gen_parser = subparsers.add_parser('generate-config', help='Generate example config')
    gen_parser.add_argument('--output', '-o', default='config.yaml',
                           help='Output file name')

    check_parser = subparsers.add_parser('check', help='Check configuration')
    check_parser.add_argument('config', help='Configuration file (YAML)')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == 'generate-config':
        from heat_inv.cli import cli as heat_cli
        sys.argv = ['heat-inv', 'generate-config', '--output', args.output]
        heat_cli()
        return

    if args.command in ['run', 'check']:
        if not os.path.exists(args.config):
            print(f"Error: Configuration file not found: {args.config}")
            sys.exit(1)

        config = load_config(args.config)

        if args.output:
            config['output'] = config.get('output', {})
            config['output']['directory'] = args.output

        if args.command == 'check':
            config['check_gradient'] = True
            config['optimization']['max_iter'] = 1

        output_dir = setup_output_dir(config)

        try:
            results = solve_inverse_problem(config, output_dir)
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            print(f"Optimal J: {results['result'].J_opt:.6e}")
            print(f"Iterations: {results['result'].n_iter}")
            print(f"Converged: {results['result'].converged}")
            print(f"Output directory: {output_dir}")
            print("=" * 60)

            if results['sigma'] is not None:
                sigma_vec = results['sigma'].vector().get_local()
                print(f"\nUncertainty Statistics:")
                print(f"  Mean σ: {np.mean(sigma_vec):.4f}")
                print(f"  Max σ:  {np.max(sigma_vec):.4f}")
                print(f"  Min σ:  {np.min(sigma_vec):.4f}")

            return results

        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    main()
