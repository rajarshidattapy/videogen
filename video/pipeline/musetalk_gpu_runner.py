"""Run talking-head model subprocesses under a strict CUDA-only, VRAM-capped policy.

This module is deliberately executed by MuseTalk's own virtualenv, before any
vendor code imports torch. It prevents the vendor scripts' CPU fallback from
ever being reached and keeps the PyTorch allocator under the configured budget.
"""

from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strict CUDA launcher for MuseTalk inference")
    parser.add_argument("--gpu-index", type=int, required=True)
    parser.add_argument("--gpu-memory-limit-mb", type=int, required=True)
    parser.add_argument("--gpu-memory-fraction", type=float, required=True)
    parser.add_argument("musetalk_command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.gpu_index < 0:
        parser.error("--gpu-index must be non-negative")
    if args.gpu_memory_limit_mb < 512:
        parser.error("--gpu-memory-limit-mb must be at least 512")
    if not 0 < args.gpu_memory_fraction <= 1:
        parser.error("--gpu-memory-fraction must be in (0, 1]")
    if args.musetalk_command[:1] == ["--"]:
        args.musetalk_command = args.musetalk_command[1:]
    valid_musetalk = args.musetalk_command[:2] == ["-m", "scripts.inference"]
    valid_liveportrait = args.musetalk_command[:1] == ["--script"] and len(
        args.musetalk_command
    ) >= 2
    if not valid_musetalk and not valid_liveportrait:
        parser.error(
            "only `-m scripts.inference ...` or `--script inference.py ...` may be launched "
            "through this guard"
        )
    return args


def main() -> int:
    args = _arguments()

    # These must be set before torch is imported. CUDA_VISIBLE_DEVICES maps the
    # requested physical card to logical cuda:0 for the vendor inference code.
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_index)
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "max_split_size_mb:64")

    import torch

    if not torch.cuda.is_available():
        print("CUDA is required for MuseTalk; refusing CPU fallback.", file=sys.stderr)
        return 3
    device = torch.device("cuda:0")
    try:
        torch.cuda.set_device(device)
        properties = torch.cuda.get_device_properties(device)
    except Exception as exc:
        print(f"GPU {args.gpu_index} is unavailable; refusing CPU fallback: {exc}", file=sys.stderr)
        return 3

    total_mb = properties.total_memory / (1024 * 1024)
    if args.gpu_memory_limit_mb > total_mb:
        print(
            f"GPU_MEMORY_LIMIT_MB={args.gpu_memory_limit_mb} exceeds GPU {args.gpu_index}'s "
            f"available {total_mb:.0f}MB; refusing to run.",
            file=sys.stderr,
        )
        return 3
    memory_fraction = min(args.gpu_memory_fraction, args.gpu_memory_limit_mb / total_mb)
    torch.cuda.set_per_process_memory_fraction(memory_fraction, device)
    torch.cuda.empty_cache()
    print(
        f"MuseTalk CUDA guard: GPU {args.gpu_index} ({properties.name}), "
        f"allocator cap {memory_fraction * total_mb:.0f}/{total_mb:.0f}MB, CPU fallback disabled.",
        flush=True,
    )

    # The runner lives outside each vendor repository, so add its cwd explicitly
    # before resolving the chosen package or script entrypoint.
    sys.path.insert(0, str(Path.cwd()))
    if args.musetalk_command[:2] == ["-m", "scripts.inference"]:
        sys.argv = ["scripts.inference", *args.musetalk_command[2:]]
        runpy.run_module("scripts.inference", run_name="__main__")
    else:
        script = Path(args.musetalk_command[1])
        sys.argv = [str(script), *args.musetalk_command[2:]]
        runpy.run_path(script, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
