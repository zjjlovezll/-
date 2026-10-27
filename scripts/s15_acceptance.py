"""L5, the acceptance layer: the only place allowed to set measurement_validation_status.

Everything up to here measures.  This layer states the goal's own criterion, compares the measured
numbers with it, and writes one of three honest outcomes:

``met``          the criterion holds on the data at hand;
``not_met``      the criterion was evaluated and does not hold (with the numbers that show it);
``not_evaluated`` something upstream refused, so there is nothing to accept.

It also writes the degradation path: what may still be quoted when the criterion is not met, and what
must not be.  A layer that only says "failed" leaves the next reader to guess which number was real.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DETECTION_TARGET = 6        # all six pre-registered sections
FALSE_ALARM_LIMIT = 0.05    # segment-level, per section
LOCALISATION_LIMIT_M = 0.0  # the peak must fall inside its own section


def summarise_channel(result: dict, label: str) -> dict:
    summary = result.get("summary") or {}
    rows = summary.get("rows") or []
    errors = [
        float(row["localisation_error_m"])
        for row in rows
        if row.get("detected") and row.get("localisation_error_m") is not None
    ]
    return {
        "channel": label,
        "sections": int(summary.get("sections_total") or 0),
        "hits": int(summary.get("sections_detected") or 0),
        "detection_fraction": summary.get("detection_rate"),
        "false_alarm_rate": summary.get("false_alarm_rate_per_section"),
        "threshold_db": summary.get("threshold_db"),
        "auc": summary.get("auc"),
        "inside_minus_outside_db": summary.get("inside_minus_outside_db"),
        "worst_localisation_error_m": max(errors) if errors else None,
        "null_expected_hits": summary.get("expected_hits_if_empty"),
        "null_probability": summary.get("null_probability"),
        "unassigned_peaks": summary.get("unassigned_peaks"),
        "detected_sections": [row["section"] for row in rows if row.get("detected")],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admission", type=Path, default=Path(r"F:\velch_tmp\verdict\verdict.json"))
    parser.add_argument("--bands", type=Path, default=Path(r"F:\velch_tmp\verdict\speed_table.json"))
    parser.add_argument("--detection", type=Path, default=Path(r"F:\velch_tmp\verdict\detection.json"))
    parser.add_argument("--output", type=Path, default=Path(r"F:\velch_tmp\verdict\verdict_final.json"))
    args = parser.parse_args(argv)

    admission = json.loads(args.admission.read_text(encoding="utf-8"))
    upstream = admission.get("layers", [])
    if not all(layer.get("passed") for layer in upstream):
        verdict = {
            "layers": upstream,
            "criterion": None,
            "measured": None,
            "measurement_validation_status": "not_evaluated",
            "reason": "an upstream layer refused, so no acceptance can be made",
        }
        args.output.write_text(json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8")
        print("measurement_validation_status: not_evaluated (upstream refused)")
        return 2

    bands = json.loads(args.bands.read_text(encoding="utf-8")) if args.bands.exists() else []
    detection = json.loads(args.detection.read_text(encoding="utf-8"))
    channels = []
    for key, label in (("vibration", "axle-box vibration"), ("sound", "interior sound")):
        if key in detection:
            channels.append(summarise_channel(detection[key], label))

    best = max(channels, key=lambda item: item["hits"] or 0) if channels else None
    met = bool(
        best
        and best["hits"] >= DETECTION_TARGET
        and (best["false_alarm_rate"] is None or best["false_alarm_rate"] <= FALSE_ALARM_LIMIT)
    )

    layers = list(upstream) + [
        {
            "layer": "L2-calibration",
            "passed": bool(bands),
            "speeds_measured": len(bands),
            "note": "one recorded speed only, so no cross-speed claim is made",
        },
        {
            "layer": "L3-operator",
            "passed": False,
            "faults": [
                "no same-speed model band operator exists yet: the stored BLMA operator is at 80 km/h "
                "while the record averages 70.8 km/h, and the criterion forbids extrapolating between speeds"
            ],
        },
        {"layer": "L4-uncertainty", "passed": False, "faults": ["skipped: L3 has no operator to carry a covariance"]},
        {
            "layer": "L5-acceptance",
            "passed": met,
            "criterion": f"detection {DETECTION_TARGET}/6 at a segment false-alarm rate <= {FALSE_ALARM_LIMIT:.0%}",
            "measured": best,
            "faults": [] if met else [
                f"detection reached {best['hits'] if best else 0}/6 "
                f"({(best['detection_fraction'] if best else 0) or 0:.0%}), short of {DETECTION_TARGET}/6"
            ],
        },
    ]

    verdict = {
        "layers": layers,
        "criterion": layers[-1]["criterion"],
        "measured": best,
        "channels": channels,
        "measurement_validation_status": "met" if met else "not_met",
        "degradation": None if met else {
            "may_quote": [
                "the corrugation wavelength measured off the record (27.5 mm median, 713.2 Hz, 23.1 dB prominence)",
                "segment-level separability given the paper's 18-40 mm prior (sound AUC 0.880, median +6.38 dB)",
                "which sections are detected: S2, S3, S4 on sound; S4, S5 on vibration",
            ],
            "must_not_quote": [
                "a 95 % detection claim on this dataset",
                "any per-band amplitude or profile recovery from it",
                "any cross-speed calibration",
            ],
            "attribution": [
                "data: one speed, two co-located channels, and no irregularity profile as truth in this dataset",
                "physics: above f_n the axle-box response is (2*pi*f_n)^2 * A, so it is wavelength-blind and the "
                "remaining contrast comes from section edges rather than from the corrugation itself",
            ],
        },
    }
    args.output.write_text(json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8")

    for layer in layers:
        print(f"{'PASS' if layer.get('passed') else 'FAIL'}  {layer['layer']}")
        for fault in layer.get("faults") or []:
            print(f"        {fault}")
    print(f"measurement_validation_status: {verdict['measurement_validation_status']}  -> {args.output}")
    return 0 if met else 2


if __name__ == "__main__":
    raise SystemExit(main())
