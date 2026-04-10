EXAMPLE DATA
============

This folder contains sample XML files and configs for testing the drainage processor.

To use this example data:

1. Copy all the .xml files from this folder into the parent folder (01_XML_Data/)
2. Copy the 00_XML_Configs/ folder contents into 01_XML_Data/00_XML_Configs/
3. Go back to the root drainage_processor/ folder
4. Double-click run.bat

The parser will process all 7 XML files and output CSVs into:
  - 02_Dynamo_Scripts/01_Manholes/  (manhole data)
  - 02_Dynamo_Scripts/02_Pipes/     (pipe data)

DO NOT run the parser from inside this example folder.
The XML files must be in 01_XML_Data/ (one level up) for the parser to find them.
