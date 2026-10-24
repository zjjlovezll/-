# -*- coding: utf-8 -*-
"""Dump mode frequencies and tread-node displacement shapes from the wheelset odb.

Run with abaqus python (Python 2.7): f-strings are not available, and the path is written
to a file because CAE console output does not survive a redirect.

For every mode the script keeps the nodes in the tread band of each wheel and writes the
radial / axial components in the wheel's local plane, plus the dominant azimuthal harmonic
of the radial component.  That harmonic is the nodal diameter, measured rather than assumed.
"""
from __future__ import print_function

import json
import math
import sys

from odbAccess import openOdb

if len(sys.argv) < 3:
    raise SystemExit('usage: abaqus python wheelset_fe_dump.py <job.odb> <modes.json>')

ODB = sys.argv[1]
OUT = sys.argv[2]

AXIS_X = -1250.0          # axle axis in the CAD frame, mm
AXLE_Y = 0.2832
# The rolling circle, not the largest radius: the outer 26 mm of this wheel is the flange, and
# a ring taken there samples the flange tip instead of the surface that carries the load.
TREAD_MIN = 455.0
TREAD_MAX = 465.0
HALF_WIDTH = 40.0         # keep nodes near the tread centre plane


def main():
    odb = openOdb(ODB, readOnly=True)
    instance = odb.rootAssembly.instances.values()[0]
    coordinates = {}
    tread = {}
    for node in instance.nodes:
        x, y, z = node.coordinates
        radius = math.hypot(x - AXIS_X, z)
        side = "R" if (y - AXLE_Y) > 0.0 else "L"
        plane = (AXLE_Y + 735.915) if side == "R" else (AXLE_Y - 735.915)
        if abs(y - plane) > HALF_WIDTH:
            continue
        if not (TREAD_MIN <= radius <= TREAD_MAX):
            continue
        theta = math.atan2(z, x - AXIS_X)
        tread[node.label] = (side, radius, theta)
        coordinates[node.label] = (x, y, z)
    print("tread nodes: %d  (L %d, R %d)" % (
        len(tread),
        sum(1 for value in tread.values() if value[0] == 'L'),
        sum(1 for value in tread.values() if value[0] == 'R')))

    step = odb.steps.values()[0]
    modes = []
    for frame in step.frames:
        if 'U' not in frame.fieldOutputs.keys():
            continue
        field = frame.fieldOutputs['U']
        samples = {}
        for value in field.values:
            label = value.nodeLabel
            if label in tread:
                samples[label] = value.data
        if not samples:
            continue
        per_side = {"L": [], "R": []}
        for label, data in samples.items():
            side, radius, theta = tread[label]
            ux, uy, uz = data[0], data[1], data[2]
            radial = ux * math.cos(theta) + uz * math.sin(theta)
            per_side[side].append([int(label), float(radius), float(theta),
                                  float(radial), float(uy), float(ux), float(uz)])
        harmonics = {}
        for side in ("L", "R"):
            rows = sorted(per_side[side], key=lambda row: row[2])
            if len(rows) < 24:
                harmonics[side] = {"harmonic": 0, "amplitude": 0.0, "ratio": 0.0}
                continue
            values = [row[3] for row in rows]
            best, best_amp = 0, 0.0
            total = 0.0
            for order in range(0, 7):
                cosine = 0.0
                sine = 0.0
                for index, value in enumerate(values):
                    angle = 2.0 * math.pi * order * index / len(values)
                    cosine += value * math.cos(angle)
                    sine += value * math.sin(angle)
                amplitude = math.hypot(cosine, sine) / len(values)
                total += amplitude * amplitude
                if amplitude > best_amp:
                    best, best_amp = order, amplitude
            ratio = best_amp * best_amp / total if total > 0.0 else 0.0
            harmonics[side] = {"harmonic": best, "amplitude": best_amp, "ratio": ratio}
        frequency = getattr(frame, 'frequency', None)
        eigenvalue = getattr(frame, 'eigenValue', None)
        frequency = float(frequency) if frequency is not None else 0.0
        if eigenvalue is None:
            eigenvalue = float((2.0 * math.pi * frequency) ** 2)
        modes.append({
            "frame": frame.frameId,
            "description": getattr(frame, 'description', ''),
            "eigenvalue": float(eigenvalue),
            "frequency_hz": frequency,
            "harmonic": harmonics,
            "nodes": {side: per_side[side] for side in ("L", "R")},
        })
    print("modes dumped: %d" % len(modes))

    handle = open(OUT, "w")
    json.dump({"odb": ODB, "tread_band_mm": [TREAD_MIN, TREAD_MAX],
               "coordinates": dict((str(key), [float(value[0]), float(value[1]), float(value[2])])
                                    for key, value in coordinates.items()),
               "modes": modes}, handle)
    handle.close()
    print("wrote %s" % OUT)


main()
