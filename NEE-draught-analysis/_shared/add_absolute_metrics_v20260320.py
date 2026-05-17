#!/usr/bin/env python3
"""Compatibility shim for v20260320 outputs that already contain absolute metrics."""

import os
import shutil


def augment_absolute_metrics(input_file, data_file=None, var_name=None, output_file=None, **kwargs):
    del data_file, var_name, kwargs
    if output_file is None or os.path.abspath(output_file) == os.path.abspath(input_file):
        return input_file
    shutil.copyfile(input_file, output_file)
    return output_file
