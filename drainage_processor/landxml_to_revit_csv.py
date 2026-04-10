"""
LandXML to Revit CSV Converter
================================
Converts Civil 3D LandXML pipe network exports into CSV files:
  1. *_pipes.csv      - into 02_Dynamo_Scripts/02_Pipes/
  2. *_manholes.csv   - into 02_Dynamo_Scripts/01_Manholes/

Reads site configurations from 01_XML_Data/00_XML_Configs/.
Automatically rebuilds site_configs.json on each run.
Processes ALL XML files referenced in the configs.

FOLDER STRUCTURE:
    root/
    ├── landxml_to_revit_csv.py       (this script)
    ├── build_configs.py
    ├── 01_XML_Data/
    │   ├── *.xml                     (input XMLs)
    │   └── 00_XML_Configs/
    │       ├── *.txt                 (site configs)
    │       └── site_configs.json     (auto-generated)
    └── 02_Dynamo_Scripts/
        ├── 01_Manholes/              (manhole CSVs + .dyn)
        └── 02_Pipes/                 (pipe CSVs + .dyn)

USAGE:
    python landxml_to_revit_csv.py
"""

import xml.etree.ElementTree as ET
import csv
import math
import os
import sys
import json


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

def load_configs(json_path):
    """Load all site configurations from site_configs.json."""
    with open(json_path, 'r') as f:
        configs = json.load(f)

    # Add coord_factor to each config
    for name, cfg in configs.items():
        c3d = cfg.get('CIVIL3D_UNITS', 'm')
        rev = cfg.get('REVIT_UNITS', 'mm')
        cfg['coord_factor'] = get_conversion_factor(c3d, rev)

        # Validate required keys
        required = ['PBP_E', 'PBP_N', 'PBP_Z', 'ATN', 'Px', 'Py', 'Pz']
        missing = [k for k in required if k not in cfg]
        if missing:
            raise ValueError(
                f"Config '{name}' missing: {', '.join(missing)}")

    return configs


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
    return [item for item in items
            if all(apply_filter(item, f) for f in filters)]


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
                item[col] = item[col].replace(
                    repl['find'], repl['replace']).strip()
    return items


# ============================================================
# COORDINATE TRANSFORM
# ============================================================

def shared_to_internal(easting, northing, elevation, cfg):
    """Transform shared coordinates to Revit internal coordinates."""
    atn_rad = cfg['ATN'] * math.pi / 180
    cos_a = math.cos(atn_rad)
    sin_a = math.sin(atn_rad)

    dE = easting - cfg['PBP_E']
    dN = northing - cfg['PBP_N']
    dZ = elevation - cfg['PBP_Z']

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
    """Write pipe segments CSV.
    X, Y = Revit internal coordinates.
    Z = raw XML elevations, unit-converted only (no PBP/Pz transform).
    """
    f = cfg['coord_factor']
    rows = []
    for p in pipes:
        sx, sy, _ = shared_to_internal(
            p['start']['easting'], p['start']['northing'], 0, cfg)
        ex, ey, _ = shared_to_internal(
            p['end']['easting'], p['end']['northing'], 0, cfg)
        sz = round(p['start']['invert_elev'] * f, 1)
        ez = round(p['end']['invert_elev'] * f, 1)
        rows.append([sx, sy, sz, ex, ey, ez,
                      float(str(p['diameter']).rstrip('.')),
                      p['name']])

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['SX', 'SY', 'SZ', 'EX', 'EY', 'EZ', 'Dia', 'Name'])
        writer.writerows(rows)

    return rows


def write_manholes_csv(structures, cfg, output_path):
    """Write manholes CSV.
    X, Y = Revit internal coordinates.
    Z_Rim, Z_Sump, Z_Invert = raw XML elevations, unit-converted only.
    """
    f = cfg['coord_factor']
    rows = []
    for s in structures:
        x, y, _ = shared_to_internal(s['easting'], s['northing'], 0, cfg)

        z_rim = round(s['rim'] * f, 1) if s['rim'] else 0
        z_sump = round(s['sump'] * f, 1) if s['sump'] else 0
        z_inv = round(s['invert'] * f, 1) if s['invert'] else 0

        rows.append([
            s['name'], s['description'],
            x, y,
            z_rim, z_sump, z_inv,
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
# PROCESS SINGLE SITE
# ============================================================

def print_rules(rules):
    """Print active filters or replacements."""
    for r in rules:
        if 'operator' in r:
            print(f"    {r['column']} {r['operator']} \"{r['value']}\"")
        elif 'find' in r:
            repl_text = f"\"{r['replace']}\"" if r['replace'] else "(delete)"
            print(f"    {r['column']}: \"{r['find']}\" -> {repl_text}")


def find_xml_for_site(site_name, xml_dir):
    """Find the XML file that matches a site name by checking filenames."""
    xml_files = [f for f in os.listdir(xml_dir) if f.lower().endswith('.xml')]
    site_key = site_name.lower().replace('_', ' ')

    for xml_file in xml_files:
        if site_key in xml_file.lower().replace('_', ' '):
            return xml_file

    return None


def process_site(site_name, cfg, root_dir):
    """Process a single site: parse XML, filter, replace, write CSVs."""
    xml_dir = os.path.join(root_dir, '01_XML_Data')
    manholes_dir = os.path.join(root_dir, '02_Dynamo_Scripts', '01_Manholes')
    pipes_dir = os.path.join(root_dir, '02_Dynamo_Scripts', '02_Pipes')

    # Auto-find XML: use XML_FILE if set, otherwise match by site name
    xml_file = cfg.get('XML_FILE', '').strip()
    if xml_file and os.path.exists(os.path.join(xml_dir, xml_file)):
        pass  # explicit match found
    else:
        xml_file = find_xml_for_site(site_name, xml_dir)
        if not xml_file:
            print(f"  SKIPPED: no matching XML found in 01_XML_Data/")
            return False

    xml_path = os.path.join(xml_dir, xml_file)

    # Output filenames
    xml_base = os.path.splitext(xml_file)[0]
    os.makedirs(manholes_dir, exist_ok=True)
    os.makedirs(pipes_dir, exist_ok=True)
    pipes_csv = os.path.join(pipes_dir, xml_base + '_pipes.csv')
    manholes_csv = os.path.join(manholes_dir, xml_base + '_manholes.csv')

    c3d = cfg.get('CIVIL3D_UNITS', 'm')
    rev = cfg.get('REVIT_UNITS', 'mm')

    print(f"  XML:   {xml_file}")
    print(f"  Units: Civil 3D={c3d}, Revit={rev} (factor: {cfg['coord_factor']})")

    structs, struct_details, pipes = parse_landxml(xml_path)
    print(f"  Found: {len(struct_details)} structures, {len(pipes)} pipes")

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

    if pipe_filters:
        print(f"\n  Pipe filters ({len(pipe_filters)}):")
        print_rules(pipe_filters)
        pipes = filter_items(pipes, pipe_filters)
        print(f"    -> {len(pipes)} pipes")

    if struct_filters:
        print(f"\n  Structure filters ({len(struct_filters)}):")
        print_rules(struct_filters)
        struct_details = filter_items(struct_details, struct_filters)
        print(f"    -> {len(struct_details)} manholes")

    if pipe_replacements:
        print(f"\n  Pipe replacements ({len(pipe_replacements)}):")
        print_rules(pipe_replacements)
        apply_replacements(pipes, pipe_replacements)

    if struct_replacements:
        print(f"\n  Structure replacements ({len(struct_replacements)}):")
        print_rules(struct_replacements)
        apply_replacements(struct_details, struct_replacements)

    pipe_rows = write_pipes_csv(pipes, cfg, pipes_csv)
    if pipe_rows:
        diameters = sorted(set(r[6] for r in pipe_rows))
        print(f"\n  Pipes -> 02_Pipes/{os.path.basename(pipes_csv)}")
        print(f"    {len(pipe_rows)} pipes, diameters: {diameters}")
    else:
        print(f"\n  Pipes: none to write")

    manhole_rows = write_manholes_csv(struct_details, cfg, manholes_csv)
    if manhole_rows:
        depths = [s['depth'] for s in struct_details if s['depth'] > 0]
        sizes = sorted(set(s['diameter'] for s in struct_details
                           if s['diameter']))
        print(f"\n  Manholes -> 01_Manholes/{os.path.basename(manholes_csv)}")
        print(f"    {len(manhole_rows)} manholes, sizes: {sizes}")
        if depths:
            print(f"    Depth range: {min(depths)} to {max(depths)}")
        print(f"    Z values = raw XML elevation in {rev}")
    else:
        print(f"\n  Manholes: none to write")

    return True


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("  LandXML to Revit CSV Converter")
    print("  Batch mode: processes all sites")
    print("=" * 60)

    root_dir = os.path.dirname(os.path.abspath(__file__))
    configs_dir = os.path.join(root_dir, '01_XML_Data', '00_XML_Configs')
    json_path = os.path.join(configs_dir, 'site_configs.json')

    if not os.path.isdir(configs_dir):
        print(f"\nERROR: 01_XML_Data/00_XML_Configs/ folder not found.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Auto-run build_configs
    print("\nBuilding site_configs.json...")
    from build_configs import build_json
    build_json(configs_dir)

    if not os.path.exists(json_path):
        print(f"\nERROR: site_configs.json was not created.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    try:
        configs = load_configs(json_path)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"\nERROR: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)

    print(f"\nLoaded {len(configs)} site config(s)")

    success = 0
    skipped = 0

    for site_name, cfg in configs.items():
        print(f"\n{'─' * 60}")
        print(f"  {site_name}")
        print(f"{'─' * 60}")
        if process_site(site_name, cfg, root_dir):
            success += 1
        else:
            skipped += 1

    print(f"\n{'=' * 60}")
    print(f"  Complete: {success} processed, {skipped} skipped")
    print(f"{'=' * 60}")

    # Update drainage settings CSV with file paths
    dynamo_dir = os.path.join(root_dir, '02_Dynamo_Scripts')
    populate_script = os.path.join(dynamo_dir, 'populate_drainage_settings.py')
    if os.path.exists(populate_script):
        print(f"\nUpdating drainage settings file paths...")
        sys.path.insert(0, dynamo_dir)
        from populate_drainage_settings import populate
        populate()
    else:
        print(f"\nNOTE: file_locations_drainage_settings.py not found, skipping path update")

    input("\nPress Enter to exit...")
