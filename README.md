# pandora-calibration-tools

Standalone tools for producing Pandora theta-energy calibration payloads and diagnostic plots for the MAIA reconstruction workflow.

Two MAIA software versions are supported. They differ in how the tables are applied during reconstruction

| | v3+ (Gaudi, EDM4hep) | v2.11 (Marlin, LCIO) |
| --- | --- | --- |
| Pandora interface | `key4hep/k4GaudiPandora` (PR #51, on `main`; not yet in a release) | `trholmes/DDMarlinPandora`: `codex/photon-em-theta-energy` |
| LCContent | `PandoraPFAOrg/LCContent` `v05-01-00` or later (PRs #41 and #47) | `trholmes/LCContent`: `codex/photon-em-nonlinearity` |
| Steering | `MuonColliderSoft/MAIAConfig` (PR #37, on `main`; not yet in a release), `reco_steer.py` | `trholmes/SteeringMacros`: `codex/photon-em-steering`, `steer_reco.py` |
| How a table reaches Pandora | the table JSON file itself | a "payload" made by `build_theta_energy_steering_payload.py` |

The logical workflow is:

1. Use reconstructed single-particle samples to create calibration factors with this repository.
2. Apply those calibrations during reconstruction with the runtime code above:
   - v3+: pass the table files to `reco_steer.py` with `--pandoraCalibration`
   - v2.11: convert the tables to payloads and pass them to `steer_reco.py`.
3. Use switches in the Pandora settings XML to control whether corrected energies are used in selected internal decisions, such as ConeBasedMerging track comparisons and `LCElectronId` E/p. The switch names differ between the two versions (see [XML Switches](#xml-switches)).

Default training inputs are cluster-based `PandoraClusters` from reco files, either EDM4hep (`.edm4hep.root`, from `k4run` with k4GaudiPandora) or LCIO (`.slcio`, from Marlin). See [Input Formats](#input-formats). The scripts use `cluster.getSubdetectorEnergies()` with:

- ECAL subdetector index: `0`
- HCAL subdetector index: `1`

Examples below use one consistent EM sample and one consistent hadronic sample:

- EM/photon sample: `photonGun_E_0_50`
- hadronic sample: `neutronGun_E_0_50`

## What This Workflow Covers

This repository provides the scripts and documentation for:

1. Photon/ECAL EM theta-energy calibration.
2. Branch-summed hadronic theta-energy calibration using ECAL+HCAL on the Pandora HAD scale.
3. DDMarlinPandora steering payload generation (v2.11 only).
4. Closure and shower-profile diagnostic plots.

The matching runtime code lives in the repositories listed above. In particular:

- `LCContent` implements the theta-energy nonlinearity plugin and configurable corrected-energy use in selected comparisons.
- v3+: `k4GaudiPandora` reads the table JSON files (properties `ElectromagneticThetaEnergyCorrectionFile`, `HadronicThetaEnergyCorrectionFile`) and registers the plugins. `MAIAConfig` adds the plugin names and track-comparison switches to the Pandora settings XML at run time and sets the flat calibration constants the tables were trained with.
- v2.11: `DDMarlinPandora` exposes calibration payload parameters and registers the plugins. `SteeringMacros` enables the plugin names in Pandora XML and loads payload JSON files from `steer_reco.py`.

## Repository Contents

- `scripts/make_ecal_theta_energy_calibration.py`: build photon/ECAL EM calibration tables.
- `scripts/make_hcal_theta_energy_calibration.py`: build hadronic calibration tables.
- `scripts/validate_theta_energy_calibration.py`: closure plots and summaries.
- `scripts/build_theta_energy_steering_payload.py`: convert calibration tables to `DDMarlinPandora.Parameters` payloads (v2.11 only; v3+ reads the table JSON directly).
- `scripts/plot_shower_profile_diagnostics.py`: plot `showerProfileStart` and `showerProfileDiscrepancy` diagnostics.
- `scripts/calibration_lib.py`: shared utilities.
- `config/example_ecal_calibration_config.txt`: example ECAL command config.
- `config/example_hcal_calibration_config.txt`: example hadronic command config.
- `docs/theta_energy_cluster_calibration_spec.md`: implementation/spec notes.

## Runtime Requirements

- MAIA software environment: `v3+` (EDM4hep reco files) or `v2.11` (LCIO reco files).
- Python 3.8+.
- `podio` (EDM4hep input, v3+) or `pyLCIO` (LCIO input, v2.11) for calibration-table production.
- `matplotlib` for `plot_shower_profile_diagnostics.py`.
- Reco inputs (`.edm4hep.root` or `.slcio`) for `photonGun_E_0_50` and `neutronGun_E_0_50`.
- Writable output directory, normally `calib/`.

## Input Formats

`make_ecal_theta_energy_calibration.py`, `make_hcal_theta_energy_calibration.py` and
`validate_theta_energy_calibration.py` read either format. The relevant options are:

| Option | Default | Meaning |
| --- | --- | --- |
| `--input-format` | `auto` | `edm4hep`, `lcio`, or `auto`. `auto` decides from the file extensions: `.root` is EDM4hep, `.slcio` is LCIO. All files in one input list must have the same format. |
| `--file-glob` | depends on format | Pattern used to find files inside directory inputs: `*.edm4hep.root` for EDM4hep, `*.slcio` for LCIO, both for `auto`. |
| `--mc-collection` | depends on format | `MCParticles` for EDM4hep, `MCParticle` for LCIO. Samples with BIB overlay may use another name (e.g. `NewMCParticles`). |

The cluster quantities are the same in both formats: k4GaudiPandora's `DDPfoCreator` and DDMarlinPandora both
fill the cluster subdetector energies with the summed calorimeter-hit energy per subdetector (ECAL index `0`,
HCAL index `1`), and both write the clusters to `PandoraClusters`. The input format and MC collection that were
used are recorded in each table's `metadata` (`input_format`, `mc_collection`).

## Set Up (v3+, Gaudi)

Run everything inside the MAIA `v3+` image (e.g. `mucoll-sim-ubuntu24:v3.1`) after `source /opt/setup_mucoll.sh`.

Applying the tables needs LCContent `v05-01-00` or later and a k4GaudiPandora that contains PR #51. PR #51 is on
`key4hep/k4GaudiPandora` `main` but not yet in a tagged release, so unless your image already contains it, build
both locally:

```bash
export MUCOL_BASE=/path/to/work/area
cd "${MUCOL_BASE}"
git clone https://github.com/PandoraPFAOrg/LCContent.git
git clone https://github.com/key4hep/k4GaudiPandora.git
git clone https://github.com/MuonColliderSoft/MAIAConfig.git
git clone https://github.com/<you>/pandora-calibration-tools.git

cd "${MUCOL_BASE}/LCContent" && git checkout v05-01-01
mkdir -p build install && cd build
cmake .. -DCMAKE_INSTALL_PREFIX="${MUCOL_BASE}/LCContent/install"
cmake --build . -j"$(nproc)" && cmake --install .

cd "${MUCOL_BASE}/k4GaudiPandora"
mkdir -p build install && cd build
cmake .. -DCMAKE_INSTALL_PREFIX="${MUCOL_BASE}/k4GaudiPandora/install" \
  -DLCContent_DIR="${MUCOL_BASE}/LCContent/install/lib/cmake/LCContent"
cmake --build . -j"$(nproc)" && cmake --install .
```

In each new shell, put the local builds in front of the image's copies. Gaudi finds libraries through
`LD_LIBRARY_PATH` and algorithm configurations through `PYTHONPATH`; `MARLIN_DLL` is not used:

```bash
export LD_LIBRARY_PATH="${MUCOL_BASE}/LCContent/install/lib:${MUCOL_BASE}/k4GaudiPandora/install/lib:${LD_LIBRARY_PATH}"
export PYTHONPATH="${MUCOL_BASE}/k4GaudiPandora/install/python:${PYTHONPATH}"
```

Use a MAIAConfig that contains PR #37 (`main`; not yet in a tagged release), which provides `--pandoraCalibration`.

## Set Up From Scratch (v2.11, Marlin)

Use this for a clean checkout in a new `v2.11` area.

```bash
export MUCOL_BASE=/scratch/trholmes/mucol/v2.11
mkdir -p "${MUCOL_BASE}"
cd "${MUCOL_BASE}"
```

Clone the repositories:

```bash
git clone git@github.com:PandoraPFA/LCContent.git
git clone git@github.com:MuonColliderSoft/DDMarlinPandora.git
git clone https://github.com/madbaron/SteeringMacros.git
git clone git@github.com:trholmes/pandora-calibration-tools.git
```

Add the fork remotes and check out the working branches:

```bash
cd "${MUCOL_BASE}/LCContent"
git remote add trholmes git@github.com:trholmes/LCContent.git
git fetch trholmes codex/photon-em-nonlinearity
git checkout codex/photon-em-nonlinearity

cd "${MUCOL_BASE}/DDMarlinPandora"
git remote add trholmes git@github.com:trholmes/DDMarlinPandora.git
git fetch trholmes codex/photon-em-theta-energy
git checkout codex/photon-em-theta-energy

cd "${MUCOL_BASE}/SteeringMacros"
git remote add trholmes git@github.com:trholmes/SteeringMacros.git
git fetch trholmes codex/photon-em-steering
git checkout codex/photon-em-steering

cd "${MUCOL_BASE}/pandora-calibration-tools"
git fetch origin codex/photon-em-payload
git checkout codex/photon-em-payload
```

Build and install local `LCContent`:

```bash
cd "${MUCOL_BASE}/LCContent"
rm -rf build install
mkdir -p build install
cd build
cmake .. -DCMAKE_INSTALL_PREFIX="${MUCOL_BASE}/LCContent/install"
cmake --build . -j"$(nproc)"
cmake --install .
```

Build and install local `DDMarlinPandora` against that `LCContent`:

```bash
cd "${MUCOL_BASE}/DDMarlinPandora"
rm -rf build install
mkdir -p build install
cd build
cmake .. \
  -DCMAKE_INSTALL_PREFIX="${MUCOL_BASE}/DDMarlinPandora/install" \
  -DLCContent_DIR="${MUCOL_BASE}/LCContent/install/lib/cmake/LCContent"
cmake --build . -j"$(nproc)"
cmake --install .
```

Point runtime to the local builds before running `k4run`:

```bash
export LD_LIBRARY_PATH="${MUCOL_BASE}/LCContent/install/lib:${MUCOL_BASE}/DDMarlinPandora/install/lib:${LD_LIBRARY_PATH}"
export MARLIN_DLL="${MUCOL_BASE}/DDMarlinPandora/install/lib/libDDMarlinPandora.so:${MARLIN_DLL}"
```

Check that the local runtime is active:

```bash
echo "${LD_LIBRARY_PATH}" | tr ':' '\n' | head -n 5
echo "${MARLIN_DLL}" | tr ':' '\n' | head -n 10
```

## Set Up Upon Return (v2.11, Marlin)

Use this when coming back to an existing `v2.11` checkout.

```bash
export MUCOL_BASE=/scratch/trholmes/mucol/v2.11
```

Update the branches:

```bash
cd "${MUCOL_BASE}/LCContent"
git fetch trholmes codex/photon-em-nonlinearity
git checkout codex/photon-em-nonlinearity
git pull --ff-only trholmes codex/photon-em-nonlinearity

cd "${MUCOL_BASE}/DDMarlinPandora"
git fetch trholmes codex/photon-em-theta-energy
git checkout codex/photon-em-theta-energy
git pull --ff-only trholmes codex/photon-em-theta-energy

cd "${MUCOL_BASE}/SteeringMacros"
git fetch trholmes codex/photon-em-steering
git checkout codex/photon-em-steering
git pull --ff-only trholmes codex/photon-em-steering

cd "${MUCOL_BASE}/pandora-calibration-tools"
git fetch origin codex/photon-em-payload
git checkout codex/photon-em-payload
git pull --ff-only origin codex/photon-em-payload
```

Rebuild after `LCContent` or `DDMarlinPandora` changes:

```bash
cd "${MUCOL_BASE}/LCContent/build"
cmake --build . -j"$(nproc)"
cmake --install .

cd "${MUCOL_BASE}/DDMarlinPandora/build"
cmake --build . -j"$(nproc)"
cmake --install .
```

Re-export the local runtime libraries in each new shell:

```bash
export LD_LIBRARY_PATH="${MUCOL_BASE}/LCContent/install/lib:${MUCOL_BASE}/DDMarlinPandora/install/lib:${LD_LIBRARY_PATH}"
export MARLIN_DLL="${MUCOL_BASE}/DDMarlinPandora/install/lib/libDDMarlinPandora.so:${MARLIN_DLL}"
```

## Calibration Inputs And Conventions

The calibration scripts train on reconstructed clusters and compare to the matched generated particle energy.

The EM/photon table is trained in the Pandora EM energy basis:

```text
E_em_basis = raw_ecal_subdetector_energy * ECalToEMGeVCalibration
```

The first-pass hadronic table is trained in a branch-summed Pandora HAD energy basis:

```text
E_had_basis = raw_ecal_subdetector_energy * ECalToHadGeVCalibration
            + raw_hcal_subdetector_energy * HCalToHadGeVCalibration
```

This is why the examples below explicitly pass the flat ECAL/HCAL calibration constants. They make the table training basis match the basis where the Pandora runtime correction is applied.

The values passed to the calibration scripts must match the values used in the reconstruction where the table will be applied. Use the same values in the reconstruction that produces the training samples as well: the subdetector energies the scripts read do not depend on them, but the `--ecal-fraction-min` / `--hcal-fraction-min` cuts divide by Pandora's calibrated cluster energy, which does.

Where the values are set:

- v3+: `MAIAConfig/ParticleFlow/pandora.py` holds the defaults (`ECalToHadGeVCalibration* = 1.371`, `HCalToHadGeVCalibration = 0.902`). When `--pandoraCalibration` is given, `MAIAConfig/Common/pandora_calibration.py` replaces them, for each branch that has a table, with the values in `CALIBRATED_PANDORA_CONSTANTS` (the values below). It also stops the job if a table's `metadata` records different values. To calibrate with other values, change `CALIBRATED_PANDORA_CONSTANTS` and pass the same values to the scripts.
- v2.11: `SteeringMacros/k4Reco/steer_reco.py`.

The values in both cases are:

| Steering parameter | Current value | Calibration-script argument |
| --- | --- | --- |
| `ECalToEMGeVCalibration` | `1.02373335516` | `--ecal-to-em-gev 1.02373335516` |
| `ECalToHadGeVCalibrationBarrel` | `1.38` | `--ecal-to-had-gev 1.38` |
| `ECalToHadGeVCalibrationEndCap` | `1.38` | `--ecal-to-had-gev 1.38` |
| `HCalToHadGeVCalibration` | `1.25` | `--hcal-to-had-gev 1.25` |

Do not treat these as universal detector constants. If the steering changes, update the calibration commands and regenerate the tables. A mismatch double-counts or under-counts a flat scale factor: the table is trained in one energy basis, while Pandora applies it in another.

Software compensation must be off in the reconstruction where the hadronic table is applied. The hadronic table plugin runs after `SoftwareCompensation` in the hadronic correction chain, and the table is trained on energies without software compensation (the scripts compute the energy from the subdetector sums and the flat constants only). In v3+, MAIAConfig turns it off (`MaxClusterEnergyToApplySoftComp = 0`) whenever a hadronic table is given.

The current hadronic script uses one ECAL-to-HAD value for both barrel and endcap, so the barrel and endcap values in steering should be identical for this workflow. If they are changed independently later, the calibration script or sample splitting should be updated before producing new hadronic payloads.

## End-To-End Calibration Workflow

Prepare output directories:

```bash
cd "${MUCOL_BASE}/pandora-calibration-tools"
mkdir -p calib calib/plots
```

### 1. Build The Photon/ECAL EM Table

```bash
python3 scripts/make_ecal_theta_energy_calibration.py \
  --inputs /scratch/trholmes/mucol/data/reco/photonGun_E_0_50 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --ecal-fraction-min 0.7 \
  --energy-basis em \
  --ecal-to-em-gev 1.02373335516 \
  --theta-bins 0,0.35,0.7,1.05,1.4,1.75,2.1,2.45,2.8,3.14159 \
  --energy-bins 0,5,10,20,50,100,200,500,1000,5000 \
  --pdg-ids 22 \
  --output calib/ecal_theta_energy_calib.json
```

### 2. Build The Hadronic Branch Table

```bash
python3 scripts/make_hcal_theta_energy_calibration.py \
  --inputs /scratch/trholmes/mucol/data/reco/neutronGun_E_0_50 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --hcal-fraction-min 0.1 \
  --energy-basis hadronic \
  --ecal-to-had-gev 1.38 \
  --hcal-to-had-gev 1.25 \
  --theta-bins 0,0.35,0.7,1.05,1.4,1.75,2.1,2.45,2.8,3.14159 \
  --energy-bins 0,5,10,20,50,100,200,500,1000,5000 \
  --pdg-ids 2112,211,111 \
  --output calib/hadronic_theta_energy_calib.json
```

### 3. Validate Closure

Validate the photon/ECAL table:

```bash
python3 scripts/validate_theta_energy_calibration.py \
  --ecal-inputs /scratch/trholmes/mucol/data/reco/photonGun_E_0_50 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --ecal-calibration calib/ecal_theta_energy_calib.json \
  --plot-dir calib/plots \
  --output calib/ecal_closure_summary.json
```

Validate the first-pass hadronic branch table:

```bash
python3 scripts/validate_theta_energy_calibration.py \
  --hcal-inputs /scratch/trholmes/mucol/data/reco/neutronGun_E_0_50 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --hadronic-calibration calib/hadronic_theta_energy_calib.json \
  --plot-dir calib/plots \
  --output calib/hadronic_closure_summary.json
```

The validation scripts write quick-look maps and theta profiles to `calib/plots`.

### 4. Build Steering Payloads (v2.11 only)

Skip this step for v3+: k4GaudiPandora reads the table JSON files directly.

Build the photon EM runtime payload:

```bash
python3 scripts/build_theta_energy_steering_payload.py \
  --photon-em-calibration calib/ecal_theta_energy_calib.json \
  --output-json calib/photon_em_calib_payload.json
```

Build the hadronic runtime payload:

```bash
python3 scripts/build_theta_energy_steering_payload.py \
  --hadronic-calibration calib/hadronic_theta_energy_calib.json \
  --output-json calib/hadronic_calib_payload.json
```

## Run Reconstruction (v3+)

Pass the table files to MAIAConfig's `reco_steer.py` (or `digi_reco_steer.py`) as a comma-separated list. Each file
is sent to the EM or hadronic branch according to its `metadata.energy_basis`:

```bash
k4run reco_steer.py --inputFiles digi.edm4hep.root --outputFile reco.edm4hep.root \
  --pandoraCalibration "${MUCOL_BASE}/pandora-calibration-tools/calib/ecal_theta_energy_calib.json,${MUCOL_BASE}/pandora-calibration-tools/calib/hadronic_theta_energy_calib.json"
```

Giving one file applies only that branch. `--pandoraCalibration default` uses the tables shipped in
`MAIAConfig/Calibration/`. A bare file name (no directory) is looked up first in that directory, or in
`MAIA_PANDORA_CALIBRATION_DIR` if set. With `--pandoraCalibration`, MAIAConfig also:

- appends `PhotonEMNonLinearity` / `HadronicThetaEnergyBinned` to the plugin lists of whichever Pandora settings XML is used,
- sets the flat constants and turns off software compensation (see [Calibration Inputs And Conventions](#calibration-inputs-and-conventions)),
- for a hadronic table, adds `UseThetaEnergyCorrectionForTrackComparison` and `ThetaEnergyCorrectionName` to `ProximityBasedMerging` and `ConeBasedMerging`, unless the XML already sets `UseThetaEnergyCorrectionForTrackComparison`. If the XML has no `ProximityBasedMerging` or no `ConeBasedMerging` algorithm (e.g. a perfect-clustering XML), the job stops with an error.

Without `--pandoraCalibration`, reconstruction is unchanged.

## Run Reconstruction With Payloads (v2.11)

Photon EM test:

```bash
k4run "${MUCOL_BASE}/SteeringMacros/k4Reco/steer_reco.py" \
  --code "${MUCOL_BASE}" \
  --data "${MUCOL_BASE}" \
  --TypeEvent photonGun_E_0_50 \
  --InFileName 0 \
  --photonEMCalibPayload "${MUCOL_BASE}/pandora-calibration-tools/calib/photon_em_calib_payload.json"
```

Hadronic branch test:

```bash
k4run "${MUCOL_BASE}/SteeringMacros/k4Reco/steer_reco.py" \
  --code "${MUCOL_BASE}" \
  --data "${MUCOL_BASE}" \
  --TypeEvent neutronGun_E_0_50 \
  --InFileName 0 \
  --hadronicCalibPayload "${MUCOL_BASE}/pandora-calibration-tools/calib/hadronic_calib_payload.json"
```

Combined photon/hadronic payload test:

```bash
k4run "${MUCOL_BASE}/SteeringMacros/k4Reco/steer_reco.py" \
  --code "${MUCOL_BASE}" \
  --data "${MUCOL_BASE}" \
  --TypeEvent photonGun_E_0_50 \
  --InFileName 0 \
  --photonEMCalibPayload "${MUCOL_BASE}/pandora-calibration-tools/calib/photon_em_calib_payload.json" \
  --hadronicCalibPayload "${MUCOL_BASE}/pandora-calibration-tools/calib/hadronic_calib_payload.json"
```

## Payloads And Runtime Switches

There are two separate runtime controls:

1. Loading the tables into the Pandora correction plugins: v3+ with `--pandoraCalibration` (see [Run Reconstruction (v3+)](#run-reconstruction-v3)); v2.11 with payload arguments to `steer_reco.py`.
2. XML switches in the Pandora settings XML decide whether selected internal comparisons use corrected energies instead of the nominal cluster energies.

Loading a table changes the corrected-energy value returned by Pandora. It does not automatically make every internal algorithm use that corrected energy. The XML switches below opt specific decisions into using corrected energies.

If a switch is turned on without the matching table, the correction plugin is still registered but has no correction table, so `GetCorrectedElectromagneticEnergy(...)` and `GetCorrectedHadronicEnergy(...)` return the energy without this correction. In v3+, `ProximityBasedMerging` and `ConeBasedMerging` additionally print a one-time warning that no theta-energy correction is registered under `ThetaEnergyCorrectionName`. If the runtime code is not built or the plugin names in XML are missing from the loaded `LCContent`, Pandora can still fail at initialization.

### Payload Arguments (v2.11)

```bash
--photonEMCalibPayload calib/photon_em_calib_payload.json
```

Loads the EM theta-energy table and enables the `PhotonEMNonLinearity` electromagnetic correction plugin. This affects corrected EM energies and final photon/EM energy assignment, and it is used by internal comparisons only where an EM corrected-energy switch is enabled.

```bash
--hadronicCalibPayload calib/hadronic_calib_payload.json
```

Loads the hadronic theta-energy table and enables the `HadronicThetaEnergyBinned` hadronic correction plugin. This affects corrected HAD energies and final hadronic energy assignment, and it is used by internal comparisons only where a HAD corrected-energy switch is enabled.

### XML Switches

All switches default to `false` in LCContent. Set only the specific comparisons you want to test to `true`. The switch names differ between the upstream LCContent used in v3+ and the `trholmes/LCContent` branch used in v2.11.

#### v3+ (upstream LCContent `v05-01-00` or later)

| XML location | Switch | Effect when `true` |
| --- | --- | --- |
| `ProximityBasedMerging` | `UseThetaEnergyCorrectionForTrackComparison`, with `ThetaEnergyCorrectionName` set to the hadronic plugin name (`HadronicThetaEnergyBinned`) | The track-cluster chi checks multiply the parent and merged-candidate hadronic energies by the table factor, evaluated at the parent cluster's direction and at each of the two energies. Setting the switch without `ThetaEnergyCorrectionName` stops Pandora at initialization. |
| `ConeBasedMerging` | same two settings | Same as above, for the cone-merging chi checks. |
| `TrackClusterAssociation` (nested inside the merging algorithms, or in `TrackPreparation/trackClusterAssociationAlgorithms`) | `UseCorrectedEnergyForTrackComparison` | The association energy tie-break uses `Cluster::GetTrackComparisonEnergy`: the corrected electromagnetic energy if the particle-ID plugin identifies the cluster as an EM shower, otherwise the corrected hadronic energy. Distance remains the primary comparison. |
| `LCElectronId` | `UseCorrectedElectromagneticEnergyForEOverP` | The electron-ID E/p comparison uses corrected electromagnetic energy. Fast profile and preselection cuts remain unchanged. |

Because the merging-algorithm and nested-association switches have different names in v3+, the scope ambiguity described for v2.11 below does not arise.

#### v2.11 (`trholmes/LCContent` `codex/photon-em-nonlinearity`)

| XML location | Switch | Effect when `true` |
| --- | --- | --- |
| `ProximityBasedMerging` | `UseCorrectedHadronicEnergyForTrackComparison` | The proximity-merging track-cluster chi checks use corrected parent and merged-candidate hadronic energies. |
| `ConeBasedMerging` | `UseCorrectedHadronicEnergyForTrackComparison` | The cone-merging track-cluster chi checks use corrected parent and merged-candidate hadronic energies. |
| nested `TrackClusterAssociation` inside `ProximityBasedMerging` | `UseCorrectedHadronicEnergyForTrackComparison` | The association energy tie-break uses corrected hadronic energy. Distance remains the primary comparison. |
| nested `TrackClusterAssociation` inside `ConeBasedMerging` | `UseCorrectedHadronicEnergyForTrackComparison` | The association energy tie-break uses corrected hadronic energy. Distance remains the primary comparison. |
| `TrackPreparation/trackClusterAssociationAlgorithms/TrackClusterAssociation` | `UseCorrectedHadronicEnergyForTrackComparison` | The final track-cluster association energy tie-break uses corrected hadronic energy. Distance remains the primary comparison. |
| `LCElectronId` | `UseCorrectedElectromagneticEnergyForEOverP` | The electron-ID E/p comparison uses corrected electromagnetic energy. Fast profile and preselection cuts remain unchanged. |

In v2.11 the hadronic switch name is reused in different XML scopes. For example, this turns on the `TrackClusterAssociation` tie-break inside `ConeBasedMerging`, not the `ConeBasedMerging` chi checks:

```xml
<algorithm type = "ConeBasedMerging">
    <algorithm type = "TrackClusterAssociation">
        <UseCorrectedHadronicEnergyForTrackComparison>true</UseCorrectedHadronicEnergyForTrackComparison>
    </algorithm>
    <UseCorrectedHadronicEnergyForTrackComparison>false</UseCorrectedHadronicEnergyForTrackComparison>
</algorithm>
```

This turns on the `ConeBasedMerging` chi checks, not the nested association tie-break:

```xml
<algorithm type = "ConeBasedMerging">
    <algorithm type = "TrackClusterAssociation">
        <UseCorrectedHadronicEnergyForTrackComparison>false</UseCorrectedHadronicEnergyForTrackComparison>
    </algorithm>
    <UseCorrectedHadronicEnergyForTrackComparison>true</UseCorrectedHadronicEnergyForTrackComparison>
</algorithm>
```

## Shower-Profile Diagnostics

`scripts/plot_shower_profile_diagnostics.py` plots `showerProfileStart` and `showerProfileDiscrepancy` with the current `LCElectronId` cuts overlaid:

```bash
python3 scripts/plot_shower_profile_diagnostics.py reco.log \
  --format dump-pfos-log \
  --output-dir calib/shower_profile_diagnostics
```

This log-parsing mode reads neutral PFO rows printed by `DumpPfosMonitoringAlgorithm`, where the columns are labelled `sStart` and `sDisc`. Charged PFO rows do not currently print these quantities. For electron-specific studies, either add those columns to the monitoring output or provide a CSV with columns:

```text
energy,sStart,sDisc,theta,label
```

`theta` and `label` are optional. The script writes:

- `shower_profile_vs_energy.png`
- `shower_profile_distributions.png`
- `shower_profile_vs_theta.png` when `theta` is present
- `shower_profile_summary.txt`

## Troubleshooting

1. `pyLCIO is required ...` or `podio is required ...`
   Source the MAIA / Key4hep software environment before running the calibration scripts.

2. `No input files found`
   Check the sample path and add `--recursive` if files are in nested directories.

3. `LCContent_DIR` not found
   Check that `${MUCOL_BASE}/LCContent/install/lib/cmake/LCContent` exists after installing `LCContent`.

4. Local changes do not appear in the `k4run` log
   - v3+: re-export `LD_LIBRARY_PATH` and `PYTHONPATH` (see [Set Up (v3+, Gaudi)](#set-up-v3-gaudi)). The k4GaudiPandora log line `Read electromagnetic theta-energy calibration from ...` (or `hadronic`) confirms that a table was loaded.
   - v2.11: re-export `LD_LIBRARY_PATH` and `MARLIN_DLL`, then check that `MARLIN_DLL` points at `${MUCOL_BASE}/DDMarlinPandora/install/lib/libDDMarlinPandora.so`.

5. Too many calibration bins have scale `1.0`
   Increase statistics, reduce bin granularity, or lower the minimum-bin threshold.

6. Cluster subdetector split is unavailable
   With `--skip-missing-subdet-split`, such events are counted in `events_skipped_split` in the table metadata. Without it, the event gets ECAL and HCAL energies of 0 and is dropped by the fraction cut or the energy > 0 check, without an error. Compare `events_used` with `events_total`, or temporarily switch to hit-based energy inputs (`--energy-source hits`) for debugging.

7. v3+: `The Pandora settings XML has no ProximityBasedMerging algorithm ...`
   MAIAConfig stops when a hadronic table is given and the Pandora settings XML lacks `ProximityBasedMerging` or `ConeBasedMerging` (e.g. a perfect-clustering XML). Remove those names from `_TRACK_COMPARISON_ALGORITHMS` in `MAIAConfig/Common/pandora_settings.py`, or add the algorithms to the XML.
