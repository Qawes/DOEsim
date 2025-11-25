import subprocess
import shutil
import os
import sys

# --- CONFIGURABLE PATHS ---
# Path to diffractsim source folder (edit as needed)
diffractsim_src = os.path.join("diffractsim-main", "diffractsim")
# Path to where diffractsim should be copied in the build output
diffractsim_dst = os.path.join("dist", "main", "_internal", "diffractsim")

# Other files/folders to copy (relative to project root)
# Universal relative-path preservation for multiple entries
# Provide paths relative to project root; nested paths are recreated under dist/main
to_copy = [
    "fzp_icon.ico",
    "aperatures",
    "_internal/resources", 
    # add more entries like "data/models", "configs/defaults" etc.
]


_orig_basename = os.path.basename
def _basename_preserve(path):
    
    if "/" in path or "\\" in path:
        return path
    return _orig_basename(path)
os.path.basename = _basename_preserve


_orig_copy2 = shutil.copy2
def _copy2_with_dirs(src, dst, *args, **kwargs):
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return _orig_copy2(src, dst, *args, **kwargs)
shutil.copy2 = _copy2_with_dirs


pyi_cmd = [
    sys.executable, "-m", "PyInstaller",
    "--windowed", "--onedir", "--clean",
    "--icon", "fzp_icon.ico",
    "main.py"
]
print("Running PyInstaller...")
subprocess.run(pyi_cmd, check=True)


print(f"Copying diffractsim from {diffractsim_src} to {diffractsim_dst} ...")
if os.path.exists(diffractsim_dst):
    shutil.rmtree(diffractsim_dst)
shutil.copytree(diffractsim_src, diffractsim_dst)
print("Copied diffractsim folder.")


dist_dir = os.path.join("dist", "main")
print("Copying extra files/folders...")
for item in to_copy:
    src = os.path.abspath(item)
    dst = os.path.join(dist_dir, os.path.basename(item))
    if os.path.isdir(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"Copied folder: {item}")
    elif os.path.isfile(src):
        shutil.copy2(src, dst)
        print(f"Copied file: {item}")
    else:
        print(f"Warning: {item} not found.")

print("Build and copy complete.")