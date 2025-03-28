#!/usr/bin/env python
"""
Compare linear and Hermite interpolation methods for streamlines.

This script loads test streamlines and processes them with both
linear and Hermite interpolation methods, then compares the results
visually and quantitatively.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import nibabel as nib
from densify import densify_streamline_subvoxel, calculate_streamline_metrics
import argparse


def process_streamlines_with_method(streamlines, step_size, method, voxel_size=1.0, use_gpu=False):
    """
    Processing a set of streamlines with a specific interpolation method.

    Parameters
    ----------
    streamlines : list
        List of streamlines to process.
    step_size : float
        Step size for streamline densification.
    method : str
        Interpolation method ('linear' or 'hermite').
    voxel_size : float, optional
        Voxel size for scaling, by default 1.0.
    use_gpu : bool, optional
        Whether using GPU acceleration, by default False.

    Returns
    -------
    list
        List of processed streamlines.
    """
    print(f"Processing {len(streamlines)} streamlines with {method} interpolation (voxel size: {voxel_size}mm)...")
    processed = []
    for idx, stream in enumerate(streamlines):
        if idx % 50 == 0:
            print(f"Processing streamline {idx}/{len(streamlines)}...")
        try:
            # Enable detailed debugging for the first few streamlines
            os.environ["DEBUG_TANGENTS"] = "1" if idx < 5 else "0"

            # Scale step size based on voxel size
            scaled_step_size = step_size * (voxel_size / 1.0)
            if idx < 5:
                print(
                    f"Using scaled step size: {scaled_step_size}mm (original: {step_size}mm) for voxel size {voxel_size}mm")

            densified = densify_streamline_subvoxel(
                stream, scaled_step_size, use_gpu=use_gpu, interp_method=method, voxel_size=voxel_size
            )
            processed.append(densified)
        except Exception as e:
            print(f"Error processing streamline {idx}: {e}")
    print(f"Processed {len(processed)}/{len(streamlines)} streamlines with {method} interpolation.")
    return processed


def calculate_metrics_for_both_methods(linear_streams, hermite_streams):
    """
    Calculating metrics for both sets of processed streamlines.

    Parameters
    ----------
    linear_streams : list
        Streamlines processed with linear interpolation.
    hermite_streams : list
        Streamlines processed with Hermite interpolation.

    Returns
    -------
    tuple
        Metrics for linear and Hermite interpolation respectively.
    """
    print("Calculating metrics for linear interpolation...")
    linear_metrics = calculate_streamline_metrics(linear_streams)
    print("Calculating metrics for Hermite interpolation...")
    hermite_metrics = calculate_streamline_metrics(hermite_streams)
    return linear_metrics, hermite_metrics


def compare_metrics(linear_metrics, hermite_metrics):
    """
    Comparing metrics between linear and Hermite interpolation methods.

    Parameters
    ----------
    linear_metrics : dict
        Metrics for linear interpolation.
    hermite_metrics : dict
        Metrics for Hermite interpolation.
    """
    print("\nComparison of Metrics:")

    linear_mean_curv = linear_metrics.get('mean_curvature', 0)
    hermite_mean_curv = hermite_metrics.get('mean_curvature', 0)
    curv_diff = hermite_mean_curv - linear_mean_curv
    curv_pct = (curv_diff / linear_mean_curv * 100) if linear_mean_curv > 0 else 0
    print(
        f"Mean Curvature - Linear: {linear_mean_curv:.6f}, Hermite: {hermite_mean_curv:.6f}, Difference: {curv_diff:.6f} ({curv_pct:.2f}%)")

    linear_max_curv = linear_metrics.get('max_curvature', 0)
    hermite_max_curv = hermite_metrics.get('max_curvature', 0)
    max_curv_diff = hermite_max_curv - linear_max_curv
    max_curv_pct = (max_curv_diff / linear_max_curv * 100) if linear_max_curv > 0 else 0
    print(
        f"Max Curvature - Linear: {linear_max_curv:.6f}, Hermite: {hermite_max_curv:.6f}, Difference: {max_curv_diff:.6f} ({max_curv_pct:.2f}%)")

    linear_mean_len = linear_metrics.get('mean_length', 0)
    hermite_mean_len = hermite_metrics.get('mean_length', 0)
    len_diff = hermite_mean_len - linear_mean_len
    len_pct = (len_diff / linear_mean_len * 100) if linear_mean_len > 0 else 0
    print(
        f"Mean Length - Linear: {linear_mean_len:.6f}, Hermite: {hermite_mean_len:.6f}, Difference: {len_diff:.6f} ({len_pct:.2f}%)")

    linear_total_len = linear_metrics.get('total_length', 0)
    hermite_total_len = hermite_metrics.get('total_length', 0)
    total_len_diff = hermite_total_len - linear_total_len
    total_len_pct = (total_len_diff / linear_total_len * 100) if linear_total_len > 0 else 0
    print(
        f"Total Length - Linear: {linear_total_len:.6f}, Hermite: {hermite_total_len:.6f}, Difference: {total_len_diff:.6f} ({total_len_pct:.2f}%)")

    if 'mean_torsion' in linear_metrics and 'mean_torsion' in hermite_metrics:
        linear_mean_torsion = linear_metrics.get('mean_torsion', 0)
        hermite_mean_torsion = hermite_metrics.get('mean_torsion', 0)
        torsion_diff = hermite_mean_torsion - linear_mean_torsion
        torsion_pct = (torsion_diff / linear_mean_torsion * 100) if linear_mean_torsion > 0 else 0
        print(
            f"Mean Torsion - Linear: {linear_mean_torsion:.6f}, Hermite: {hermite_mean_torsion:.6f}, Difference: {torsion_diff:.6f} ({torsion_pct:.2f}%)")

    print("\nSummary:")
    if abs(curv_pct) > 5:
        print(
            f"Hermite interpolation yields {abs(curv_pct):.1f}% {'higher' if curv_pct > 0 else 'lower'} mean curvature.")
    else:
        print("Curvature differences are minimal.")
    if abs(len_pct) > 5:
        print(
            f"Hermite interpolation yields {abs(len_pct):.1f}% {'longer' if len_pct > 0 else 'shorter'} streamlines on average.")
    else:
        print("Length differences are minimal.")

    print("\nRecommendation:")
    if abs(curv_pct) > 10 or abs(len_pct) > 5:
        if curv_pct > 0:
            print("Hermite interpolation better preserves curvature, which is generally desirable.")
            print("Recommendation: Use Hermite interpolation for improved anatomical accuracy.")
        else:
            print("Hermite interpolation results in less curvature, which is unexpected.")
            print("Recommendation: Verify the Hermite interpolation implementation.")
    else:
        print("Both methods produce similar results; either method should be suitable.")


def visualize_comparison(linear_streams, hermite_streams, max_streamlines=5):
    """
    Visualizing the comparison between linear and Hermite interpolation.

    Parameters
    ----------
    linear_streams : list
        Streamlines processed with linear interpolation.
    hermite_streams : list
        Streamlines processed with Hermite interpolation.
    max_streamlines : int, optional
        Maximum number of streamlines to visualize, by default 5.
    """
    num_streams = min(len(linear_streams), len(hermite_streams), max_streamlines)
    fig = plt.figure(figsize=(15, 10))

    for i in range(num_streams):
        linear_stream = linear_streams[i]
        hermite_stream = hermite_streams[i]
        ax = fig.add_subplot(num_streams, 2, i * 2 + 1, projection='3d')
        ax.set_title(f"Streamline {i + 1} - Linear")
        ax.plot(linear_stream[:, 0], linear_stream[:, 1], linear_stream[:, 2], 'b-')
        ax.scatter(linear_stream[::10, 0], linear_stream[::10, 1], linear_stream[::10, 2], c='r', s=20)
        ax = fig.add_subplot(num_streams, 2, i * 2 + 2, projection='3d')
        ax.set_title(f"Streamline {i + 1} - Hermite")
        ax.plot(hermite_stream[:, 0], hermite_stream[:, 1], hermite_stream[:, 2], 'g-')
        ax.scatter(hermite_stream[::10, 0], hermite_stream[::10, 1], hermite_stream[::10, 2], c='r', s=20)

    plt.tight_layout()
    plt.savefig('streamline_comparison.png')
    print("Saved visualization to streamline_comparison.png")

    for i in range(min(3, num_streams)):
        linear_stream = linear_streams[i]
        hermite_stream = hermite_streams[i]
        min_length = min(len(linear_stream), len(hermite_stream))
        linear_points = linear_stream[:min_length]
        hermite_points = hermite_stream[:min_length]
        diff = np.linalg.norm(linear_points - hermite_points, axis=1)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(diff, 'r-', label=f'Streamline {i + 1} point differences')
        ax.set_title(f'Point-by-point Euclidean distance (Streamline {i + 1})')
        ax.set_xlabel('Point index')
        ax.set_ylabel('Distance')
        ax.grid(True)
        ax.legend()
        plt.tight_layout()
        plt.savefig(f'streamline_{i + 1}_point_diff.png')
        print(f"Saved point difference plot to streamline_{i + 1}_point_diff.png")
        mean_diff = np.mean(diff)
        print(f"Mean point difference for streamline {i + 1}: {mean_diff:.6f}")

    if num_streams > 0:
        fig, axes = plt.subplots(3, 1, figsize=(15, 10))
        linear_stream = linear_streams[0]
        hermite_stream = hermite_streams[0]
        axes[0].plot(linear_stream[:, 0], 'b-', label='Linear')
        axes[0].plot(hermite_stream[:, 0], 'g-', label='Hermite')
        axes[0].set_title('X Coordinate Comparison')
        axes[0].set_ylabel('X')
        axes[0].grid(True)
        axes[0].legend()
        axes[1].plot(linear_stream[:, 1], 'b-', label='Linear')
        axes[1].plot(hermite_stream[:, 1], 'g-', label='Hermite')
        axes[1].set_title('Y Coordinate Comparison')
        axes[1].set_ylabel('Y')
        axes[1].grid(True)
        axes[1].legend()
        axes[2].plot(linear_stream[:, 2], 'b-', label='Linear')
        axes[2].plot(hermite_stream[:, 2], 'g-', label='Hermite')
        axes[2].set_title('Z Coordinate Comparison')
        axes[2].set_xlabel('Point index')
        axes[2].set_ylabel('Z')
        axes[2].grid(True)
        axes[2].legend()
        plt.tight_layout()
        plt.savefig('coordinate_comparison.png')
        print("Saved coordinate comparison to coordinate_comparison.png")


def plot_metrics_comparison(linear_metrics, hermite_metrics):
    """
    Plotting metrics comparison between linear and Hermite interpolation.

    Parameters
    ----------
    linear_metrics : dict
        Metrics for linear interpolation.
    hermite_metrics : dict
        Metrics for Hermite interpolation.
    """
    linear_curv = linear_metrics.get('curvature', [])
    hermite_curv = hermite_metrics.get('curvature', [])
    linear_length = linear_metrics.get('length', [])
    hermite_length = hermite_metrics.get('length', [])
    linear_torsion = linear_metrics.get('torsion', [])
    hermite_torsion = hermite_metrics.get('torsion', [])

    if not linear_curv or not hermite_curv or not linear_length or not hermite_length:
        print("Insufficient data for metrics comparison plots.")
        return

    linear_curv_flat = []
    hermite_curv_flat = []
    for l_curv, h_curv in zip(linear_curv, hermite_curv):
        linear_curv_flat.extend(l_curv)
        hermite_curv_flat.extend(h_curv)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(linear_curv_flat, bins=50, alpha=0.5, label='Linear', color='blue')
    ax.hist(hermite_curv_flat, bins=50, alpha=0.5, label='Hermite', color='green')
    ax.set_title('Curvature Distribution')
    ax.set_xlabel('Curvature')
    ax.set_ylabel('Frequency')
    ax.grid(True)
    ax.legend()
    plt.tight_layout()
    plt.savefig('curvature_histogram.png')
    print("Saved curvature histogram to curvature_histogram.png")

    fig, ax = plt.subplots(figsize=(10, 6))
    indices = np.arange(min(len(linear_length), len(hermite_length)))
    ax.bar(indices - 0.2, linear_length, width=0.4, alpha=0.6, label='Linear', color='blue')
    ax.bar(indices + 0.2, hermite_length, width=0.4, alpha=0.6, label='Hermite', color='green')
    ax.set_title('Streamline Length Comparison')
    ax.set_xlabel('Streamline Index')
    ax.set_ylabel('Length')
    ax.grid(True)
    ax.legend()
    plt.tight_layout()
    plt.savefig('length_comparison.png')
    print("Saved length comparison to length_comparison.png")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(linear_length, hermite_length, alpha=0.7)
    ax.plot([min(linear_length), max(linear_length)], [min(linear_length), max(linear_length)], 'r--')
    ax.set_title('Linear vs. Hermite Length Scatter Plot')
    ax.set_xlabel('Linear Length')
    ax.set_ylabel('Hermite Length')
    ax.grid(True)
    plt.tight_layout()
    plt.savefig('length_scatter.png')
    print("Saved length scatter plot to length_scatter.png")

    if linear_torsion and hermite_torsion:
        linear_torsion_flat = []
        hermite_torsion_flat = []
        for l_torsion, h_torsion in zip(linear_torsion, hermite_torsion):
            linear_torsion_flat.extend(np.abs(l_torsion))
            hermite_torsion_flat.extend(np.abs(h_torsion))
        upper_limit = np.percentile(linear_torsion_flat + hermite_torsion_flat, 99)
        linear_torsion_filtered = [t for t in linear_torsion_flat if t < upper_limit]
        hermite_torsion_filtered = [t for t in hermite_torsion_flat if t < upper_limit]
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(linear_torsion_filtered, bins=50, alpha=0.5, label='Linear', color='blue')
        ax.hist(hermite_torsion_filtered, bins=50, alpha=0.5, label='Hermite', color='green')
        ax.set_title('Torsion Distribution (Absolute Values, 99th Percentile)')
        ax.set_xlabel('Torsion')
        ax.set_ylabel('Frequency')
        ax.grid(True)
        ax.legend()
        plt.tight_layout()
        plt.savefig('torsion_histogram.png')
        print("Saved torsion histogram to torsion_histogram.png")

        if len(linear_curv) > 0 and len(hermite_curv) > 0:
            linear_mean_curvs = [np.mean(c) for c in linear_curv]
            sample_idx = np.argmax(linear_mean_curvs)
            if sample_idx < len(linear_torsion) and sample_idx < len(hermite_torsion):
                fig, axes = plt.subplots(2, 1, figsize=(12, 10))
                axes[0].plot(linear_curv[sample_idx], 'b-', label='Linear')
                axes[0].plot(hermite_curv[sample_idx], 'g-', label='Hermite')
                axes[0].set_title(f'Curvature Along Streamline {sample_idx + 1}')
                axes[0].set_xlabel('Point Index')
                axes[0].set_ylabel('Curvature')
                axes[0].grid(True)
                axes[0].legend()
                axes[1].plot(linear_torsion[sample_idx], 'b-', label='Linear')
                axes[1].plot(hermite_torsion[sample_idx], 'g-', label='Hermite')
                axes[1].set_title(f'Torsion Along Streamline {sample_idx + 1}')
                axes[1].set_xlabel('Point Index')
                axes[1].set_ylabel('Torsion')
                axes[1].grid(True)
                axes[1].legend()
                plt.tight_layout()
                plt.savefig('curvature_torsion_comparison.png')
                print("Saved curvature and torsion comparison to curvature_torsion_comparison.png")


def compare_interpolations(trk_file, step_size=0.5, voxel_size=None, num_streamlines=None, use_gpu=False):
    """
    Comparing linear and Hermite interpolation methods.

    Parameters
    ----------
    trk_file : str
        Path to input TRK file.
    step_size : float, optional
        Step size for streamline densification (default: 0.5).
    voxel_size : float, optional
        Voxel size to use for processing. If None, the voxel size from the TRK file is used.
    num_streamlines : int, optional
        Number of streamlines to process (default: all).
    use_gpu : bool, optional
        Whether using GPU acceleration (default: False).
    """
    print(f"Comparing interpolation methods on {trk_file}")
    print(f"Step size: {step_size}, Using GPU: {use_gpu}")

    print("Loading streamlines...")
    trk_data = nib.streamlines.load(trk_file)
    streamlines = trk_data.streamlines
    original_voxel_sizes = trk_data.header.get('voxel_sizes', [1.0, 1.0, 1.0])
    original_voxel_size = float(np.mean(original_voxel_sizes))

    if voxel_size is None:
        voxel_size = original_voxel_size

    print(
        f"Original voxel sizes: {original_voxel_sizes[0]:.3f}, {original_voxel_sizes[1]:.3f}, {original_voxel_sizes[2]:.3f}mm")
    print(f"Mean voxel size: {original_voxel_size:.3f}mm, Using voxel size: {voxel_size:.3f}mm")
    print(f"Loaded {len(streamlines)} streamlines.")

    if num_streamlines is not None and num_streamlines < len(streamlines):
        print(f"Limiting to {num_streamlines} streamlines.")
        streamlines = streamlines[:num_streamlines]

    linear_streams = process_streamlines_with_method(streamlines, step_size, 'linear', voxel_size=voxel_size,
                                                     use_gpu=use_gpu)
    hermite_streams = process_streamlines_with_method(streamlines, step_size, 'hermite', voxel_size=voxel_size,
                                                      use_gpu=use_gpu)

    if not linear_streams or not hermite_streams:
        print("ERROR: Failed to process streamlines with one or both methods.")
        return

    print("\nBasic Statistics:")
    print(f"Linear interpolation: {len(linear_streams)} streamlines processed.")
    print(f"Hermite interpolation: {len(hermite_streams)} streamlines processed.")

    total_points_linear = sum(len(s) for s in linear_streams)
    total_points_hermite = sum(len(s) for s in hermite_streams)
    print(f"Total points - Linear: {total_points_linear}, Hermite: {total_points_hermite}")
    diff = total_points_hermite - total_points_linear
    print(
        f"Difference in point count: {diff} ({(diff / total_points_linear * 100) if total_points_linear > 0 else 0:.2f}%)")

    linear_metrics, hermite_metrics = calculate_metrics_for_both_methods(linear_streams, hermite_streams)
    compare_metrics(linear_metrics, hermite_metrics)
    visualize_comparison(linear_streams, hermite_streams)
    plot_metrics_comparison(linear_metrics, hermite_metrics)

    print("\nComparison completed. Check the generated plots for visual details.")
    print("\nTorsion and Curvature Summary:")
    if 'mean_curvature' in linear_metrics and 'mean_curvature' in hermite_metrics:
        curv_diff_pct = ((hermite_metrics['mean_curvature'] - linear_metrics['mean_curvature']) /
                         linear_metrics['mean_curvature'] * 100) if linear_metrics['mean_curvature'] > 0 else 0
        print(
            f"Curvature: Hermite is {abs(curv_diff_pct):.1f}% {'higher' if curv_diff_pct > 0 else 'lower'} than Linear")
    if 'mean_torsion' in linear_metrics and 'mean_torsion' in hermite_metrics:
        torsion_diff_pct = ((hermite_metrics['mean_torsion'] - linear_metrics['mean_torsion']) /
                            linear_metrics['mean_torsion'] * 100) if linear_metrics['mean_torsion'] > 0 else 0
        print(
            f"Torsion: Hermite is {abs(torsion_diff_pct):.1f}% {'higher' if torsion_diff_pct > 0 else 'lower'} than Linear")
    if 'mean_curvature' in linear_metrics and 'mean_torsion' in linear_metrics:
        if curv_diff_pct > 5 and torsion_diff_pct > 5:
            print(
                "Both curvature and torsion are significantly higher with Hermite interpolation, indicating better preservation of streamline geometry.")
        elif curv_diff_pct < -5 and torsion_diff_pct < -5:
            print(
                "Both curvature and torsion are lower with Hermite interpolation, which may indicate smoothing or implementation issues.")
        else:
            print("Mixed results between curvature and torsion metrics. Visual inspection is recommended.")


def main():
    parser = argparse.ArgumentParser(description='Compare linear and Hermite interpolation methods for streamlines.')
    parser.add_argument('trk_file', type=str, help='Path to input TRK file.')
    parser.add_argument('--step_size', type=float, default=0.5, help='Step size for densification (default: 0.5).')
    parser.add_argument('--voxel_size', type=float, default=None,
                        help='Voxel size for analysis (default: use voxel size from TRK file).')
    parser.add_argument('--num_streamlines', type=int, default=None,
                        help='Number of streamlines to process (default: all).')
    parser.add_argument('--use_gpu', type=lambda x: str(x).lower() != 'false', nargs='?', const=True, default=False,
                        help='Use GPU acceleration (default: False).')
    parser.add_argument('--debug_tangents', action='store_true', default=False,
                        help='Enable detailed tangent debugging (default: False).')

    args = parser.parse_args()

    if args.debug_tangents:
        os.environ["DEBUG_TANGENTS"] = "1"
        print("Tangent debugging enabled")

    compare_interpolations(args.trk_file, args.step_size, args.voxel_size, args.num_streamlines, args.use_gpu)


if __name__ == "__main__":
    main()