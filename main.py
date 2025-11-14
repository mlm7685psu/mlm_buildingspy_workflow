"""
JSON-driven simulation orchestrator for Modelica data center templates.

Usage:
    python main.py --config main.json [--run-id mo03_baseline]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DYMOLA = Path(
    r"C:\Program Files\Dymola 2024x Refresh 1\bin64\Dymola.exe"
)

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "mo_01": {
        "description": "1N DX-cooled data center without ASE",
        "model_file": "mo_01_Data-Center_DX-cooled_without_ASE_1N/mo_01_dc_woase_n1.mo",
        "entry_model": "mo_01_dc_woase_n1.CRAC_DXwoASE.CRAC_dx",
        "default_stop": 86_400,
        "default_intervals": 8_640,
        "default_results": "runs/mo01_baseline",
    },
    "mo_03": {
        "description": "4N DX-cooled data center without ASE",
        "model_file": "mo_03_Data-Center_DX-cooled_without_ASE_4N/mo_03_dc_woase_n4.mo",
        "entry_model": "mo_03_dc_woase_n4.CRAC_DXwoASE.CRAC_dx",
        "default_stop": 86_400,
        "default_intervals": 8_640,
        "default_results": "runs/mo03_baseline",
    },
}

MOS_TEMPLATE = textwrap.dedent(
    """
    Modelica.Utilities.Streams.print("=== Starting {run_id} ===");
    cd("{repo_path}");
    clearlog();

    loadModel("Modelica");

    Modelica.Utilities.Streams.print("Loading Buildings library from {buildings_file}");
    openModel("{buildings_file}");

    Modelica.Utilities.Streams.print("Loading template package {model_file}");
    openModel("{model_file}");

    resultsDir := "{results_dir}";
    if not Modelica.Utilities.Files.exist(resultsDir) then
      Modelica.Utilities.Files.createDirectory(resultsDir);
    end if;

    Modelica.Utilities.Streams.print("Simulating {entry_model} ...");
    simulateModel(
      "{entry_model}",
      startTime=0,
      stopTime={stop_time},
      numberOfIntervals={n_intervals},
      tolerance={tolerance},
      method="{method}",
      resultFile="{result_file}");

    Modelica.Utilities.Streams.print("Simulation finished. Results stored at {result_file}.mat");
    """
).strip()


def posix(path: Path) -> str:
    """Return a forward-slash path for Dymola."""
    return path.as_posix()


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def select_runs(config: Dict[str, Any], run_id: str | None) -> List[Dict[str, Any]]:
    runs: List[Dict[str, Any]] = config.get("runs", [])
    if not runs:
        raise ValueError("Config must contain a non-empty 'runs' array.")
    if run_id is None:
        return runs
    for run in runs:
        if run.get("run_id") == run_id:
            return [run]
    raise ValueError(f"Run id '{run_id}' not found in config.")


def build_mos_text(
    run: Dict[str, Any],
    template_cfg: Dict[str, Any],
    buildings_file: Path,
) -> tuple[str, Path]:
    repo_path = posix(REPO_ROOT)
    model_file = posix(REPO_ROOT / template_cfg["model_file"])
    entry_model = run.get("entry_model", template_cfg["entry_model"])
    stop_time = run.get("stop_time", template_cfg["default_stop"])
    n_intervals = run.get("number_of_intervals", template_cfg["default_intervals"])
    tolerance = run.get("tolerance", 1e-6)
    method = run.get("method", "Dassl")

    results_rel = run.get("result_subdir", template_cfg["default_results"])
    results_dir = REPO_ROOT / results_rel
    results_dir.mkdir(parents=True, exist_ok=True)
    result_file = results_dir / run["run_id"]

    mos_body = MOS_TEMPLATE.format(
        run_id=run["run_id"],
        repo_path=repo_path,
        buildings_file=posix(buildings_file),
        model_file=model_file,
        results_dir=posix(results_dir),
        entry_model=entry_model,
        stop_time=stop_time,
        n_intervals=n_intervals,
        tolerance=tolerance,
        method=method,
        result_file=posix(result_file),
    )
    return mos_body + "\n", results_dir


def write_mos_file(run_id: str, mos_text: str) -> Path:
    target_dir = REPO_ROOT / "automation" / "generated_mos"
    target_dir.mkdir(parents=True, exist_ok=True)
    mos_path = target_dir / f"{run_id}.mos"
    mos_path.write_text(mos_text, encoding="utf-8")
    return mos_path


def execute_run(run: Dict[str, Any], dymola_exe: Path) -> None:
    template_key = run.get("template")
    if template_key not in TEMPLATES:
        raise ValueError(f"Unknown template '{template_key}'. Available: {', '.join(TEMPLATES)}")
    template_cfg = TEMPLATES[template_key]

    buildings_file = REPO_ROOT / "Buildings" / "package.mo"
    if not buildings_file.exists():
        raise FileNotFoundError("Buildings library not found. Did you initialize submodules?")

    mos_text, results_dir = build_mos_text(run, template_cfg, buildings_file)
    mos_path = write_mos_file(run["run_id"], mos_text)

    print(f"[INFO] Running '{run['run_id']}' using {mos_path}")
    try:
        subprocess.run(
            [str(dymola_exe), str(mos_path)],
            cwd=REPO_ROOT,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Dymola run '{run['run_id']}' failed") from exc

    mat_path = results_dir / f"{run['run_id']}.mat"
    if mat_path.exists():
        print(f"[INFO] Result file available at {mat_path}")
    else:
        print(f"[WARN] Expected result file missing: {mat_path}")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Modelica simulation orchestrator")
    parser.add_argument(
        "--config",
        default="main.json",
        help="Path to JSON config (default: main.json)",
    )
    parser.add_argument(
        "--run-id",
        help="Run only the specified run_id from the config",
    )
    parser.add_argument(
        "--dymola-exe",
        help="Override path to Dymola executable",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    config_path = (REPO_ROOT / args.config).resolve() if not os.path.isabs(args.config) else Path(args.config)
    config = load_config(config_path)

    dymola_path = Path(args.dymola_exe or config.get("dymola_exe", DEFAULT_DYMOLA))
    if not dymola_path.exists():
        raise FileNotFoundError(f"Dymola executable not found: {dymola_path}")

    runs = select_runs(config, args.run_id)
    for run in runs:
        execute_run(run, dymola_path)


if __name__ == "__main__":
    main()
