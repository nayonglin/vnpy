"""Select a private vn.py settings directory BEFORE importing vn.py."""
import os
from pathlib import Path
import sys

from .config import ROOT


def activate_runtime() -> Path:
    runtime = ROOT / 'runtime'
    private = runtime / '.vntrader'
    if runtime.is_symlink() or private.is_symlink():
        raise ValueError('Stock runtime paths must not be symlinks')
    utility = sys.modules.get('vnpy.trader.utility')
    if utility is not None and Path(utility.TEMP_DIR).resolve() != private.resolve():
        raise RuntimeError('vn.py is already loaded with another settings directory; use the standalone stock CLI')
    private.mkdir(parents=True, exist_ok=True)
    os.chdir(runtime)
    return runtime
