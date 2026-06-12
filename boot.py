#!/usr/bin/env -S python3 -B
import subprocess
import sys
import os

# Ensure Cargo-installed binaries (e.g. chariot) are findable
os.environ["PATH"] = os.path.expanduser("~/.cargo/bin") + os.pathsep + os.environ.get("PATH", "")

QEMU_FLAGS = [
    "-m", "2G",
    "-cpu", "IvyBridge",
    "-debugcon", "stdio",
    "-d", "int",
]


def run_command(cmd, **kwargs):
    """Run a command, raise on failure."""
    result = subprocess.run(cmd, check=True, **kwargs)
    return result


def get_eucalypt_path():
    """Resolve the eucalypt package install directory via chariot."""
    result = run_command(
        ["chariot", "path", "package/eucalypt_kernel"],
        capture_output=True,
        text=True,
    )
    for line in result.stderr.splitlines():
        if "Path:" in line:
            return line.split("Path:", 1)[1].strip()
    raise RuntimeError(f"Could not parse chariot path output:\n{result.stderr}")


def install_file(src, dst_dir):
    """Copy a single file into dst_dir."""
    run_command(["install", "-D", src, dst_dir])


def install_dir(src, dst_dir):
    """Recursively copy a directory into dst_dir."""
    run_command(["cp", "-r", src, dst_dir])


def setup_output(eucalypt_path):
    """Create output directory and install required files."""
    os.makedirs("output", exist_ok=True)

    install_file(
        os.path.join(eucalypt_path, "eucalypt-x86_64.iso"),
        "./output",
    )
    install_dir(
        os.path.join(eucalypt_path, "disks"),
        "./output",
    )
    install_dir(
        os.path.join(eucalypt_path, "edk2-ovmf"),
        "./output",
    )


def run_qemu():
    """Launch QEMU with the eucalypt ISO."""
    cmd = [
        "qemu-system-x86_64",
        "-M", "q35",
        "-drive", "if=pflash,unit=0,format=raw,"
                  "file=output/edk2-ovmf/ovmf-code-x86_64.fd,readonly=on",
        "-cdrom", "./output/eucalypt-x86_64.iso",
        *QEMU_FLAGS,
    ]
    run_command(cmd)


def main():
    run_command(["chariot", "wipe", "recipe", "package/eucalypt_kernel"])
    run_command(["chariot", "build", "package/eucalypt_kernel"])
    try:
        eucalypt_path = get_eucalypt_path()
        print(f"Using eucalypt path: {eucalypt_path}")
        setup_output(eucalypt_path)
        run_qemu()
    except subprocess.CalledProcessError as e:
        print(f"Command failed (exit {e.returncode}): {' '.join(e.cmd)}", file=sys.stderr)
        sys.exit(e.returncode)
    except FileNotFoundError as e:
        print(f"Executable not found: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()