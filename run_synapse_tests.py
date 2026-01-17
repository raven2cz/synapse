import subprocess
import os
import sys

def run_command(cmd, cwd=None):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    print("STDOUT:")
    print(result.stdout)
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    return result.returncode

def main():
    root = "/home/box/git/github/synapse"
    uv_bin = "/home/box/.local/bin/uv"
    
    print(f"Starting test runner in {root}")
    
    # 1. Sync venv
    print("\n--- Syncing Environment ---")
    run_command([uv_bin, "pip", "install", "-e", ".[dev]"], cwd=root)
    
    # 2. Run logic tests
    print("\n--- Running Logic Tests ---")
    exit_code = run_command([uv_bin, "run", "pytest", "tests/store/test_pack_service_v2.py", "tests/store/test_pack_workflow.py", "-v"], cwd=root)
    
    # 3. Running architectural checks
    print("\n--- Running Architectural Checks (No Legacy API calls) ---")
    
    # Check backend
    print("\nChecking backend:")
    backend_grep = subprocess.run(['grep', '-r', "--exclude-dir=__pycache__", "/api/comfyui", os.path.join(root, "apps/api/src")], capture_output=True, text=True)
    
    print(f"Grep Return Code: {backend_grep.returncode}")
    if backend_grep.stdout:
        print(f"Grep Stdout: {backend_grep.stdout}")
    if backend_grep.stderr:
        print(f"Grep Stderr: {backend_grep.stderr}")

    if backend_grep.returncode != 0 and not backend_grep.stdout:
        print("PASS: No legacy calls in backend.")
    else:
        print("FAIL: Found legacy calls in backend.")
        exit_code = 1
        
    # Check frontend
    print("\nChecking frontend:")
    # We ignore the .git and node_modules if they exist, but here we just check apps/web/src
    frontend_grep = subprocess.run(['grep', '-r', "/api/comfyui", os.path.join(root, "apps/web/src")], capture_output=True, text=True)
    if frontend_grep.returncode != 0 and not frontend_grep.stdout:
        print("PASS: No legacy calls in frontend.")
    else:
        # We need to check if these are real calls or just comments/placeholders
        print("Found some matches in frontend, reviewing...")
        # For now, if there are matches, we report them
        print(frontend_grep.stdout)
        # Note: We expect 0 matches in our modified path.
        if frontend_grep.stdout:
             exit_code = 1
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
