"""
LandXML to Revit CSV Converter
================================
Converts a Civil 3D LandXML pipe network export into two CSV files:
  1. *_pipes.csv      - pipe segments with start/end coordinates for Dynamo
  2. *_structures.csv - manholes with position, elevations, depth, size

Reads calibration, units, filter, and replace settings from revit_config.txt.

USAGE:
    1. Export your pipe network from Civil 3D as LandXML (.xml)
    2. Fill in revit_config.txt (same folder as this script)
    3. Run:  python landxml_to_revit_csv.py [path_to_xml]
"""

import xml.etree.ElementTree as ET
import csv
import math
import os
import sys


# ============================================================
# UNITS
# ============================================================

UNIT_TO_METERS = {
    'mm': 0.001,
    'm': 1.0,
    'ft': 0.3048
}


def get_conversion_factor(from_unit, to_unit):
    """Get multiplication factor to convert from one unit to another."""
    from_unit = from_unit.lower().strip()
    to_unit = to_unit.lower().strip()

    if from_unit not in UNIT_TO_METERS:
        raise ValueError(f"Unknown unit '{from_unit}'. Use: mm, m, ft")
    if to_unit not in UNIT_TO_METERS:
        raise ValueError(f"Unknown unit '{to_unit}'. Use: mm, m, ft")

    return UNIT_TO_METERS[from_unit] / UNIT_TO_METERS[to_unit]


# ============================================================
# CONFIG
# ============================================================

def load_config(config_path):
    """Load calibration values, units, filters, and replacements."""
    values = {}
    filters_both = []
    filters_pipe = []
    filters_struct = []
    replace_both = []
    replace_pipe = []
    replace_struct = []

    with open(config_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue

            key, val = line.split('=', 1)
            key = key.strip()
            val_raw = val.split('#')[0]

            if key in ('FILTER', 'PIPE_FILTER', 'STRUCT_FILTER'):
                parts = [p.strip() for p in val_raw.split('|')]
                if len(parts) == 3:
                    filt = {
                        'column': parts[0].lower(),
                        'operator': parts[1].lower(),
                        'value': parts[2]
                    }
                    if key == 'FILTER':
                        filters_both.append(filt)
                    elif key == 'PIPE_FILTER':
                        filters_pipe.append(filt)
                    elif key == 'STRUCT_FILTER':
                        filters_struct.append(filt)

            elif key in ('REPLACE', 'PIPE_REPLACE', 'STRUCT_REPLACE'):
                parts = val_raw.split('|')
                if len(parts) >= 2:
                    repl = {
                        'column': parts[0].strip().lower(),
                        'find': parts[1].strip(),
                        'replace': parts[2].strip() if len(parts) > 2 else ''
                    }
                    if key == 'REPLACE':
                        replace_both.append(repl)
                    elif key == 'PIPE_REPLACE':
                        replace_pipe.append(repl)
                    elif key == 'STRUCT_REPLACE':
                        replace_struct.append(repl)

            elif key in ('CIVIL3D_UNITS', 'REVIT_UNITS'):
                values[key] = val_raw.strip().lower()

            else:
                try:
                    values[key] = float(val_raw.strip())
                except ValueError:
                    values[key] = val_raw.strip()

    required = ['PBP_E', 'PBP_N', 'PBP_Z', 'ATN', 'Px', 'Py', 'Pz']
    missing = [k for k in required if k not in values]
    if missing:
        raise ValueError(f"Missing values in config: {', '.join(missing)}")

    # Default units
    values.setdefault('CIVIL3D_UNITS', 'm')
    values.setdefault('REVIT_UNITS', 'mm')

    # Compute conversion factor
    values['coord_factor'] = get_conversion_factor(
        values['CIVIL3D_UNITS'], values['REVIT_UNITS'])

    values['filters_both'] = filters_both
    values['filters_pipe'] = filters_pipe
    values['filters_struct'] = filters_struct
    values['replace_both'] = replace_both
    values['replace_pipe'] = replace_pipe
    values['replace_struct'] = replace_struct
    return values


# ============================================================
# FILTERING
# ============================================================

def apply_filter(item, filt):
    """Apply a single filter. Returns True if item passes."""
    col = filt['column']
    op = filt['operator']
    target = filt['value']

    raw = item.get(col, '')
    if raw is None:
        raw = ''

    if op in ('greater_than', 'less_than'):
        try:
            num_val = float(str(raw).rstrip('.'))
            num_target = float(target)
        except (ValueError, TypeError):
            return True
        if op == 'greater_than':
            return num_val > num_target
        if op == 'less_than':
            return num_val < num_target

    val_str = str(raw).lower()
    target_lower = target.lower()

    if op == 'equals':
        try:
            return float(str(raw).rstrip('.')) == float(target)
        except (ValueError, TypeError):
            pass
        return val_str == target_lower
    elif op == 'not_equals':
        try:
            return float(str(raw).rstrip('.')) != float(target)
        except (ValueError, TypeError):
            pass
        return val_str != target_lower
    elif op == 'contains':
        return target_lower in val_str
    elif op == 'not_contains':
        return target_lower not in val_str
    elif op == 'starts_with':
        return val_str.startswith(target_lower)
    elif op == 'ends_with':
        return val_str.endswith(target_lower)
    else:
        print(f"  WARNING: Unknown operator '{op}', skipping filter")
        return True


def filter_items(items, filters):
    """Apply all filters (AND logic)."""
    if not filters:
        return items
    return [item for item in items if all(apply_filter(item, f) for f in filters)]


# ============================================================
# REPLACE / DELETE TEXT
# ============================================================

def apply_replacements(items, replacements):
    """Apply text replacements to matching columns."""
    if not replacements:
        return items
    for item in items:
        for repl in replacements:
            col = repl['column']
            if col in item and isinstance(item[col], str):
                item[col] = item[col].replace(repl['find'], repl['replace']).strip()
    return items


# ============================================================
# COORDINATE TRANSFORM
# ============================================================

def shared_to_internal(easting, northing, elevation, cfg):
    """Transform shared coordinates to Revit internal coordinates."""
    atn_rad = cfg['ATN'] * math.pi / 180
    cos_a = math.cos(atn_rad)
    sin_a = math.sin(atn_rad)

    # Deltas in Civil 3D units
    dE = easting - cfg['PBP_E']
    dN = northing - cfg['PBP_N']
    dZ = elevation - cfg['PBP_Z']

    # Convert to Revit units, rotate, add offset
    f = cfg['coord_factor']
    x = cfg['Px'] + (dE * cos_a - dN * sin_a) * f
    y = cfg['Py'] + (dE * sin_a + dN * cos_a) * f
    z = cfg['Pz'] + dZ * f

    return round(x, 1), round(y, 1), round(z, 1)


# ============================================================
# XML PARSING
# ============================================================

def parse_landxml(xml_path):
    """Parse LandXML and extract structures and pipes."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    structs = {}
    struct_details = []

    for s in root.iter():
        if not s.tag.endswith('Struct'):
            continue

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

        inverts = []
        connected_pipes = []
        for child in s:
            if child.tag.endswith('Invert'):
                inv_elev = float(child.get('elev', '0'))
                flow_dir = child.get('flowDir', '')
                ref_pipe = child.get('refPipe', '')
                inverts.append(inv_elev)
                if ref_pipe:
                    connected_pipes.append(f"{ref_pipe} ({flow_dir})")

        avg_inv = sum(inverts) / len(inverts) if inverts else 0
        min_inv = min(inverts) if inverts else 0
        is_null = 'Null' in name

        structs[name] = {
            'easting': easting,
            'northing': northing,
            'invert_elev': avg_inv
        }

        if not is_null:
            desc = s.get('desc', '')
            elev_rim = s.get('elevRim', '')
            elev_sump = s.get('elevSump', '')

            diameter = ''
            material = ''
            for child in s:
                if child.tag.endswith('CircStruct'):
                    diameter = child.get('diameter', '')
                    material = child.get('material', '')
                    break
                elif child.tag.endswith('RectStruct'):
                    length = child.get('length', '0')
                    width = child.get('width', '0')
                    diameter = f"{length}x{width}"
                    material = child.get('material', '')
                    break

            rim = float(elev_rim) if elev_rim else 0
            sump = float(elev_sump) if elev_sump else 0
            depth = round((rim - min_inv) * 1000) if rim and min_inv else 0

            struct_details.append({
                'name': name,
                'description': desc,
                'easting': easting,
                'northing': northing,
                'rim': rim,
                'sump': sump,
                'invert': min_inv,
                'depth': depth,
                'diameter': diameter,
                'material': material,
                'connected_pipes': '; '.join(connected_pipes)
            })

    pipes = []
    for p in root.iter():
        if not p.tag.endswith('Pipe') or not p.get('refStart'):
            continue

        ref_start = p.get('refStart', '')
        ref_end = p.get('refEnd', '')
        pipe_name = p.get('name', '')
        desc = p.get('desc', '')
        length = p.get('length', '')
        slope = p.get('slope', '')

        circ = None
        for child in p:
            if child.tag.endswith('CircPipe'):
                circ = child
                break

        diameter = circ.get('diameter', '0') if circ is not None else '0'
        material = circ.get('material', '') if circ is not None else ''

        if ref_start in structs and ref_end in structs:
            pipes.append({
                'name': pipe_name,
                'start_struct': ref_start,
                'end_struct': ref_end,
                'diameter': diameter,
                'material': material,
                'description': desc,
                'length': length,
                'slope': slope,
                'start': structs[ref_start],
                'end': structs[ref_end]
            })

    return structs, struct_details, pipes


# ============================================================
# CSV OUTPUT
# ============================================================

def write_pipes_csv(pipes, cfg, output_path):
    """Write pipe segments CSV."""
    rows = []
    for p in pipes:
        sx, sy, sz = shared_to_internal(
            p['start']['easting'], p['start']['northing'],
            p['start']['invert_elev'], cfg)
        ex, ey, ez = shared_to_internal(
            p['end']['easting'], p['end']['northing'],
            p['end']['invert_elev'], cfg)
        rows.append([sx, sy, sz, ex, ey, ez,
                      float(str(p['diameter']).rstrip('.'))])

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['SX', 'SY', 'SZ', 'EX', 'EY', 'EZ', 'Dia'])
        writer.writerows(rows)

    return rows


def write_structures_csv(structures, cfg, output_path):
    """Write structures/manholes CSV."""
    f = cfg['coord_factor']
    rows = []
    for s in structures:
        x, y, _ = shared_to_internal(s['easting'], s['northing'], 0, cfg)
        z_rim = cfg['Pz'] + (s['rim'] - cfg['PBP_Z']) * f if s['rim'] else 0
        z_sump = cfg['Pz'] + (s['sump'] - cfg['PBP_Z']) * f if s['sump'] else 0
        z_inv = cfg['Pz'] + (s['invert'] - cfg['PBP_Z']) * f if s['invert'] else 0

        rows.append([
            s['name'], s['description'],
            x, y,
            round(z_rim, 1), round(z_sump, 1), round(z_inv, 1),
            s['depth'],
            s['diameter'], s['material'],
            s['connected_pipes']
        ])

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Name', 'Description',
            'X', 'Y',
            'Z_Rim', 'Z_Sump', 'Z_Invert',
            'Depth',
            'Diameter', 'Material',
            'Connected_Pipes'
        ])
        writer.writerows(rows)

    return rows


# ============================================================
# MAIN
# ============================================================

def print_rules(rules):
    """Print active filters or replacements."""
    for r in rules:
        if 'operator' in r:
            print(f"    {r['column']} {r['operator']} \"{r['value']}\"")
        elif 'find' in r:
            repl_text = f"\"{r['replace']}\"" if r['replace'] else "(delete)"
            print(f"    {r['column']}: \"{r['find']}\" -> {repl_text}")


def convert(xml_path, cfg):
    """Full conversion: parse, filter, replace, write both CSVs."""
    base = os.path.splitext(xml_path)[0]
    pipes_csv = base + '_pipes.csv'
    structs_csv = base + '_structures.csv'

    c3d = cfg.get('CIVIL3D_UNITS', 'm')
    rev = cfg.get('REVIT_UNITS', 'mm')

    print(f"\nParsing: {os.path.basename(xml_path)}")
    print(f"  Units: Civil 3D={c3d}, Revit={rev} (factor: {cfg['coord_factor']})")

    structs, struct_details, pipes = parse_landxml(xml_path)
    print(f"  {len(struct_details)} structures, {len(pipes)} pipes")

    # Build scoped lists
    f_both = cfg.get('filters_both', [])
    f_pipe = cfg.get('filters_pipe', [])
    f_struct = cfg.get('filters_struct', [])
    r_both = cfg.get('replace_both', [])
    r_pipe = cfg.get('replace_pipe', [])
    r_struct = cfg.get('replace_struct', [])

    pipe_filters = f_both + f_pipe
    struct_filters = f_both + f_struct
    pipe_replacements = r_both + r_pipe
    struct_replacements = r_both + r_struct

    # Filter
    if pipe_filters:
        print(f"\n  Pipe filters ({len(pipe_filters)}):")
        print_rules(pipe_filters)
        pipes = filter_items(pipes, pipe_filters)
        print(f"    -> {len(pipes)} pipes")

    if struct_filters:
        print(f"\n  Structure filters ({len(struct_filters)}):")
        print_rules(struct_filters)
        struct_details = filter_items(struct_details, struct_filters)
        print(f"    -> {len(struct_details)} structures")

    # Replace
    if pipe_replacements:
        print(f"\n  Pipe replacements ({len(pipe_replacements)}):")
        print_rules(pipe_replacements)
        apply_replacements(pipes, pipe_replacements)

    if struct_replacements:
        print(f"\n  Structure replacements ({len(struct_replacements)}):")
        print_rules(struct_replacements)
        apply_replacements(struct_details, struct_replacements)

    # Write pipes
    pipe_rows = write_pipes_csv(pipes, cfg, pipes_csv)
    if pipe_rows:
        all_z = [r[2] for r in pipe_rows] + [r[5] for r in pipe_rows]
        diameters = sorted(set(r[6] for r in pipe_rows))
        print(f"\n  Pipes: {os.path.basename(pipes_csv)}")
        print(f"    {len(pipe_rows)} pipes, diameters: {diameters}")
    else:
        print(f"\n  Pipes: none to write")

    # Write structures
    struct_rows = write_structures_csv(struct_details, cfg, structs_csv)
    if struct_rows:
        depths = [s['depth'] for s in struct_details if s['depth'] > 0]
        sizes = sorted(set(s['diameter'] for s in struct_details if s['diameter']))
        print(f"\n  Structures: {os.path.basename(structs_csv)}")
        print(f"    {len(struct_rows)} manholes, sizes: {sizes}")
        if depths:
            print(f"    Depth range: {min(depths)} to {max(depths)}")
    else:
        print(f"\n  Structures: none to write")

    return pipes_csv, structs_csv


if __name__ == '__main__':
    print("=" * 50)
    print("  LandXML to Revit CSV Converter")
    print("  Outputs: pipes + structures")
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

    total_f = (len(cfg['filters_both']) + len(cfg['filters_pipe'])
               + len(cfg['filters_struct']))
    total_r = (len(cfg['replace_both']) + len(cfg['replace_pipe'])
               + len(cfg['replace_struct']))
    print(f"\nConfig loaded: {total_f} filter(s), {total_r} replacement(s)")

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
