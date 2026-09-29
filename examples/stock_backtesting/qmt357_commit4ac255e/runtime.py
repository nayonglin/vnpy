"""Choose this variant's private settings before any vn.py import."""
import os
from pathlib import Path
import sys

from .config import ROOT


def activate_runtime():
    runtime = ROOT / 'runtime'
    private = runtime / '.vntrader'
    if runtime.is_symlink() or private.is_symlink():
        raise ValueError('Variant runtime paths must not be symlinks')
    utility = sys.modules.get('vnpy.trader.utility')
    if utility is not None and Path(utility.TEMP_DIR).resolve() != private.resolve():
        raise RuntimeError('vn.py already uses another settings directory; use standalone CLI')
    private.mkdir(parents=True, exist_ok=True)
    os.chdir(runtime)
    return runtime
