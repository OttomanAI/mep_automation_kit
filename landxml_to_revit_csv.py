"""
LandXML to Revit CSV Converter
================================
Converts a Civil 3D LandXML pipe network export into a CSV file
with pre-computed Revit internal coordinates for use with Dynamo.

USAGE:
    1. Export your pipe network from Civil 3D as LandXML (.xml)
    2. Fill in revit_config.txt with your project's coordinates
    3. Place both files in the same folder as this script
    4. Double-click this script (or run: python landxml_to_revit_csv.py)

CONFIG FILE (revit_config.txt):
    The script reads calibration values from revit_config.txt.
    Required values:
        PBP_E    - Project Base Point Easting (meters)
        PBP_N    - Project Base Point Northing (meters)
        PBP_Z    - Project Base Point Elevation (meters)
        ATN      - Angle to True North (degrees)
        Px       - Internal X offset (mm) - set to 0 initially
        Py       - Internal Y offset (mm) - set to 0 initially
        Pz       - Internal Z offset (mm) - set to 0 initially

FIRST-TIME CALIBRATION FOR A NEW PROJECT:
    1. In Revit, click the Project Base Point and note down:
       E/W, N/S, Elev, and Angle to True North
    2. Put those values in revit_config.txt (divide mm by 1000 for meters)
    3. Set Px, Py, Pz all to 0
    4. Run the script and place the pipes in Revit via Dynamo
    5. Measure the X, Y, Z offset between where pipes landed
       and where they should be (use dimensions or spot coordinates)
    6. Enter those offsets into Px, Py, Pz in the config:
       - If pipes need to move LEFT,  Px is NEGATIVE
       - If pipes need to move RIGHT, Px is POSITIVE
       - If pipes need to move DOWN,  Py is NEGATIVE
       - If pipes need to move UP,    Py is POSITIVE
       - If pipes are too HIGH,       Pz is NEGATIVE
       - If pipes are too LOW,        Pz is POSITIVE
    7. Re-run the script and re-place pipes. Repeat if needed.
"""

import xml.etree.ElementTree as ET
import csv
import math
import os
import sys


def load_config(config_path):
    """Load calibration values from a simple key=value text file."""
    values = {}
    with open(config_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.split('#')[0].strip()
                try:
                    values[key] = float(val)
                except ValueError:
                    pass

    required = ['PBP_E', 'PBP_N', 'PBP_Z', 'ATN', 'Px', 'Py', 'Pz']
    missing = [k for k in required if k not in values]
    if missing:
        raise ValueError(f"Missing values in config: {', '.join(missing)}")

    return values


def parse_landxml(xml_path):
    """Parse a LandXML file and extract structures and pipes."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    structs = {}
    for s in root.iter():
        if s.tag.endswith('Struct'):
            name = s.get('name', '')
            center = None
            for child in s:
                if child.tag.endswith('Center') and child.text:
                    center = child
                    break
            if center is None:
                continue

            parts = center.text.strip().split()
            northing = float(parts[0])
            easting = float(parts[1])

            inverts = [child for child in s if child.tag.endswith('Invert')]
            inv_elevs = [float(iv.get('elev', '0')) for iv in inverts]
            avg_inv = sum(inv_elevs) / len(inv_elevs) if inv_elevs else 0

            structs[name] = {
                'easting': easting,
                'northing': northing,
                'invert_elev': avg_inv,
                'is_null': 'Null' in name
            }

    pipes = []
    for p in root.iter():
        if p.tag.endswith('Pipe') and p.get('refStart'):
            ref_start = p.get('refStart', '')
            ref_end = p.get('refEnd', '')

            circ = None
            for child in p:
                if child.tag.endswith('CircPipe'):
                    circ = child
                    break

            diameter = float(circ.get('diameter', '0')) if circ is not None else 0

            if ref_start in structs and ref_end in structs:
                pipes.append({
                    'diameter': diameter,
                    'start': structs[ref_start],
                    'end': structs[ref_end]
                })

    return structs, pipes


def shared_to_internal(easting, northing, elevation, cfg):
    """Transform shared coordinates to Revit internal coordinates (mm)."""
    atn_rad = cfg['ATN'] * math.pi / 180
    cos_a = math.cos(atn_rad)
    sin_a = math.sin(atn_rad)

    dE = easting - cfg['PBP_E']
    dN = northing - cfg['PBP_N']
    dZ = elevation - cfg['PBP_Z']

    x = cfg['Px'] + (dE * cos_a - dN * sin_a) * 1000
    y = cfg['Py'] + (dE * sin_a + dN * cos_a) * 1000
    z = cfg['Pz'] + dZ * 1000

    return round(x, 1), round(y, 1), round(z, 1)


def convert(xml_path, cfg, output_path=None):
    """Convert a LandXML file to a Dynamo-ready CSV."""

    print(f"\nParsing: {os.path.basename(xml_path)}")
    structs, pipes = parse_landxml(xml_path)

    real = sum(1 for s in structs.values() if not s['is_null'])
    null = sum(1 for s in structs.values() if s['is_null'])
    diameters = sorted(set(p['diameter'] for p in pipes))

    print(f"  {len(structs)} structures ({real} manholes, {null} endpoints)")
    print(f"  {len(pipes)} pipes, diameters: {diameters} mm")

    rows = []
    for p in pipes:
        sx, sy, sz = shared_to_internal(
            p['start']['easting'], p['start']['northing'],
            p['start']['invert_elev'], cfg)
        ex, ey, ez = shared_to_internal(
            p['end']['easting'], p['end']['northing'],
            p['end']['invert_elev'], cfg)
        rows.append([sx, sy, sz, ex, ey, ez, p['diameter']])

    if output_path is None:
        base = os.path.splitext(xml_path)[0]
        output_path = base + '_revit_coords.csv'

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['SX', 'SY', 'SZ', 'EX', 'EY', 'EZ', 'Dia'])
        writer.writerows(rows)

    all_z = [r[2] for r in rows] + [r[5] for r in rows]
    print(f"\n  Output: {os.path.basename(output_path)}")
    print(f"  {len(rows)} pipes, Z span: {(max(all_z) - min(all_z)) / 1000:.1f}m")

    return output_path


if __name__ == '__main__':
    print("=" * 50)
    print("  LandXML to Revit CSV Converter")
    print("=" * 50)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'revit_config.txt')

    if not os.path.exists(config_path):
        print(f"\nERROR: revit_config.txt not found.")
        print(f"  Place it in: {script_dir}")
        input("\nPress Enter to exit...")
        sys.exit(1)

    try:
        cfg = load_config(config_path)
    except ValueError as e:
        print(f"\nERROR: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)

    print(f"\nConfig:")
    print(f"  PBP: E={cfg['PBP_E']}, N={cfg['PBP_N']}, Z={cfg['PBP_Z']}")
    print(f"  ATN: {cfg['ATN']} deg")
    print(f"  Offset: Px={cfg['Px']}, Py={cfg['Py']}, Pz={cfg['Pz']}")

    if len(sys.argv) > 1:
        xml_path = sys.argv[1].strip().strip('"').strip("'")
    else:
        xml_path = input("\nDrag and drop your XML file here:\n> ")
        xml_path = xml_path.strip().strip('"').strip("'")

    if not os.path.exists(xml_path):
        print(f"\nERROR: File not found: {xml_path}")
        input("\nPress Enter to exit...")
        sys.exit(1)

    try:
        convert(xml_path, cfg)
        print("\nDone!")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

    input("\nPress Enter to exit...")
