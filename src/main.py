import argparse
import nibabel as nib
import numpy as np
import os
from nifti_preprocessing import resample_nifti
from transform import build_new_affine
from streamline_processing import transform_and_densify_streamlines
from nibabel.streamlines import Tractogram, save as save_trk


def process_and_save(
        old_nifti_path,
        old_trk_path,
        new_voxel_size=0.5,
        new_dim=(116, 140, 96),
        output_prefix="resampled",
        n_jobs=8,
        patch_center=None,
        reduction_method=None,
        use_gpu=True,
        interp_method='hermite',
        step_size=0.5,
        max_output_gb=64.0
):
    """
    Processing and resampling NIfTI and tractography data.

    Parameters
    ----------
    old_nifti_path : str
        Path to input NIfTI file.
    old_trk_path : str
        Path to input TRK file.
    new_voxel_size : float, optional
        New voxel size, by default 0.5.
    new_dim : tuple, optional
        New dimensions, by default (116, 140, 96).
    output_prefix : str, optional
        Output file prefix, by default "resampled".
    n_jobs : int, optional
        Number of parallel jobs, by default 8.
    patch_center : tuple, optional
        Center point in mm, by default None.
    reduction_method : str, optional
        Reduction method (mip or mean), by default None.
    use_gpu : bool, optional
        Whether to use GPU acceleration, by default True.
    interp_method : str, optional
        Interpolation method for streamlines ('hermite' or 'linear'), by default 'hermite'.
    step_size : float, optional
        Step size for streamline densification, by default 0.5.
    max_output_gb : float, optional
        Maximum output size in GB, by default 64.0.
    """
    # Choosing array library based on GPU usage
    if use_gpu:
        try:
            import cupy as xp
            from numba import cuda
            print("Using GPU acceleration")
        except ImportError:
            print("Could not import GPU libraries, falling back to CPU")
            import numpy as xp
            use_gpu = False
    else:
        import numpy as xp
        print("Using CPU processing")

    print("Loading NIfTI data")
    old_img = nib.load(old_nifti_path, mmap=True)
    old_affine = old_img.affine
    old_shape = old_img.shape[:3]
    old_voxel_sizes = np.array(old_img.header.get_zooms()[:3])
    print(f"Old shape: {old_shape}")
    print(f"Old voxel sizes: {old_voxel_sizes}")
    print(f"Old affine:\n{old_affine}")

    print("Building new affine")
    print(f"Using dimensions: {new_dim}")
    A_new = build_new_affine(old_affine, old_shape, new_voxel_size, new_dim, patch_center_mm=patch_center,
                             use_gpu=use_gpu)
    print(f"New affine:\n{A_new}")
    print(f"New dimensions: {new_dim}")

    print(f"Resampling NIfTI data using {'GPU' if use_gpu else 'CPU'}")
    print(f"Resampling to dimensions: {new_dim}, Memory limit: {max_output_gb} GB")
    new_data, tmp_mmap = resample_nifti(old_img, A_new, new_dim, chunk_size=(64, 64, 64), n_jobs=n_jobs,
                                        use_gpu=use_gpu, max_output_gb=max_output_gb)
    print(f"Resampled data shape: {new_data.shape}")

    if new_data.shape[:3] != new_dim:
        print(f"WARNING: Resampled shape {new_data.shape[:3]} does not match expected dimensions {new_dim}")
        print("This could lead to streamline clipping issues!")

    if reduction_method:
        print(f"Applying reduction: {reduction_method}")
        if use_gpu:
            if reduction_method == 'mip':
                reduced_data = xp.max(new_data, axis=1)
            elif reduction_method == 'mean':
                reduced_data = xp.mean(new_data, axis=1)
            else:
                raise ValueError(f"Unsupported reduction method: {reduction_method}")
            reduced_data = reduced_data[..., xp.newaxis]
            new_data = reduced_data
        else:
            if reduction_method == 'mip':
                reduced_data = np.max(new_data, axis=1)
            elif reduction_method == 'mean':
                reduced_data = np.mean(new_data, axis=1)
            else:
                raise ValueError(f"Unsupported reduction method: {reduction_method}")
            reduced_data = reduced_data[..., np.newaxis]
            new_data = reduced_data
        new_dim = (new_dim[0], 1, new_dim[2])

    new_data_np = xp.asnumpy(new_data) if use_gpu else new_data
    print(f"Final data shape before saving: {new_data_np.shape}")

    new_img = nib.Nifti1Image(new_data_np, A_new)
    out_nifti_path = output_prefix + ".nii.gz"
    nib.save(new_img, out_nifti_path)
    if os.path.exists(tmp_mmap):
        os.remove(tmp_mmap)
    print(f"Saved new NIfTI at {out_nifti_path}")

    print("Loading tractography data")
    trk_obj = nib.streamlines.load(old_trk_path)
    old_streams_mm = trk_obj.tractogram.streamlines
    print(f"Loaded {len(old_streams_mm)} streamlines")

    total_points = sum(len(s) for s in old_streams_mm)
    avg_points = total_points / len(old_streams_mm) if old_streams_mm else 0
    print(f"Total points in original streamlines: {total_points}")
    print(f"Average points per streamline: {avg_points:.2f}")

    print(
        f"Transforming, densifying, and clipping streamlines using {'GPU' if use_gpu else 'CPU'} with {interp_method} interpolation")
    print(f"Step size: {step_size}, Voxel size: {new_voxel_size}, FOV clipping enabled, Using dimensions: {new_dim}")
    densified_vox = transform_and_densify_streamlines(
        old_streams_mm, A_new, new_dim, step_size=step_size, n_jobs=n_jobs,
        use_gpu=use_gpu, interp_method=interp_method
    )

    print(f"Processed {len(densified_vox)} streamlines")
    if len(densified_vox) == 0:
        print(
            "WARNING: No streamlines were processed. Check your parameters and consider a larger voxel size or different step size.")
        return

    total_points_new = sum(len(s) for s in densified_vox)
    avg_points_new = total_points_new / len(densified_vox) if densified_vox else 0
    print(f"Total points in processed streamlines: {total_points_new}")
    print(f"Average points per streamline: {avg_points_new:.2f}")
    print(
        f"Change in streamline count: {len(densified_vox) - len(old_streams_mm)} ({(len(densified_vox) - len(old_streams_mm)) / len(old_streams_mm) * 100:.1f}%)")
    print(
        f"Change in point count: {total_points_new - total_points} ({(total_points_new - total_points) / total_points * 100:.1f}%)")

    new_trk_header = trk_obj.header.copy()
    new_trk_header["dimensions"] = np.array(new_dim, dtype=np.int16)
    new_voxsize = np.sqrt(np.sum(A_new[:3, :3] ** 2, axis=0))
    new_trk_header["voxel_sizes"] = new_voxsize.astype(np.float32)
    new_trk_header["voxel_to_rasmm"] = A_new.astype(np.float32)

    print("Saving new .trk file")
    new_tractogram = Tractogram(densified_vox, affine_to_rasmm=A_new)
    out_trk_path = output_prefix + ".trk"
    save_trk(new_tractogram, out_trk_path, header=new_trk_header)
    print(f"Saved new .trk at {out_trk_path}")
    print("Process completed successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process and resample NIfTI and streamline tractography data.")
    parser.add_argument("--input", type=str, required=True, help="Path to input NIfTI (.nii or .nii.gz) file.")
    parser.add_argument("--trk", type=str, required=True, help="Path to input TRK (.trk) file.")
    parser.add_argument("--output", type=str, default="resampled", help="Prefix for output files.")
    parser.add_argument("--voxel_size", type=float, default=0.5, help="New voxel size (default: 0.5 mm).")
    parser.add_argument("--new_dim", type=int, nargs=3, default=[116, 140, 96], help="New image dimensions (x, y, z).")
    parser.add_argument("--jobs", type=int, default=8, help="Number of parallel jobs (-1 for all CPUs).")
    parser.add_argument("--patch_center", type=float, nargs=3, default=None, help="Optional patch center in mm.")
    parser.add_argument("--reduction", type=str, choices=["mip", "mean"], default=None,
                        help="Optional reduction along z-axis.")
    parser.add_argument("--use_gpu", type=lambda x: str(x).lower() != 'false', nargs='?', const=True, default=True,
                        help="Use GPU acceleration (default: True). Set to False with --use_gpu=False")
    parser.add_argument("--cpu", action="store_true", help="Force CPU processing (disables GPU).")
    parser.add_argument("--interp", type=str, choices=["hermite", "linear"], default="hermite",
                        help="Interpolation method for streamlines (default: hermite).")
    parser.add_argument("--step_size", type=float, default=0.5,
                        help="Step size for streamline densification (default: 0.5).")
    parser.add_argument("--max_gb", type=float, default=64.0,
                        help="Maximum output size in GB (default: 64.0). Dimensions will be automatically reduced if exceeded.")
    args = parser.parse_args()

    requested_dim = tuple(args.new_dim)
    if np.prod(requested_dim) > 100_000_000:
        print(f"WARNING: Requested dimensions {requested_dim} are very large!")
        print("Consider using lower-resolution dimensions or a smaller voxel size.")

    use_gpu = not args.cpu and args.use_gpu
    print(f"Processing mode: {'GPU' if use_gpu else 'CPU'}")

    process_and_save(
        old_nifti_path=args.input,
        old_trk_path=args.trk,
        new_voxel_size=args.voxel_size,
        new_dim=tuple(args.new_dim),
        output_prefix=args.output,
        n_jobs=args.jobs,
        patch_center=tuple(args.patch_center) if args.patch_center else None,
        reduction_method=args.reduction,
        use_gpu=use_gpu,
        interp_method=args.interp,
        step_size=args.step_size,
        max_output_gb=args.max_gb
    )