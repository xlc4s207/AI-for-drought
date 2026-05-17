#!/usr/bin/env python3
import os
import sys

BASE_DIR = "/home/xulc/flash_drought"
SHARED_DIR = os.path.join(BASE_DIR, "process/NEE-draught-analysis/_shared")
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

from response_launchers_v20260316_2 import run_with_abs_key


if __name__ == "__main__":
    run_with_abs_key("nee_code1")
