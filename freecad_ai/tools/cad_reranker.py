from .registry import ToolResult
import json
import urllib.error
import urllib.parse
import urllib.request
STEP_PARTS_API = "https://api.step.parts/v1/parts"   # ← endpoint goes here
def normalize_candidate(model):
    attributes = model.get("attributes") or {}
    standard_info = model.get("standard") or {}

    candidate = {
        "id": model.get("id"),
        "name": model.get("name"),
        "description": model.get("description"),
        "thread": attributes.get("thread"),
        "length_mm": attributes.get("lengthMm"),
        "head_style": attributes.get("headStyle"),
        "drive_style": attributes.get("driveStyle"),
        "standard": standard_info.get("designation"),
        "category": model.get("category"),
        "family": model.get("family"),
        "tags": model.get("tags") or [],
        "aliases": model.get("aliases") or [],
        "step_url": model.get("stepUrl"),
        "sha256": model.get("sha256"),
    }

    return candidate

def score_candidate(candidate, requirements):
    score = 0
    details = {}

    # 1. Thread match: 30 points
    requested_thread = requirements.get("thread")
    candidate_thread = candidate.get("thread")

    if requested_thread and candidate_thread:
        if requested_thread.lower() == candidate_thread.lower():
            details["thread"] = 30
        else:
            details["thread"] = 0
    else:
        details["thread"] = 0

    # 2. Length similarity: 25 points
    requested_length = requirements.get("length_mm")
    candidate_length = candidate.get("length_mm")

    if requested_length and candidate_length is not None:
        difference = abs(requested_length - candidate_length)
        similarity = max(0, 1 - difference / requested_length)
        details["length"] = 25 * similarity
    else:
        details["length"] = 0

    # 3. Head style match: 25 points
    requested_head = requirements.get("head_style")
    candidate_head = candidate.get("head_style")

    if requested_head and candidate_head:
        details["head_style"] = (
            25 if requested_head.lower() == candidate_head.lower() else 0
        )
    else:
        details["head_style"] = 0

    # 4. Standard match: 10 points
    requested_standard = requirements.get("standard")
    candidate_standard = candidate.get("standard")

    if requested_standard and candidate_standard:
        details["standard"] = (
            10
            if requested_standard.lower() == candidate_standard.lower()
            else 0
        )
    else:
        details["standard"] = 0

    # 5. Category match: 10 points
    requested_category = requirements.get("category")
    candidate_category = candidate.get("category")

    if requested_category and candidate_category:
        details["category"] = (
            10
            if requested_category.lower() == candidate_category.lower()
            else 0
        )
    else:
        details["category"] = 0

    score = sum(details.values())

    return round(score, 2), details


def rank_candidates(candidates, requirements):
    ranked = []

    for candidate in candidates:
        score, details = score_candidate(candidate, requirements)

        ranked.append({
            "candidate": candidate,
            "score": score,
            "details": details,
        })

    ranked.sort(key=lambda item: item["score"], reverse=True)

    return ranked


import tempfile
import os
from dataclasses import dataclass


def _get_volume(gmsh, dim, tag) -> float:
    """Try several gmsh API names across versions. Returns 0.0 if none exist."""
    for fn in (
        lambda: gmsh.model.getMass(dim, tag),
        lambda: gmsh.model.occ.getMass(dim, tag),
        lambda: gmsh.model.geo.getMass(dim, tag),
    ):
        try:
            return float(fn())
        except (AttributeError, TypeError):
            continue
    return 0.0


@dataclass
class ValidationResult:
    valid: bool                      # overall pass/fail
    has_solid: bool                  # at least one 3D solid
    units: str = "unknown"           # inferred: "mm", "inch", "unknown"
    measured_length_mm: float = 0.0  # actual bounding-box length (normalized to mm)
    declared_length_mm: float = 0.0  # from API metadata (candidate["length_mm"])
    length_match: bool = False       # measured vs declared within ±10%
    volume: float = 0.0              # solid volume (gmsh getMass without density = volume)
    error: str = ""


def validate_step_bytes(step_bytes: bytes, expected_length_mm: float | None = None) -> ValidationResult:
    """Write bytes to a temp .step file, parse with gmsh, and cross-check geometry vs metadata."""
    import gmsh

    # Write bytes to a temporary file — gmsh needs a path, not raw bytes
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as tmp:
        tmp.write(step_bytes)
        tmp_path = tmp.name

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)

    try:
        # gmsh.open() takes a FILE PATH, not bytes
        gmsh.open(tmp_path)

        volumes = gmsh.model.getEntities(3)
        has_solid = len(volumes) > 0

        measured_length_mm = 0.0
        volume = 0.0
        units = "unknown"
        length_match = False

        if volumes:
            dim, tag = volumes[0]
            xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(dim, tag)
            measured_length = max(xmax - xmin, ymax - ymin, zmax - zmin)

            # Volume is a nice-to-have metric — never let an unsupported API
            # call crash the whole validation.
            try:
                volume = _get_volume(gmsh, dim, tag)
            except Exception:
                volume = 0.0

            # Infer units by cross-checking measured length vs declared length
            if expected_length_mm:
                if abs(measured_length - expected_length_mm) / expected_length_mm <= 0.10:
                    units = "mm"
                    measured_length_mm = measured_length
                    length_match = True
                elif abs(measured_length * 25.4 - expected_length_mm) / expected_length_mm <= 0.10:
                    units = "inch"
                    measured_length_mm = measured_length * 25.4
                    length_match = True
                else:
                    measured_length_mm = measured_length  # report raw as fallback
            else:
                # No declared length to compare against — report raw measurement
                measured_length_mm = measured_length

        return ValidationResult(
            valid=has_solid and measured_length > 0,
            has_solid=has_solid,
            units=units,
            measured_length_mm=round(measured_length_mm, 3),
            declared_length_mm=expected_length_mm or 0.0,
            length_match=length_match,
            volume=round(volume, 6),
        )
    except Exception as exc:
        return ValidationResult(
            valid=False,
            has_solid=False,
            error=str(exc),
        )
    finally:
        gmsh.finalize()
        os.unlink(tmp_path)  # clean up the temp file


def handle_search_cad_library(
    query: str,
    thread: str = "",
    length_mm: float | None = None,
    head_style: str = "",
    standard: str = "",
    category: str = "",
) -> ToolResult:
    """Search step.parts API, rank candidates, validate top match geometry."""
    try:
        url = STEP_PARTS_API + "?" + urllib.parse.urlencode({"q": query, "pageSize": 20})
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        return ToolResult(
            success=False, output="", error=f"API request failed: {e}"
        )

    models = data.get("items") or []
    if not models:
        return ToolResult(success=True, output="No models found for query.")

    # Flatten API models into candidates
    candidates = [normalize_candidate(m) for m in models]

    # Build requirements from the LLM-provided arguments
    requirements = {
        "thread": thread or None,
        "length_mm": length_mm if length_mm else None,
        "head_style": head_style or None,
        "standard": standard or None,
        "category": category or None,
    }

    # Rank by match score
    ranked = rank_candidates(candidates, requirements)

    # Build human-readable output (like your test_api.py print())
    lines = []
    for i, item in enumerate(ranked, 1):
        c = item["candidate"]
        lines.append(f"#{i} — Score: {item['score']}/100")
        lines.append(
            f"  {c['name']} | thread={c['thread']} | "
            f"length={c['length_mm']}mm | head={c['head_style']}"
        )

    # Validate top match's STEP geometry
    top = ranked[0]["candidate"]
    if top.get("step_url"):
        try:
            with urllib.request.urlopen(top["step_url"], timeout=30) as step_resp:
                step_bytes = step_resp.read()
            result = validate_step_bytes(step_bytes, top.get("length_mm"))
            lines.append(
                f"Top match validation: valid={result.valid}, "
                f"units={result.units}, length_match={result.length_match}"
            )
        except Exception as e:
            lines.append(f"Geometry validation skipped: {e}")

    return ToolResult(success=True, output="\n".join(lines))
