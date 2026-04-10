# Drainage Processor

Automates the transfer of Civil 3D pipe network data (LandXML) into Autodesk Revit via Dynamo. Handles coordinate transformation, unit conversion, filtering, and parameter population for manholes and pipes across multiple drainage networks.

---

## Quick Start

### Step 0 — Export LandXML from Civil 3D

Before anything else, you need to export a LandXML file from Civil 3D containing the pipe networks you want to transfer into Revit.

In Civil 3D, go to **Output → Export to LandXML**. In the export dialog, you will see a list of all available data — surfaces, alignments, pipe networks, etc. Make sure only the pipe networks you want to model are checked. You don't strictly need to uncheck everything else (surfaces, alignments, etc.) — the Python parser will ignore anything that isn't a pipe network — but **you must be careful with which pipe networks are ticked**. Any pipe network that is checked will be included in the export, and its data will come through into the CSV output. If you leave unwanted networks checked, those pipes and structures will end up in your Revit model.

So the rule is simple: **check only the networks you want, uncheck the ones you don't**. Everything else in the export dialog can be left as-is.

Save the `.xml` file and move on to Step 1.

### Step 1 — Prepare the XML Data

Place all exported XML files into the `01_XML_Data/` folder.

Each XML file needs a corresponding config file in `01_XML_Data/00_XML_Configs/`. A config `.txt` file controls how the parser filters structures, strips network name suffixes, and transforms coordinates. The parser auto-matches XML files to configs by checking if the config filename (e.g. `Battery_Room.txt`) appears in the XML filename (e.g. `HEL11-C3D-CIV - Drainage Battery Room Model.xml`). You do not need to hardcode filenames — just make sure the config name is a recognisable substring of the XML filename.

Your folder should look like this:

```
01_XML_Data/
├── 00_XML_Configs/
│   ├── Battery_Room.txt
│   ├── Drainage_Ditches.txt
│   ├── Foul_Water.txt
│   ├── Oily_Water.txt
│   ├── Rainwater.txt
│   ├── Stormwater.txt
│   └── Sub_Soil.txt
├── HEL11-C3D-CIV - Drainage Battery Room Model.xml
├── HEL11-C3D-CIV - Drainage Ditches Model.xml
├── HEL11-C3D-CIV - Drainage Foul Water Model.xml
├── HEL11-C3D-CIV - Drainage Oily Water Model.xml
├── HEL11-C3D-CIV - Drainage Rainwater Model.xml
├── HEL11-C3D-CIV - Drainage Sub Soil Model.xml
└── HEL11-C3D-CIV - Drainage SW + CP Model.xml
```

Example data is provided in `01_XML_Data/example_data_folder/` — copy its contents into `01_XML_Data/` to test.

### Step 2 — Run the Parser

Double-click `run.bat` (or run `python landxml_to_revit_csv.py` from a terminal).

The script will:

1. Read all config files from `01_XML_Data/00_XML_Configs/`
2. Scan `01_XML_Data/` for matching XML files
3. Parse each XML, apply filters and text replacements
4. Output CSV files into `02_Dynamo_Scripts/01_Manholes/` and `02_Dynamo_Scripts/02_Pipes/`
5. Auto-run `populate_drainage_settings.py` to update file paths in `config_drainage_settings.csv`

After running, you should see manhole and pipe CSVs alongside the Dynamo scripts:

```
02_Dynamo_Scripts/
├── 01_Manholes/
│   ├── HEL11-C3D-CIV - Drainage Battery Room Model_manholes.csv
│   ├── HEL11-C3D-CIV - Drainage Foul Water Model_manholes.csv
│   ├── ... (one per network)
│   └── manholes.dyn
├── 02_Pipes/
│   ├── HEL11-C3D-CIV - Drainage Battery Room Model_pipes.csv
│   ├── HEL11-C3D-CIV - Drainage Foul Water Model_pipes.csv
│   ├── ... (one per network)
│   └── pipes.dyn
├── config_drainage_settings.csv
├── config_global_settings.csv
└── populate_drainage_settings.py
```

### Step 3 — Run the Dynamo Scripts in Revit

Open your Revit project and launch Dynamo. The Dynamo scripts use a dropdown menu to select which drainage network to process, so you do not need separate scripts per network.

#### Placing Pipes

1. Open `02_Dynamo_Scripts/02_Pipes/pipes.dyn` in Dynamo
2. Set the two **File Path** nodes to point to `config_global_settings.csv` and `config_drainage_settings.csv` (both in `02_Dynamo_Scripts/`)
3. Select the drainage type from the **Drainage Type** dropdown (e.g. `BATTERY ROOM`, `FOUL WATER`, etc.)
4. Select the correct **Level** for placement
5. Select the correct **Pipe Type** and **System Type** indices in the Code Blocks (check the Watch nodes to see available types and their indices)
6. Set Run mode to **Manual**, then click **Run**
7. The script will read the correct pipe CSV, place pipes with the Z offset applied, set the Mark parameter, and assign the correct workset

#### Placing Manholes

1. Open `02_Dynamo_Scripts/01_Manholes/manholes.dyn` in Dynamo
2. Set the two **File Path** nodes to point to `config_global_settings.csv` and `config_drainage_settings.csv`
3. Select the drainage type from the **Drainage Type** dropdown
4. Select the correct **Family Type** and **Level** for placement
5. Click **Run**
6. The script will place manholes at X,Y on the selected level, then set: **Elevation from Level** (Z_Rim with z_offset applied, converted mm → ft), **Mark**, **Height** (depth + slab thickness), **X Coordinate**, **Y Coordinate**, and **Workset**

#### Running Multiple Networks

To process all drainage types in one Revit session:

1. Open the Dynamo script (pipes or manholes)
2. Select the first drainage type from the dropdown
3. Run the script
4. Change the dropdown to the next drainage type
5. Run again
6. Repeat for each network

Each run places elements on the correct workset automatically based on the `config_drainage_settings.csv` mapping.

---

## Folder Structure

```
drainage_processor/
├── run.bat                          # Double-click to run the parser
├── landxml_to_revit_csv.py          # Main parser — XML to CSV
├── build_configs.py                 # Builds site_configs.json from .txt files
│
├── 01_XML_Data/                     # INPUT — place XML files here
│   ├── 00_XML_Configs/              # One .txt config per drainage network
│   │   ├── Battery_Room.txt
│   │   ├── Foul_Water.txt
│   │   └── ...
│   └── example_data_folder/         # Example data for testing
│
└── 02_Dynamo_Scripts/               # OUTPUT + Dynamo scripts
    ├── 01_Manholes/                 # Manhole CSVs + .dyn script
    ├── 02_Pipes/                    # Pipe CSVs + .dyn script
    ├── config_drainage_settings.csv # Maps drainage types to worksets and CSV paths
    ├── config_global_settings.csv   # Global settings (z_offset)
    └── populate_drainage_settings.py # Auto-populates CSV paths
```

---

## Config Files

### Site Configs (`01_XML_Data/00_XML_Configs/*.txt`)

Each drainage network has a `.txt` config controlling how its XML is parsed. Key settings:

| Setting | Description |
|---|---|
| `PBP_E`, `PBP_N`, `PBP_Z` | Project Base Point shared coordinates (metres) |
| `ATN` | Angle to True North (degrees) |
| `Px`, `Py`, `Pz` | Internal origin offset (mm) |
| `CIVIL3D_UNITS` | Unit of the LandXML coordinates (`m`, `mm`, or `ft`) |
| `REVIT_UNITS` | Unit Dynamo expects (`mm`, `m`, or `ft`) |
| `STRUCT_FILTER` | Filter to select specific structures (e.g. `name \| contains \| BAT-MH`) |
| `REPLACE` | Text replacement on names (e.g. `name \| (Battery Room) \|` to strip network suffix) |
| `XML_FILE` | (Optional) Explicit XML filename. If omitted, auto-matched by config name |

Filters use the format: `column | operator | value`. Operators: `equals`, `not_equals`, `contains`, `not_contains`, `greater_than`, `less_than`, `starts_with`, `ends_with`. Multiple filters are combined with AND logic.

### Global Settings (`config_global_settings.csv`)

Contains the `z_offset` value applied to all pipe and manhole Z coordinates in Dynamo. This compensates for the difference between Civil 3D survey elevations and Revit's internal coordinate system.

### Drainage Settings (`config_drainage_settings.csv`)

Maps each drainage type to its Revit workset and the file paths for its manhole and pipe CSVs. The `populate_drainage_settings.py` script auto-fills the file path columns by scanning the `01_Manholes/` and `02_Pipes/` folders. This runs automatically at the end of the parser, but can also be run independently.

---

## CSV Output Format

### Pipes (`*_pipes.csv`)

| Column | Description |
|---|---|
| `SX`, `SY` | Start point X, Y in Revit internal coordinates (mm) |
| `SZ` | Start point Z — raw XML elevation, unit-converted (mm) |
| `EX`, `EY` | End point X, Y in Revit internal coordinates (mm) |
| `EZ` | End point Z — raw XML elevation, unit-converted (mm) |
| `Dia` | Pipe diameter (mm) |
| `Name` | Pipe name from the XML |

### Manholes (`*_manholes.csv`)

| Column | Description |
|---|---|
| `Name` | Structure name (filtered and cleaned) |
| `Description` | Civil 3D structure description |
| `X`, `Y` | Revit internal coordinates (mm) |
| `Z_Rim` | Rim elevation — raw XML value, unit-converted (mm) |
| `Z_Sump` | Sump elevation — raw XML value, unit-converted (mm) |
| `Z_Invert` | Lowest invert elevation — raw XML value, unit-converted (mm) |
| `Depth` | Rim to lowest invert (mm) |
| `Diameter` | Structure diameter (mm) |
| `Material` | Structure material |
| `Connected_Pipes` | List of connected pipes with flow direction |

---

## Coordinate System

X and Y coordinates are transformed from Civil 3D shared coordinates (Easting/Northing) to Revit internal coordinates using the Project Base Point calibration values and Angle to True North rotation. The transform formula is:

```
dE = Easting  - PBP_E
dN = Northing - PBP_N

X = Px + (dE × cos(ATN) - dN × sin(ATN)) × unit_factor
Y = Py + (dE × sin(ATN) + dN × cos(ATN)) × unit_factor
```

Z values are **not transformed** — they are raw Civil 3D survey elevations converted to the target unit (typically metres × 1000 = mm). The `z_offset` in `config_global_settings.csv` is applied in Dynamo at placement time to align with the Revit level system.

---

## Requirements

- Python 3.x (included with most Autodesk installations)
- Autodesk Revit with Dynamo
- Dynamo packages: **MEPover** (for `Pipe.ByLines` node)
- Civil 3D LandXML exports of pipe networks

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Parser skips an XML file | Check that the config filename is a substring of the XML filename (case-insensitive). E.g. `Drainage_Ditches.txt` matches `HEL11-C3D-CIV - Drainage Ditches Model.xml` |
| Pipes/manholes placed in wrong location | Verify `PBP_E`, `PBP_N`, `ATN`, `Px`, `Py` values match your Revit project. Check the Project Base Point properties in Revit |
| Z elevations are wrong | Adjust `z_offset` in `config_global_settings.csv`. This value shifts all Z coordinates at placement time |
| Workset assignment fails | Ensure the workset names in `config_drainage_settings.csv` match exactly (including trailing spaces) with the worksets in your Revit project |
| `config_drainage_settings.csv` paths are empty | Run `populate_drainage_settings.py` manually, or re-run `run.bat` which calls it automatically |
| Dynamo dropdown shows wrong type | The dropdown values must match the `type` column in `config_drainage_settings.csv` exactly |
| `Elevation from Level` not setting correctly | The Dynamo script converts Z_Rim from mm to feet (÷ 304.8) for Revit's internal parameter. If your family uses a different parameter name, update the string node |
