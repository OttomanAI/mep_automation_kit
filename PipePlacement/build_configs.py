"""
Build Site Configs JSON
========================
Scans revit_configs/ folder, parses each .txt config file,
and writes a combined site_configs.json in the parent folder.

USAGE:
    python build_configs.py
"""

import os
import sys
import json


def parse_config_file(filepath):
    """Parse a single revit_config .txt file into a dict."""
    values = {}
    filters_both = []
    filters_pipe = []
    filters_struct = []
    replace_both = []
    replace_pipe = []
    replace_struct = []

    with open(filepath, 'r') as f:
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

            elif key in ('CIVIL3D_UNITS', 'REVIT_UNITS', 'XML_FILE'):
                values[key] = val_raw.strip()

            else:
                try:
                    values[key] = float(val_raw.strip())
                except ValueError:
                    values[key] = val_raw.strip()

    values['filters_both'] = filters_both
    values['filters_pipe'] = filters_pipe
    values['filters_struct'] = filters_struct
    values['replace_both'] = replace_both
    values['replace_pipe'] = replace_pipe
    values['replace_struct'] = replace_struct

    return values


def build_json(configs_dir=None):
    """Scan config folder and build site_configs.json inside it."""
    if configs_dir is None:
        configs_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(configs_dir, 'site_configs.json')

    configs = {}
    txt_files = sorted([f for f in os.listdir(configs_dir)
                        if f.endswith('.txt')])

    if not txt_files:
        print("ERROR: No .txt config files found in revit_configs/")
        sys.exit(1)

    print(f"Scanning {len(txt_files)} config files in revit_configs/\n")

    for txt_file in txt_files:
        site_name = os.path.splitext(txt_file)[0]
        filepath = os.path.join(configs_dir, txt_file)
        cfg = parse_config_file(filepath)

        xml_file = cfg.get('XML_FILE', '').strip()
        if not xml_file:
            print(f"  WARNING: {txt_file} has no XML_FILE set - skipping")
            continue

        configs[site_name] = cfg
        n_filters = (len(cfg['filters_both']) + len(cfg['filters_pipe'])
                     + len(cfg['filters_struct']))
        n_replace = (len(cfg['replace_both']) + len(cfg['replace_pipe'])
                     + len(cfg['replace_struct']))
        print(f"  {site_name}")
        print(f"    XML:     {xml_file}")
        print(f"    Filters: {n_filters}, Replacements: {n_replace}")
        print(f"    Pz:      {cfg.get('Pz', 'NOT SET')}")

    with open(output_path, 'w') as f:
        json.dump(configs, f, indent=2)

    print(f"\nWrote {len(configs)} site config(s) to site_configs.json")
    skipped = len(txt_files) - len(configs)
    if skipped:
        print(f"  ({skipped} config(s) skipped - no XML_FILE set)")

    return output_path


if __name__ == '__main__':
    build_json()
    input("\nPress Enter to exit...")
