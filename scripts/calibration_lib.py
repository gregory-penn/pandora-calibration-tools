#!/usr/bin/env python3
"""Shared utilities for ECAL/HCAL theta-energy calibration production."""

from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import math
import os
from typing import Iterable, List, Sequence, Tuple


def parse_float_list(value: str) -> List[float]:
    if not value.strip():
        return []
    return [float(x.strip()) for x in value.split(",") if x.strip()]


def parse_int_list(value: str) -> List[int]:
    if not value.strip():
        return []
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def ensure_strictly_increasing(values: Sequence[float], name: str) -> None:
    if len(values) < 2:
        raise ValueError(f"{name} must contain at least two edges")
    for i in range(1, len(values)):
        if values[i] <= values[i - 1]:
            raise ValueError(f"{name} must be strictly increasing; failed at index {i}")


def find_bin(edges: Sequence[float], value: float) -> int:
    """Find bin index in [0, len(edges)-2], return -1 for under/overflow."""
    if value < edges[0] or value >= edges[-1]:
        return -1
    for i in range(len(edges) - 1):
        if edges[i] <= value < edges[i + 1]:
            return i
    return -1


def flatten_index(i_theta: int, i_energy: int, n_energy_bins: int) -> int:
    return i_theta * n_energy_bins + i_energy


def expand_input_paths(inputs: Sequence[str], file_glob: str, recursive: bool = False) -> List[str]:
    files: List[str] = []

    def add_from_directory(directory: str) -> None:
        pattern = os.path.join(directory, "**", file_glob) if recursive else os.path.join(directory, file_glob)
        files.extend(glob.glob(pattern, recursive=recursive))

    for item in inputs:
        if any(c in item for c in "*?[]"):
            matches = glob.glob(item)
            for m in matches:
                if os.path.isdir(m):
                    add_from_directory(m)
                elif os.path.isfile(m):
                    files.append(m)
            continue
        if os.path.isdir(item):
            add_from_directory(item)
            continue
        if os.path.isfile(item):
            files.append(item)
    files = sorted(set([f for f in files if os.path.isfile(f)]))
    return files


def robust_estimate(values: Sequence[float], estimator: str, trim_fraction: float) -> float:
    if not values:
        return 1.0
    if estimator == "mean":
        return sum(values) / float(len(values))
    sorted_values = sorted(values)
    if estimator == "median":
        n = len(sorted_values)
        mid = n // 2
        if n % 2:
            return sorted_values[mid]
        return 0.5 * (sorted_values[mid - 1] + sorted_values[mid])
    if estimator == "trimmed_mean":
        n = len(sorted_values)
        trim = int(n * trim_fraction)
        lo = min(trim, n - 1)
        hi = max(lo + 1, n - trim)
        trimmed = sorted_values[lo:hi]
        return sum(trimmed) / float(len(trimmed))
    raise ValueError(f"Unknown estimator: {estimator}")


@dataclasses.dataclass
class CalibrationTable:
    domain: str
    theta_edges: List[float]
    energy_edges: List[float]
    scales: List[float]
    counts: List[int]
    metadata: dict

    def validate(self) -> None:
        ensure_strictly_increasing(self.theta_edges, "theta_edges")
        ensure_strictly_increasing(self.energy_edges, "energy_edges")
        n_theta = len(self.theta_edges) - 1
        n_energy = len(self.energy_edges) - 1
        expected = n_theta * n_energy
        if len(self.scales) != expected:
            raise ValueError(f"scales size {len(self.scales)} does not match expected {expected}")
        if len(self.counts) != expected:
            raise ValueError(f"counts size {len(self.counts)} does not match expected {expected}")

    def lookup(self, theta: float, energy: float) -> float:
        i_theta = find_bin(self.theta_edges, theta)
        i_energy = find_bin(self.energy_edges, energy)
        if i_theta < 0 or i_energy < 0:
            return 1.0
        n_energy = len(self.energy_edges) - 1
        return self.scales[flatten_index(i_theta, i_energy, n_energy)]

    def to_json_dict(self) -> dict:
        return dataclasses.asdict(self)

    @staticmethod
    def from_json_dict(data: dict) -> "CalibrationTable":
        table = CalibrationTable(
            domain=data["domain"],
            theta_edges=list(data["theta_edges"]),
            energy_edges=list(data["energy_edges"]),
            scales=list(data["scales"]),
            counts=list(data.get("counts", [0] * len(data["scales"]))),
            metadata=dict(data.get("metadata", {})),
        )
        table.validate()
        return table


def save_table_json(table: CalibrationTable, output_path: str) -> None:
    table.validate()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(table.to_json_dict(), f, indent=2, sort_keys=True)


def load_table_json(path: str) -> CalibrationTable:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CalibrationTable.from_json_dict(data)


def get_ecal_table_energy(table: CalibrationTable, raw_ecal_energy: float) -> float:
    basis = str(table.metadata.get("energy_basis", "raw")).lower()
    if basis == "raw":
        return raw_ecal_energy
    if basis == "em":
        return raw_ecal_energy * float(table.metadata.get("ecal_to_em_gev", 1.0))
    raise ValueError(f"Unsupported ECAL calibration energy_basis: {basis}")


def apply_ecal_calibration(table: CalibrationTable, theta: float, raw_ecal_energy: float) -> float:
    table_energy = get_ecal_table_energy(table, raw_ecal_energy)
    return table.lookup(theta, table_energy) * table_energy


def get_hadronic_table_energy(table: CalibrationTable, raw_ecal_energy: float, raw_hcal_energy: float) -> float:
    basis = str(table.metadata.get("energy_basis", "raw")).lower()
    if basis != "hadronic":
        raise ValueError(f"Unsupported hadronic calibration energy_basis: {basis}")
    ecal_to_had = float(table.metadata.get("ecal_to_had_gev", 1.0))
    hcal_to_had = float(table.metadata.get("hcal_to_had_gev", 1.0))
    return raw_ecal_energy * ecal_to_had + raw_hcal_energy * hcal_to_had


def apply_hadronic_calibration(table: CalibrationTable, theta: float, raw_ecal_energy: float, raw_hcal_energy: float) -> float:
    table_energy = get_hadronic_table_energy(table, raw_ecal_energy, raw_hcal_energy)
    return table.lookup(theta, table_energy) * table_energy


def _fmt_float(x: float) -> str:
    return f"{x:.8g}"


def table_to_ddmarlin_params(table: CalibrationTable) -> dict:
    """Return one-domain DDMarlin steering parameters as string vectors."""
    prefix = "ECal" if table.domain.upper() == "ECAL" else "HCal"
    return {
        f"{prefix}ThetaEnergyCorrectionThetaBinEdges": [_fmt_float(x) for x in table.theta_edges],
        f"{prefix}ThetaEnergyCorrectionEnergyBinEdges": [_fmt_float(x) for x in table.energy_edges],
        f"{prefix}ThetaEnergyCorrectionScaleFactors": [_fmt_float(x) for x in table.scales],
    }


def combine_ddmarlin_params(ecal_table: CalibrationTable, hcal_table: CalibrationTable, plugin_name: str = "ThetaEnergyBinned") -> dict:
    params = {
        "ThetaEnergyCorrectionEnabled": ["true"],
        "ThetaEnergyCorrectionPluginName": [plugin_name],
    }
    params.update(table_to_ddmarlin_params(ecal_table))
    params.update(table_to_ddmarlin_params(hcal_table))
    return params


def build_photon_em_ddmarlin_params(
    em_table: CalibrationTable,
    plugin_name: str = "PhotonEMNonLinearity",
) -> dict:
    if em_table.domain.upper() != "ECAL":
        raise ValueError(f"Photon EM payload expects ECAL-domain table, got {em_table.domain}")
    if str(em_table.metadata.get("energy_basis", "raw")).lower() != "em":
        raise ValueError("Photon EM payload expects an ECAL table built with --energy-basis em")

    return {
        "ElectromagneticThetaEnergyCorrectionEnabled": ["true"],
        "ElectromagneticThetaEnergyCorrectionPluginName": [plugin_name],
        "ElectromagneticThetaEnergyCorrectionThetaBinEdges": [_fmt_float(x) for x in em_table.theta_edges],
        "ElectromagneticThetaEnergyCorrectionEnergyBinEdges": [_fmt_float(x) for x in em_table.energy_edges],
        "ElectromagneticThetaEnergyCorrectionScaleFactors": [_fmt_float(x) for x in em_table.scales],
    }


def build_hadronic_ddmarlin_params(
    hadronic_table: CalibrationTable,
    plugin_name: str = "HadronicThetaEnergyBinned",
) -> dict:
    if hadronic_table.domain.upper() != "HADRONIC":
        raise ValueError(f"Hadronic payload expects HADRONIC-domain table, got {hadronic_table.domain}")
    if str(hadronic_table.metadata.get("energy_basis", "raw")).lower() != "hadronic":
        raise ValueError("Hadronic payload expects a table built with --energy-basis hadronic")

    return {
        "HadronicThetaEnergyCorrectionEnabled": ["true"],
        "HadronicThetaEnergyCorrectionPluginName": [plugin_name],
        "HadronicThetaEnergyCorrectionThetaBinEdges": [_fmt_float(x) for x in hadronic_table.theta_edges],
        "HadronicThetaEnergyCorrectionEnergyBinEdges": [_fmt_float(x) for x in hadronic_table.energy_edges],
        "HadronicThetaEnergyCorrectionScaleFactors": [_fmt_float(x) for x in hadronic_table.scales],
    }


def combine_branch_ddmarlin_params(
    ecal_table: CalibrationTable,
    hcal_table: CalibrationTable,
    branch: str,
    plugin_name: str = "ThetaEnergyBinned",
) -> dict:
    branch_key = branch.strip().lower()
    if branch_key == "hadronic":
        prefix = "Hadronic"
    elif branch_key == "electromagnetic":
        prefix = "Electromagnetic"
    else:
        raise ValueError(f"Unsupported branch: {branch}")

    return {
        f"{prefix}ThetaEnergyCorrectionEnabled": ["true"],
        f"{prefix}ThetaEnergyCorrectionPluginName": [plugin_name],
        f"{prefix}ECalThetaEnergyCorrectionThetaBinEdges": [_fmt_float(x) for x in ecal_table.theta_edges],
        f"{prefix}ECalThetaEnergyCorrectionEnergyBinEdges": [_fmt_float(x) for x in ecal_table.energy_edges],
        f"{prefix}ECalThetaEnergyCorrectionScaleFactors": [_fmt_float(x) for x in ecal_table.scales],
        f"{prefix}HCalThetaEnergyCorrectionThetaBinEdges": [_fmt_float(x) for x in hcal_table.theta_edges],
        f"{prefix}HCalThetaEnergyCorrectionEnergyBinEdges": [_fmt_float(x) for x in hcal_table.energy_edges],
        f"{prefix}HCalThetaEnergyCorrectionScaleFactors": [_fmt_float(x) for x in hcal_table.scales],
    }


INPUT_FORMATS = ("auto", "edm4hep", "lcio")

# Per-format defaults, used when --file-glob or --mc-collection is not given.
FORMAT_DEFAULTS = {
    "edm4hep": {"file_glob": "*.edm4hep.root", "mc_collection": "MCParticles"},
    "lcio": {"file_glob": "*.slcio", "mc_collection": "MCParticle"},
}


def add_input_format_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--input-format",
        choices=INPUT_FORMATS,
        default="auto",
        help="Input file format. 'auto' decides from the file extensions (.slcio = lcio, .root = edm4hep).",
    )


def detect_input_format(files: Sequence[str]) -> str:
    """Return 'lcio' or 'edm4hep' from the file extensions; all files must share one format."""
    formats = set()
    for fname in files:
        if fname.endswith(".slcio"):
            formats.add("lcio")
        elif fname.endswith(".root"):
            formats.add("edm4hep")
        else:
            raise RuntimeError(f"Cannot tell the format of {fname} from its extension; pass --input-format.")
    if len(formats) != 1:
        raise RuntimeError(f"Input files mix formats {sorted(formats)}; give one format per input list.")
    return formats.pop()


def resolve_input_files(
    inputs: Sequence[str], input_format: str, file_glob, recursive: bool
) -> Tuple[List[str], str]:
    """
    Expand the inputs into files and decide their format.

    Without --file-glob, directories are searched with the glob of the chosen format, or with
    both formats' globs when the format is 'auto'. Returns (files, format); the format is None
    when no files are found and the format is 'auto'.
    """
    if file_glob:
        files = expand_input_paths(inputs, file_glob, recursive=recursive)
    elif input_format != "auto":
        files = expand_input_paths(inputs, FORMAT_DEFAULTS[input_format]["file_glob"], recursive=recursive)
    else:
        files = sorted(
            set(
                f
                for defaults in FORMAT_DEFAULTS.values()
                for f in expand_input_paths(inputs, defaults["file_glob"], recursive=recursive)
            )
        )

    if input_format != "auto":
        return files, input_format
    if not files:
        return files, None
    return files, detect_input_format(files)


def resolve_mc_collection(mc_collection, input_format: str) -> str:
    """Return the requested MC collection name, or the default name for the input format."""
    if mc_collection:
        return mc_collection
    return FORMAT_DEFAULTS[input_format]["mc_collection"]


def setup_lcio_reader(collection_names: Sequence[str]):
    try:
        import pyLCIO  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pyLCIO is required but not available in this environment") from exc
    reader = pyLCIO.IOIMPL.LCFactory.getInstance().createLCReader()
    reader.setReadCollectionNames(list(collection_names))
    return reader


def iter_events(files: Sequence[str], input_format: str, collection_names: Sequence[str] = ()):
    """
    Yield the events of all files in order: LCIO LCEvent objects or podio Frame objects.
    Use get_collection / require_collection to read collections from either kind.
    collection_names limits which collections are read; it is only used for LCIO.
    """
    if not files:
        return
    if input_format == "lcio":
        reader = setup_lcio_reader(collection_names)
        for fname in files:
            reader.open(fname)
            try:
                for event in reader:
                    yield event
            finally:
                reader.close()
    elif input_format == "edm4hep":
        try:
            from podio.root_io import Reader  # type: ignore
        except ImportError as exc:
            raise RuntimeError("podio is required for EDM4hep input but is not available in this environment") from exc
        yield from Reader(list(files)).get("events")
    else:
        raise ValueError(f"Unknown input format: {input_format}")


def get_collection(event, name: str):
    """Return the named collection of an LCIO event or podio frame, or None if it is absent."""
    try:
        if hasattr(event, "getCollection"):
            return event.getCollection(name)
        return event.get(name)
    except Exception:
        return None


def require_collection(event, name: str):
    """Return the named collection, raising an error that names it if it is absent."""
    collection = get_collection(event, name)
    if collection is None:
        raise RuntimeError(f"Collection '{name}' not found in event; check --mc-collection / --input-format.")
    return collection


def collection_elements(collection):
    """Iterate over the elements of an LCIO LCCollection or a podio collection."""
    if hasattr(collection, "getNumberOfElements"):
        for i in range(collection.getNumberOfElements()):
            yield collection.getElementAt(i)
    else:
        yield from collection


def _momentum_xyz(mcp) -> Tuple[float, float, float]:
    """Return (px, py, pz). LCIO returns an indexable array; EDM4hep returns a Vector3d with x, y, z."""
    momentum = mcp.getMomentum()
    if hasattr(momentum, "x"):
        return float(momentum.x), float(momentum.y), float(momentum.z)
    return float(momentum[0]), float(momentum[1]), float(momentum[2])


def mcp_eta(mcp) -> float:
    px, py, pz = _momentum_xyz(mcp)
    p = math.sqrt(px * px + py * py + pz * pz)
    if p <= 0.0:
        return 999.0
    cos_theta = max(-1.0, min(1.0, pz / p))
    theta = math.acos(cos_theta)
    tan_half = math.tan(0.5 * theta)
    if tan_half <= 0:
        return 999.0
    return -math.log(tan_half)


def mcp_theta(mcp) -> float:
    px, py, pz = _momentum_xyz(mcp)
    p =math.sqrt(px * px + py * py + pz * pz)
    if p <= 0.0:
        return 0.0
    cos_theta = max(-1.0, min(1.0, pz / p))
    return math.acos(cos_theta)


def find_single_primary(
    mcp_collection,
    pdg_ids: Sequence[int],
    eta_max: float,
    require_single: bool,
):
    matches = []
    for mcp in collection_elements(mcp_collection):
        if mcp.getGeneratorStatus() != 1:
            continue
        if abs(mcp.getPDG()) not in pdg_ids:
            continue
        eta = mcp_eta(mcp)
        if abs(eta) > eta_max:
            continue
        matches.append(mcp)
    if not matches:
        return None
    if require_single and len(matches) != 1:
        return None
    return max(matches, key=lambda x: x.getEnergy())


def sum_collection_energy(event, name: str) -> float:
    collection = get_collection(event, name)
    if collection is None:
        return 0.0
    return sum(hit.getEnergy() for hit in collection_elements(collection))


def get_best_cluster(event, cluster_collection: str):
    collection = get_collection(event, cluster_collection)
    if collection is None:
        return None
    best = None
    best_energy = -1.0
    for cluster in collection_elements(collection):
        energy = float(cluster.getEnergy())
        if energy > best_energy:
            best_energy = energy
            best = cluster
    return best


def get_cluster_energy_split(cluster, ecal_index: int = 0, hcal_index: int = 1):
    """Return (total, ecal, hcal, has_split)."""
    total = float(cluster.getEnergy())
    values: List[float] = []
    if hasattr(cluster, "getSubdetectorEnergies"):
        sub = cluster.getSubdetectorEnergies()
        try:
            n = len(sub)
            values = [float(sub[i]) for i in range(n)]
        except Exception:
            try:
                values = [float(x) for x in sub]
            except Exception:
                values = []
    max_idx = max(ecal_index, hcal_index)
    has_split = len(values) > max_idx
    ecal = float(values[ecal_index]) if len(values) > ecal_index else 0.0
    hcal = float(values[hcal_index]) if len(values) > hcal_index else 0.0
    return total, ecal, hcal, has_split


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input files/directories/globs. Directories are expanded with --file-glob.",
    )
    parser.add_argument(
        "--file-glob",
        default=None,
        help="Glob used when an input is a directory (default: *.edm4hep.root for edm4hep, *.slcio for lcio, "
        "both for auto).",
    )
    add_input_format_args(parser)
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search directory inputs using **/<file-glob>.",
    )
    parser.add_argument("--max-events", type=int, default=-1, help="Maximum events to process (-1 = all).")
    parser.add_argument("--eta-max", type=float, default=2.436, help="Truth particle acceptance cut.")
    parser.add_argument(
        "--require-single-primary",
        action="store_true",
        help="Require exactly one matching primary truth particle per event.",
    )
    parser.add_argument(
        "--theta-bins",
        required=True,
        help="Comma-separated theta bin edges in radians (e.g. 0,0.4,0.8,3.14159).",
    )
    parser.add_argument(
        "--energy-bins",
        required=True,
        help="Comma-separated energy bin edges in GeV.",
    )
    parser.add_argument("--min-bin-count", type=int, default=20, help="Minimum entries to calibrate a bin.")
    parser.add_argument(
        "--estimator",
        choices=["median", "mean", "trimmed_mean"],
        default="median",
        help="Per-bin estimator for correction factor.",
    )
    parser.add_argument(
        "--trim-fraction",
        type=float,
        default=0.1,
        help="Trim fraction on each side when estimator=trimmed_mean.",
    )


def build_table_from_ratios(
    domain: str,
    theta_edges: List[float],
    energy_edges: List[float],
    ratios_per_bin: List[List[float]],
    min_bin_count: int,
    estimator: str,
    trim_fraction: float,
    metadata: dict,
) -> CalibrationTable:
    n_theta = len(theta_edges) - 1
    n_energy = len(energy_edges) - 1
    expected = n_theta * n_energy
    if len(ratios_per_bin) != expected:
        raise ValueError("Internal error: ratio buffer size mismatch")

    scales: List[float] = []
    counts: List[int] = []
    for values in ratios_per_bin:
        counts.append(len(values))
        if len(values) < min_bin_count:
            scales.append(1.0)
        else:
            scales.append(robust_estimate(values, estimator, trim_fraction))

    table = CalibrationTable(
        domain=domain,
        theta_edges=theta_edges,
        energy_edges=energy_edges,
        scales=scales,
        counts=counts,
        metadata=metadata,
    )
    table.validate()
    return table
