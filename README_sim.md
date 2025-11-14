# Data Center DX Simulation + Plotting Playbook

1. **Purpose** – Execute the mo_03 4N DX-cooled template end-to-end (pull repo, run Dymola batch simulation, archive plots/results) at a standard suitable for Penn State AE research reviews and future publication packages.

2. **Prerequisites**
   - Windows workstation with Dymola 2024x Refresh 1 (64‑bit) licensed.
   - Git for cloning repositories; `core.longpaths` enabled (`git config --global core.longpaths true`).
   - Python 3.12+ with `pip install numpy matplotlib buildingspy dymat`.
   - Disk layout used herein (adjust if different):  
     `C:/Users/mlm7685/OneDrive - The Pennsylvania State University/Desktop/mlm_buildingspy_workflow/`

3. **Repository Linking**
   1. Clone the template repo:  
      `git clone https://github.com/mlm7685psu/mo_03_Data-Center_DX-cooled_without_ASE_4N.git`
   2. Pull latest before every run:  
      `git pull origin main`
   3. Clone the Buildings library (release 12.0.0) beside the template so Dymola can load it without path gymnastics:  
      `git clone --depth 1 --branch v12.0.0 https://github.com/lbl-srg/modelica-buildings.git Buildings`

4. **Batch Simulation Script (`simulate_crac_dx.mos`)**
   - Location: `mo_03_Data-Center_DX-cooled_without_ASE_4N/simulate_crac_dx.mos`
   - Responsibilities:
     1. Loads `Modelica` and the cloned `Buildings` library.
     2. Opens `mo_03_dc_woase_n4.mo`.
     3. Runs `mo_03_dc_woase_n4.CRAC_DXwoASE.CRAC_dx` from 0–86400 s with Dassl, `tol = 1e-6`, storing results in `results/CRAC_dx_res.mat`.
   - Run command (PowerShell, repository root as working directory):
     ```
     & 'C:\Program Files\Dymola 2024x Refresh 1\bin64\Dymola.exe' scripts/simulate_crac_dx.mos
     ```
   - Monitor `dslog.txt` for completion notice:  
     `Simulation finished. Results stored at ...\results\CRAC_dx_res.mat`

5. **Result Management**
   1. Raw Dymola artifacts land in `mo_03_Data-Center_DX-cooled_without_ASE_4N/results/`.
   2. Archive the `.mat`, `.log`, and `simulate_crac_dx.mos` hash in Git for traceability (never commit temporary `ds*` files larger than needed).
   3. Record metadata (git commit SHA for both template and Buildings library, Dymola build, simulation timestamp) inside your engineering log.

6. **Plotting & KPI Extraction**
   - **Option A – Dymola GUI**: Open `results/CRAC_dx_res.mat`, overlay `TRoo`, `TSup`, fan/compressor speeds, and coil load signals highlighted in README.md validation checklist.
   - **Option B – Python automation** (preferred for reproducibility):
     ```python
     import pathlib
     import matplotlib.pyplot as plt
     from buildingspy.io.outputfile import Reader

     repo = pathlib.Path(r"C:/Users/mlm7685/.../mlm_buildingspy_workflow")
     result = repo / "mo_03_Data-Center_DX-cooled_without_ASE_4N" / "results" / "CRAC_dx_res.mat"
     rdr = Reader(str(result), "dymola")

     t = rdr.time()
     TRoo = rdr.interpolate("mo_03_dc_woase_n4.CRAC_DXwoASE.CRAC_dx.roo.T")
     TSup = rdr.interpolate("mo_03_dc_woase_n4.CRAC_DXwoASE.CRAC_dx.global_senTemSupplyAIr.T")

     plt.plot(t/3600, TRoo-273.15, label="Room Air (°C)")
     plt.plot(t/3600, TSup-273.15, label="Supply Air (°C)")
     plt.xlabel("Time [h]")
     plt.ylabel("Temperature [°C]")
     plt.legend()
     plt.grid()
     plt.tight_layout()
     plt.savefig(result.with_suffix("_temps.png"), dpi=300)
     ```
   - Extend the script with compressor/fan speed KPIs, energy integrals, and any sensitivity scans needed for paper figures.

7. **Verification Checklist (aligns with README.dev.md §4)**
   1. Model loads with zero errors/warnings beyond expected IBPSA notices.
   2. Simulation reaches 86400 s without event chattering.
   3. Room temperature tracks 24 °C ±0.5 K; supply air 18 °C ±0.3 K.
   4. Fans stay within `minSpeFan`–100 %; compressor stages follow expected sequence.
   5. Plots and KPI tables exported to `docs/figures` with source CSVs.

8. **Next Actions**
   1. Automate post-processing into a reproducible Python notebook or CLI.
   2. Wire this workflow into CI (optional) once licensing constraints are resolved.
   3. Mirror results + plots into the engineering notebook for Dr. Zuo review packages.

9. **JSON-Driven Automation (`main.py`, `main.json`)**
   1. Input parameters live in `main.json`. Each object under `runs` defines `run_id`, `template`, stop time, solver settings, and the target results directory.
   2. Execute all runs: `python main.py` (defaults to `main.json`). Execute a single run: `python main.py --run-id mo03_baseline`.
   3. The script renders a MOS file per run in `automation/generated_mos/`, launches Dymola headlessly, and drops results in `runs/<run_id>/<run_id>.mat`.
   4. Customize the Dymola executable path either in `main.json` (`dymola_exe`) or ad-hoc via `python main.py --dymola-exe "D:/Apps/Dymola/bin64/Dymola.exe"`.
   5. Extend each run entry with future `plot_signals` or KPI definitions—`main.py` already parses them for downstream processing hooks.
