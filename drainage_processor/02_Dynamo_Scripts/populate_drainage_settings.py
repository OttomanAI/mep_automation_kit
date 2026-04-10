"""
Populate Drainage Settings CSV
================================
Scans 01_Manholes/ and 02_Pipes/ folders for CSVs that match
the 'type' column, then writes the paths into manhole_data and pipe_data.

Expects to be in: 02_Dynamo_Scripts/00_Revit_Dynamo_Configs/
Scans siblings:    02_Dynamo_Scripts/01_Manholes/
                   02_Dynamo_Scripts/02_Pipes/

USAGE:
    python populate_drainage_settings.py
"""

import os
import csv


def populate():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'config_drainage_settings.csv')
    manholes_dir = os.path.join(script_dir, '01_Manholes')
    pipes_dir = os.path.join(script_dir, '02_Pipes')

    if not os.path.exists(csv_path):
        print(f"ERROR: drainage_settings.csv not found in {script_dir}")
        return

    # List available CSVs
    mh_csvs = [f for f in os.listdir(manholes_dir) if f.endswith('.csv')] if os.path.isdir(manholes_dir) else []
    pipe_csvs = [f for f in os.listdir(pipes_dir) if f.endswith('.csv')] if os.path.isdir(pipes_dir) else []

    print(f"Found {len(mh_csvs)} manhole CSVs, {len(pipe_csvs)} pipe CSVs\n")

    # Read settings
    with open(csv_path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Match each type to its CSVs
    for row in rows:
        site_type = row['type'].strip().upper()

        # Find manhole CSV containing this type name
        match = None
        for mh in mh_csvs:
            if site_type.lower().replace(' ', '') in mh.lower().replace(' ', '').replace('_', ''):
                match = mh
                break
        if match:
            row['manhole_data'] = os.path.join(manholes_dir, match)
            print(f"  {site_type}")
            print(f"    Manholes: {match}")
        else:
            row['manhole_data'] = ''
            print(f"  {site_type}")
            print(f"    Manholes: NOT FOUND")

        # Find pipe CSV containing this type name
        match = None
        for pc in pipe_csvs:
            if site_type.lower().replace(' ', '') in pc.lower().replace(' ', '').replace('_', ''):
                match = pc
                break
        if match:
            row['pipe_data'] = os.path.join(pipes_dir, match)
            print(f"    Pipes:    {match}")
        else:
            row['pipe_data'] = ''
            print(f"    Pipes:    NOT FOUND")

    # Write back
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['type', 'workset', 'manhole_data', 'pipe_data'])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nUpdated drainage_settings.csv")


if __name__ == '__main__':
    populate()
    input("\nPress Enter to exit...")
