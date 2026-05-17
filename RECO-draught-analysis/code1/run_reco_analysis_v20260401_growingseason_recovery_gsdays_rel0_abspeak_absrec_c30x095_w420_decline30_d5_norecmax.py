#!/usr/bin/env python3
import os
import sys

BASE_DIR = "/home/xulc/flash_drought"
SHARED_DIR = os.path.join(BASE_DIR, "process/NEE-draught-analysis/_shared")
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

from response_launchers_v20260322_lu_025deg import run_with_abs_key


if __name__ == "__main__":
    run_with_abs_key("reco_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax")
