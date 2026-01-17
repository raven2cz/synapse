import os
import subprocess
import sys

def main():
    print(f"Current working directory: {os.getcwd()}")
    print(f"User ID: {os.getuid()}")
    print(f"Python executable: {sys.executable}")
    
    try:
        files = os.listdir('.')
        print(f"Files in current directory ({len(files)}):")
        for f in sorted(files):
            print(f" - {f}")
    except Exception as e:
        print(f"Error listing directory: {e}")

    print("\nEnvironment variables:")
    for k, v in sorted(os.environ.items()):
        if k in ['PATH', 'PYTHONPATH', 'SYNAPSE_ROOT', 'PWD']:
            print(f"{k}={v}")

    print("\nAttempting to run 'ls -la':")
    try:
        result = subprocess.run(['ls', '-la'], capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"Error running 'ls -la': {e}")

if __name__ == "__main__":
    main()
