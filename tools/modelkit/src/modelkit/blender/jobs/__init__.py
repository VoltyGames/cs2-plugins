"""Jobs the CLI runs in a background Blender: each module's `main(**args)` returns JSON data.

`modelkit.headless.run_job` starts Blender with this entry point and reads the result file.
"""

import importlib
import json


def run(job: str, args: str, result_path: str) -> None:
    result = importlib.import_module(f"{__name__}.{job}").main(**json.loads(args))
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f)
