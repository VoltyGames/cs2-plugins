"""Jobs the CLI runs in a background Blender: each module's `main(**args)` returns JSON data.

`modelkit.headless.run_job` starts Blender with this entry point.
"""

import importlib
import json


def run(job: str, args_path: str, result_path: str) -> None:
    with open(args_path, encoding="utf-8") as f:
        args = json.load(f)
    result = importlib.import_module(f"{__name__}.{job}").main(**args)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f)
