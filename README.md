# LandXML to Revit Pipe & Manhole Placer

Converts Civil 3D pipe network exports (LandXML) into Revit MEP pipes and manhole family instances via Dynamo.

## Files

| File | Purpose |
|------|---------|
| `landxml_to_revit_csv.py` | Python script — converts LandXML to two Dynamo-ready CSVs (pipes + structures) |
| `revit_config.txt` | Project calibration values, units, filters, and text replacements (edit per project) |
| `place_pipes_Battery_Room_V9_1.dyn` | Dynamo script — places pipes from CSV into Revit |
| `place_structures_from_csv_V1_4.dyn` | Dynamo script — places manhole families from CSV into Revit |

## Requirements

- Python 3.6+ (standard library only, no pip installs)
- Revit 2024+ with Dynamo 2.x
- MEPover Dynamo package (for `Pipe.ByLines` node in the pipes script)
- A manhole family loaded in the Revit project (e.g. `g-PLM-PIN_Storm+Foulwater_Manhole_R21`)

## Workflow

### 1. Export from Civil 3D

Export your pipe network as LandXML (.xml):

- Open Civil 3D with your pipe network
- `Output` tab → `Export to LandXML`
- Select the pipe network(s) to export
- Save as `.xml`

### 2. Configure for your Revit project (one-time per project)

Edit `revit_config.txt` with values from your Revit model:

```
# From Revit > Project Base Point properties
PBP_E = 24517724.1561    # E/W in meters
PBP_N = 6687664.9191     # N/S in meters
PBP_Z = 76.750           # Elevation in meters
ATN = 124.703             # Angle to True North in degrees

# Internal offset — set to 0 first, calibrate after first run
Px = 0
Py = 0
Pz = 0

# Units
CIVIL3D_UNITS = m
REVIT_UNITS = mm
```

**Where to find these values in Revit:**

1. In a site plan view, make the Project Base Point visible (Visibility/Graphics → Site category)
2. Click the Project Base Point icon
3. Read E/W, N/S, Elev from the properties panel (divide by 1000 if shown in mm)
4. Read Angle to True North

### 3. Run the converter

Place `landxml_to_revit_csv.py`, `revit_config.txt`, and your `.xml` file in the same folder.

Double-click `landxml_to_revit_csv.py` or run from command line:

```
python landxml_to_revit_csv.py path\to\your_network.xml
```

This outputs two files alongside the XML:
- `your_network_pipes.csv` — pipe segments
- `your_network_structures.csv` — manholes

### 4. Place pipes in Dynamo

1. Open Revit and launch Dynamo
2. Open `place_pipes_Battery_Room_V9_1.dyn`
3. Update the **File Path** node to point to the pipes CSV
4. Select the correct **Level**, **PipeType**, and **PipingSystemType**
5. Run (set to Manual mode first to preview)

### 5. Place structures in Dynamo

1. Open `place_structures_from_csv_V1_4.dyn`
2. Update the **File Path** node to point to the structures CSV
3. Select the correct **Level** and **Family Type** (manhole family)
4. Run

The structures script:
- Places each manhole at the correct XY position and rim elevation
- Sets the **Mark** parameter to the structure name from the CSV
- Sets the **Height** parameter to the structure depth (rim to lowest invert)
- Uses `Level.Elevation` internally to compute the correct Z offset for `FamilyInstance.ByPointAndLevel`

## Config file reference

### Calibration values

| Key | Description | Where to find it |
|-----|-------------|-----------------|
| `PBP_E` | Project Base Point Easting (meters) | Revit PBP properties |
| `PBP_N` | Project Base Point Northing (meters) | Revit PBP properties |
| `PBP_Z` | Project Base Point Elevation (meters) | Revit PBP properties |
| `ATN` | Angle to True North (degrees) | Revit PBP properties |
| `Px` | Internal X offset (mm) | Calibrate — see below |
| `Py` | Internal Y offset (mm) | Calibrate — see below |
| `Pz` | Internal Z offset (mm) | Calibrate — see below |

### Units

```
CIVIL3D_UNITS = m      # Unit of LandXML coordinates (mm, m, or ft)
REVIT_UNITS = mm        # Unit Dynamo expects (match your Revit project)
```

The converter automatically applies the conversion factor between the two units.

### Filters (optional)

Filter which pipes and/or structures are included in the output CSVs. Three scopes:

| Scope | Applies to |
|-------|-----------|
| `FILTER` | Both pipes and structures |
| `PIPE_FILTER` | Pipes CSV only |
| `STRUCT_FILTER` | Structures CSV only |

Format: `FILTER = column | operator | value`

Available operators: `equals`, `not_equals`, `contains`, `not_contains`, `greater_than`, `less_than`, `starts_with`, `ends_with`

Available columns:
- Pipes: `name`, `start_struct`, `end_struct`, `diameter`, `material`, `description`
- Structures: `name`, `description`, `diameter`, `material`, `rim`, `sump`, `invert`, `depth`

Multiple filters are combined with AND logic. Examples:

```
FILTER = name | contains | Battery Room          # both CSVs
PIPE_FILTER = diameter | greater_than | 100      # pipes only
STRUCT_FILTER = name | contains | BAT-MH         # structures only
```

### Text replacements (optional)

Clean up text in the output CSVs. Three scopes: `REPLACE`, `PIPE_REPLACE`, `STRUCT_REPLACE`.

Format: `REPLACE = column | find_text | replace_text`

To delete text, leave the replacement empty:

```
REPLACE = name | (Battery Room) |               # removes " (Battery Room)" from names
PIPE_REPLACE = material | SE2 | HDPE            # renames material in pipes CSV
```

## CSV formats

### Pipes CSV

Pre-computed Revit internal coordinates in the output unit (default mm). Dynamo reads these directly with no transformation.

```
SX,SY,SZ,EX,EY,EZ,Dia
48018.4,249606.3,-17637.0,43770.4,238291.1,-17746.1,131.0
```

| Column | Description |
|--------|-------------|
| SX, SY, SZ | Pipe start point (Revit internal coordinates) |
| EX, EY, EZ | Pipe end point (Revit internal coordinates) |
| Dia | Pipe diameter (mm) |

### Structures CSV

XY in Revit internal coordinates, Z values as **project elevations** (not internal coordinates). The Dynamo script uses `Level.Elevation` to compute the correct placement offset.

```
Name,Description,X,Y,Z_Rim,Z_Sump,Z_Invert,Depth,Diameter,Material,Connected_Pipes
BAT-MH1,Concentric...,48018.4,249606.3,76741.6,73180.0,73180.0,3562,900.,Plastic,...
```

| Column | Description |
|--------|-------------|
| Name | Structure name (after any text replacements) |
| Description | Structure type from Civil 3D |
| X, Y | Revit internal coordinates |
| Z_Rim | Rim elevation as project elevation (e.g. 76742 for 76.742m) |
| Z_Sump | Sump elevation as project elevation |
| Z_Invert | Lowest invert elevation as project elevation |
| Depth | Rim to lowest invert (mm) |
| Diameter | Structure diameter from Civil 3D |
| Material | Structure material |
| Connected_Pipes | Pipes connected to this structure with flow direction |

**Why Z values are project elevations, not internal coordinates:**
`FamilyInstance.ByPointAndLevel` treats the point's Z as an offset from the level, not an absolute coordinate. The Dynamo script computes `z_place = z_rim - Level.Elevation`, so when Dynamo places the family at `Level.Elevation + z_place`, the result equals the rim elevation.

## Coordinate transform

The converter transforms from Civil 3D shared coordinates (ETRF89/OSGB) to Revit internal coordinates using:

```
dE = easting - PBP_E
dN = northing - PBP_N
dZ = elevation - PBP_Z

x = Px + (dE × cos(ATN) - dN × sin(ATN)) × unit_factor
y = Py + (dE × sin(ATN) + dN × cos(ATN)) × unit_factor
z = Pz + dZ × unit_factor          # for pipes (internal coords)
z = elevation × unit_factor          # for structures (project elevation)
```

All coordinate maths is done in the Python script. Dynamo does zero transformation — it reads the CSV values directly.

## Calibrating Px, Py, Pz for a new project

The first four config values (PBP_E, PBP_N, PBP_Z, ATN) can be read directly from Revit. The last three (Px, Py, Pz) account for the internal offset of the Project Base Point, which varies per model and cannot be read from any Revit property.

**First-time calibration:**

1. Set `Px = 0`, `Py = 0`, `Pz = 0` in the config
2. Run the converter and place pipes via Dynamo
3. The pipes will appear in the wrong location but with correct shape and rotation
4. Use Revit's dimension tool to measure the offset between placed pipes and their correct position (e.g. a linked DWG reference)
5. Enter the measured offsets into the config:

| Pipes need to move | Set |
|---------------------|-----|
| Left | `Px` = negative value |
| Right | `Px` = positive value |
| Down (in plan) | `Py` = negative value |
| Up (in plan) | `Py` = positive value |
| Down (elevation) | `Pz` = negative value |
| Up (elevation) | `Pz` = positive value |

6. Re-run the converter and re-place pipes
7. Repeat if needed — usually takes 1–2 iterations to get within tolerance

**Verifying Pz:** Compare the rim elevation of a placed manhole (in Revit properties) to the known value in Civil 3D. A consistent offset across multiple manholes means Pz needs adjusting by that amount.

## Troubleshooting

**Pipes appear as a steep diagonal in elevation:**
The rotation transform is wrong. Check that ATN matches the Angle to True North shown on the Project Base Point exactly.

**Pipes are the right shape but in the wrong location:**
Px, Py, Pz need calibrating. See the calibration section above.

**Manholes appear at the correct point in Dynamo preview but place lower:**
This was a known issue fixed in V1_4. The Dynamo script must use `z_place = z_rim - Level.Elevation` because `FamilyInstance.ByPointAndLevel` internally subtracts the level elevation from the Z value. Make sure you are using `place_structures_from_csv_V1_4.dyn` and the latest version of the Python script which outputs Z values as project elevations.

**Dynamo warning "Inputs are outside the currently selected modeling range":**
Click Workspace Geometry Scaling → set to Large. This is normal for large coordinate offsets.

**Pipes have wrong diameter:**
The Dynamo PipeType node selects by index. Check that the index matches the pipe type you want in your model. The CSV supplies the correct diameter from the XML, but the PipeType must support that size.

**No pipes created / errors in Dynamo:**
Ensure the MEPover package is installed (Dynamo → Packages → Search for MEPover). The `Pipe.ByLines` node comes from this package.

**Structures not filtered correctly:**
Check your `STRUCT_FILTER` entries in `revit_config.txt`. Column names are case-insensitive. Multiple filters use AND logic — all conditions must match.

**Text replacements not working:**
The `REPLACE` format uses `|` as a separator. Make sure there are no extra `|` characters in your find/replace text. To delete text, leave the replacement empty: `REPLACE = name | (Battery Room) |`
