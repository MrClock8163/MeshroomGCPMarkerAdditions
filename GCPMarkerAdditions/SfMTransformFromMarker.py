__version__ = "2.0"

from meshroom.core import desc
from meshroom.core import cgroup

import os.path
import csv
import psutil
import shlex
import json

class SfMTransformFromMarker(desc.Node):
    # Commandline call template
    commandLine = "aliceVision_sfmTransform {input} --method from_markers --scale 1.0 --landmarksDescriberTypes {markerTypeValue} {applyScale} {applyRotation} {applyTranslation} {verboseLevel} {output} {outputViewsAndPoses}"
    category = 'Utils'
    documentation = '''
This is a custom version of the standard SfMTransform node.
The node allows to read the available marker 3D coordinates from an
external CSV file.

CSV format:

    markerID, easting, northing, elevation
    
    markerID:           unique ID of marker
    easting:            eastward coordinate of marker in target coordinate system
    northing:           northward coordinate of marker in target coordinate system
    elevation:          elevation of marker in target coordinate system
'''
    cgroupParsed = False
    cmdMem = ''
    cmdCore = ''
    
    # Constructor copied from the desc.CommandLineNode class
    def __init__(self):
        
        if SfMTransformFromMarker.cgroupParsed is False:

            SfMTransformFromMarker.cmdMem = ''
            memSize = cgroup.getCgroupMemorySize()
            if memSize > 0:
                SfMTransformFromMarker.cmdMem = ' --maxMemory={memSize}'.format(memSize=memSize)

            SfMTransformFromMarker.cmdCore = ''
            coresCount = cgroup.getCgroupCpuCount()
            if coresCount > 0:
                SfMTransformFromMarker.cmdCore = ' --maxCores={coresCount}'.format(coresCount=coresCount)

            SfMTransformFromMarker.cgroupParsed = True

    inputs = [
        desc.File(
            name = "input",
            label = "Input",
            description = "SfMData file.",
            value = "",
            uid = [0]
        ),
        desc.ChoiceParam(
            name = "marker_source",
            label = "Marker ID Source",
            description = "Extract marker IDs from SfM data, or specify them manually.",
            value = "auto",
            values = ["auto", "manual"],
            exclusive = True,
            uid = [0]
        ),
        desc.StringParam(
            name = "marker_ids",
            label = "Marker IDs",
            description = "List of markers IDs to use (comma separated list).",
            value = "",
            enabled = lambda node: node.marker_source.value == "manual",
            uid = [0]
        ),
        desc.GroupAttribute(
            name = "coordinates",
            label = "Marker Coordinates",
            description = "Marker alignment data",
            joinChar = " ",
            groupDesc = [
                desc.File(
                    name = "file",
                    label = "Coordinates File",
                    description = "CSV file holding all available marker coordinates (markerID, easting, northing, elevation).",
                    value = "",
                    uid = [0]
                ),
                desc.ChoiceParam(
                    name = "delimiter",
                    label = "Delimiter",
                    description = "Delimiter character used in the input CSV file.",
                    value = "semicolon",
                    values = ["space", "tab", "comma", "colon", "semicolon"],
                    exclusive = True,
                    uid = [0]
                ),
                desc.GroupAttribute(
                    name = "offset",
                    label = "Offset",
                    description = "Offset amount for marker coordinates to recenter mesh and avoid loss of precision.\nIf all coordinates are positive, use negative offset to recenter them.",
                    joinChar = ":",
                    groupDesc = [
                        desc.FloatParam(name="x", label="x", description="Offset along X axis.", value=0.0, uid=[0], range=(-2.0, 2.0, 1.0)),
                        desc.FloatParam(name="y", label="y", description="Offset along Y axis.", value=0.0, uid=[0], range=(-2.0, 2.0, 1.0)),
                        desc.FloatParam(name="z", label="z", description="Offset along Z axis.", value=0.0, uid=[0], range=(-2.0, 2.0, 1.0)),
                    ]
                )
            ]
        ),
        desc.ChoiceParam(
            name = "markerType",
            label = "Marker Type",
            description = "Type of marker to use for the transformation.",
            value = "cctag3",
            values = ["cctag3", "cctag4", "tag16h5"],
            exclusive = True,
            uid = [0]
        ),
        desc.IntParam(
            name = "precision",
            label = "Coordinate Precision",
            description = "Number of decimal places to pass to transformation algorithm",
            value = 3,
            range = (0, 10, 1),
            uid = [0]
        ),
        desc.BoolParam(
            name = "applyScale",
            label = "Scale",
            description = "Apply scale transformation.",
            value = True,
            uid = [0]
        ),
        desc.BoolParam(
            name = "applyRotation",
            label = "Rotation",
            description = "Apply rotation transformation.",
            value = True,
            uid = [0]
        ),
        desc.BoolParam(
            name = "applyTranslation",
            label = "Translation",
            description = "Apply translation transformation.",
            value = True,
            uid = [0]
        ),
        desc.ChoiceParam(
            name = "verboseLevel",
            label = "Verbose Level",
            description = "Verbosity level (fatal, error, warning, info, debug, trace).",
            value = "info",
            values = ["fatal", "error", "warning", "info", "debug", "trace"],
            exclusive = True,
            uid = []
        ),
    ]

    outputs = [
        desc.File(
            name = "output",
            label = "SfMData File",
            description = "Aligned SfMData file.",
            value = lambda attr: desc.Node.internalFolder + (os.path.splitext(os.path.basename(attr.node.input.value))[0] or "sfmData") + ".abc",
            uid = []
        ),
        desc.File(
            name = "outputViewsAndPoses",
            label = "Poses",
            description = "Path to the output SfMData file with cameras (views and poses).",
            value = desc.Node.internalFolder + "cameras.sfm",
            uid = []
        )
    ]
    
    # Function copied from the vanilla desc.AVCommandLineNode class
    def buildCommandLine(self, chunk):
        cmdPrefix = ''
        # if rez available in env, we use it
        if 'REZ_ENV' in os.environ and chunk.node.packageVersion:
            # if the node package is already in the environment, we don't need a new dedicated rez environment
            alreadyInEnv = os.environ.get('REZ_{}_VERSION'.format(chunk.node.packageName.upper()), "").startswith(chunk.node.packageVersion)
            if not alreadyInEnv:
                cmdPrefix = '{rez} {packageFullName} -- '.format(rez=os.environ.get('REZ_ENV'), packageFullName=chunk.node.packageFullName)
        
        cmdSuffix = ''
        if chunk.node.isParallelized and chunk.node.size > 1:
            cmdSuffix = ' ' + self.commandLineRange.format(**chunk.range.toDict())
        
        cmd = cmdPrefix + chunk.node.nodeDesc.commandLine.format(**chunk.node._cmdVars) + cmdSuffix
        
        return cmd + SfMTransformFromMarker.cmdMem + SfMTransformFromMarker.cmdCore
    
    # Get the IDs of markers to use for transformation
    def get_markerids(self, chunk):
        ids = []
        
        # Use the EXE connected to the ConvertSfMFormat node to
        # extract the reconstructed marker features, and their IDs
        if chunk.node.marker_source.value == "auto":
            marker_json = os.path.join(chunk.node.internalFolder, "markers.json")
            convert_cmd = "aliceVision_convertSfMFormat  --input \"{}\" --describerTypes {} --views False --intrinsics False --extrinsics False --structure True --observations False --verboseLevel info --output \"{}\"".format(chunk.node.input.value, chunk.node.markerType.value, marker_json)
            chunk.subprocess = psutil.Popen(shlex.split(convert_cmd), stdout=None, stderr=None, cwd=chunk.node.internalFolder)
            chunk.statThread.proc = chunk.subprocess
            chunk.subprocess.wait()
            
            return_code = chunk.subprocess.returncode
            if chunk.subprocess.returncode != return_code:
                raise RuntimeError('Error on node "{}":\n'.format(chunk.name))
        
            sfm = []
            with open(marker_json) as file:
                sfm = json.load(file).get("structure")
            
            
            if sfm:
                ids = sorted([int(point["color"][0]) for point in sfm]) # marker IDs are stored as the red color value
        
        # Parse the manually set ID list
        else:
            for id in chunk.node.marker_ids.value.split(","):
                try:
                    id = int(id)
                except:
                    continue
                
                ids.append(id)
        
        return ids
            
    # Load 3D marker coordinates from CSV file into dictionary
    def load_coords(self, filepath, delimiter, offset):
        if not os.path.isfile(filepath):
            return {}
        
        coordinates = {}
        
        with open(filepath, "r") as csvfile:
            markers = csv.reader(csvfile, delimiter=delimiter, quoting=csv.QUOTE_NONNUMERIC)
            for item in markers:
                if len(item) < 4:
                    print("Could not read marker coordinates")
                    continue
                    
                coordinates[item[0]] = (item[1] + offset.x.value, item[2] + offset.y.value, item[3] + offset.z.value)
        
        return coordinates
    
    # Format markers parameter for aliceVision_sfmTransform.exe from the supplied
    # dictionary containing the coordinates
    def build_markers_param(self, markers, precision = 3):
        cmd = " --markers"
        form = f" %d:%.{precision}f,%.{precision}f,%.{precision}f"
        
        for item in markers:
            cmd += form % (item, *markers[item])
        
        return cmd
    
    # Processing function called by the node
    def processChunk(self, chunk):
        markers_cmd = ""
        
        delimiters_options = {
            "space": " ",
            "tab": "\t",
            "comma": ",",
            "colon": ":",
            "semicolon": ";"
        }
        delimiter = delimiters_options[chunk.node.coordinates.delimiter.value]
        
        # Load marker coordinates and format commandline parameter
        try:
            chunk.logManager.start(chunk.node.verboseLevel.value)
            chunk.logger.info("Loading marker coordinates")
            
            marker_ids = self.get_markerids(chunk)
            print("Marker IDs: ", marker_ids)
            coords = self.load_coords(chunk.node.coordinates.file.value, delimiter, chunk.node.coordinates.offset)
            markers = {id: coords[id] for id in marker_ids}
            markers_cmd = self.build_markers_param(markers, chunk.node.precision.value)
            
        except Exception as e:
            chunk.logger.error(e)
            raise
        finally:
            chunk.logManager.end()
            
        # Call aliceVision_sfmTransform.exe
        try:
            with open(chunk.logFile, 'w') as logF:
                cmd = self.buildCommandLine(chunk) + markers_cmd
                chunk.status.commandLine = cmd
                chunk.saveStatusFile()
                print(' - commandLine: {}'.format(cmd))
                print(' - logFile: {}'.format(chunk.logFile))
                chunk.subprocess = psutil.Popen(shlex.split(cmd), stdout=logF, stderr=logF, cwd=chunk.node.internalFolder)

                chunk.statThread.proc = chunk.subprocess
                stdout, stderr = chunk.subprocess.communicate()
                chunk.subprocess.wait()

                chunk.status.returnCode = chunk.subprocess.returncode

            if chunk.subprocess.returncode != 0:
                with open(chunk.logFile, 'r') as logF:
                    logContent = ''.join(logF.readlines())
                raise RuntimeError('Error on node "{}":\nLog:\n{}'.format(chunk.name, logContent))
            
        except:
            raise
        finally:
            chunk.subprocess = None