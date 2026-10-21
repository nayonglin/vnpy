"""This directory is passed only to the newly launched OFF-provider process tree."""
import os
from pathlib import Path
import sys

sys.dont_write_bytecode=True
try:
    tools=Path(__file__).resolve().parent.parent
    sys.path.insert(0,str(tools))
    from stage109_provider_runtime_launcher import bootstrap_from_env
    bootstrap_from_env()
except BaseException as error:
    # Python normally swallows sitecustomize errors. Never enter a CLI body
    # after a failed identity check, and never print environment/credentials.
    os.write(2,('stage109_bootstrap_failed:'+type(error).__name__+'\n').encode())
    os._exit(78)
