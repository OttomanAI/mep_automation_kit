# LandXML to Revit Pipe Placer

Converts Civil 3D pipe network exports (LandXML) into Revit MEP pipes via Dynamo.

## Files

| File | Purpose |
|------|---------|
| `landxml_to_revit_csv.py` | Python script — converts LandXML to a Dynamo-ready CSV |
| `revit_config.txt` | Project calibration values (edit per project) |
| `place_pipes_Battery_Room_V9.dyn` | Dynamo script — places pipes from CSV into Revit |

## Requirements

- Python 3.6+ (standard library only, no pip installs)
- Revit 2024+ with Dynamo 2.x
- MEPover Dynamo package (for `Pipe.ByLines` node)

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

This outputs `your_network_revit_coords.csv` in the same folder as the XML.

### 4. Place pipes in Dynamo

1. Open Revit and launch Dynamo
2. Open `place_pipes_Battery_Room_V9.dyn`
3. Update the **File Path** node to point to the CSV
4. Select the correct **Level**, **PipeType**, and **PipingSystemType**
5. Run (set to Manual mode first to preview)

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
7. Repeat if needed — usually takes 1-2 iterations to get within tolerance

## CSV format

The converter outputs a simple 7-column CSV with pre-computed Revit internal coordinates in mm:

```
SX,SY,SZ,EX,EY,EZ,Dia
48018.4,249606.3,-17637.0,43770.4,238291.1,-17746.1,131.0
...
```

| Column | Description |
|--------|-------------|
| SX, SY, SZ | Pipe start point (Revit internal mm) |
| EX, EY, EZ | Pipe end point (Revit internal mm) |
| Dia | Pipe diameter (mm) |

The Dynamo script reads these directly with no further transformation.

## Troubleshooting

**Pipes appear as a steep diagonal in elevation:**
The rotation transform is wrong. Check that ATN matches the Angle to True North shown on the Project Base Point exactly.

**Pipes are the right shape but in the wrong location:**
Px, Py, Pz need calibrating. See the calibration section above.

**Dynamo warning "Inputs are outside the currently selected modeling range":**
Click Workspace Geometry Scaling → set to Large. This is normal for large coordinate offsets.

**Pipes have wrong diameter:**
The Dynamo PipeType node selects by index. Check that the index matches the pipe type you want in your model. The CSV supplies the correct diameter from the XML, but the PipeType must support that size.

**No pipes created / errors in Dynamo:**
Ensure the MEPover package is installed (Dynamo → Packages → Search for MEPover). The `Pipe.ByLines` node comes from this package.
