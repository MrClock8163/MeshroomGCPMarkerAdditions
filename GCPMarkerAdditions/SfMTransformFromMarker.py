__version__ = "1.0"

from meshroom.core import desc
from meshroom.core import cgroup

import os.path
import csv
import psutil
import shlex

class SfMTransformFromMarker(desc.Node):
    commandLine = "aliceVision_sfmTransform {input} --method from_markers --scale 1.0 --landmarksDescriberTypes {markerTypeValue} {applyScale} {applyRotation} {applyTranslation} {verboseLevel} {output} {outputViewsAndPoses}"
    category = 'Utils'
    documentation = '''
This is a custom version of the standard SfMTransform node.
The node allows to read the available marker 3D coordinates from an
external CSV file.
'''
    cgroupParsed = False
    cmdMem = ''
    cmdCore = ''
    
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
            name="input",
            label="Input",
            description="SfMData file.",
            value="",
            uid=[0],
        ),
        desc.StringParam(
            name="markers",
            label="Markers",
            description="List of markers IDs to use (comma separated list).",
            value="",
            uid=[0], 
        ),
        desc.GroupAttribute(
            name="coordinates",
            label="Marker Coordinates",
            description="Marker alignment data",
            joinChar=" ",
            groupDesc=[
                desc.File(
                    name="file",
                    label="Coordinates File",
                    description="CSV file holding all available marker coordinates (markerID, easting, northing, elevation).",
                    value="",
                    uid=[0],
                ),
                desc.ChoiceParam(
                    name="delimiter",
                    label="Delimiter",
                    description="Delimiter character used in the input CSV file.",
                    value="semicolon",
                    values=["space", "tab", "comma", "colon", "semicolon"],
                    exclusive=True,
                    uid=[0],
                ),
                desc.GroupAttribute(
                    name="offset",
                    label="Offset",
                    description="Offset amount for marker coordinates to recenter mesh and avoid loss of precision.\nIf all coordinates are positive, use negative offset to recenter them.",
                    joinChar=":",
                    groupDesc=[
                        desc.FloatParam(name="x", label="x", description="Offset along X axis.", value=0.0, uid=[0], range=(-2.0, 2.0, 1.0)),
                        desc.FloatParam(name="y", label="y", description="Offset along Y axis.", value=0.0, uid=[0], range=(-2.0, 2.0, 1.0)),
                        desc.FloatParam(name="z", label="z", description="Offset along Z axis.", value=0.0, uid=[0], range=(-2.0, 2.0, 1.0)),
                    ],
                ),
            ],
        ),
        desc.ChoiceParam(
            name="markerType",
            label="Marker Type",
            description="Type of marker to use for the transformation.",
            value="cctag3",
            values=["cctag3", "cctag4", "tag16h5"],
            exclusive=True,
            uid=[0],
        ),
        desc.IntParam(
            name="precision",
            label="Coordinate Precision",
            description="Number of decimal places to pass to transformation algorithm",
            value=3,
            range=(0, 10, 1),
            uid=[0],
        ),
        desc.BoolParam(
            name="applyScale",
            label="Scale",
            description="Apply scale transformation.",
            value=True,
            uid=[0],
        ),
        desc.BoolParam(
            name="applyRotation",
            label="Rotation",
            description="Apply rotation transformation.",
            value=True,
            uid=[0],
        ),
        desc.BoolParam(
            name="applyTranslation",
            label="Translation",
            description="Apply translation transformation.",
            value=True,
            uid=[0],
        ),
        desc.ChoiceParam(
            name="verboseLevel",
            label="Verbose Level",
            description="Verbosity level (fatal, error, warning, info, debug, trace).",
            value="info",
            values=["fatal", "error", "warning", "info", "debug", "trace"],
            exclusive=True,
            uid=[],
        ),
    ]

    outputs = [
        desc.File(
            name="output",
            label="SfMData File",
            description="Aligned SfMData file.",
            value=lambda attr: desc.Node.internalFolder + (os.path.splitext(os.path.basename(attr.node.input.value))[0] or "sfmData") + ".abc",
            uid=[],
        ),
        desc.File(
            name="outputViewsAndPoses",
            label="Poses",
            description="Path to the output SfMData file with cameras (views and poses).",
            value=desc.Node.internalFolder + "cameras.sfm",
            uid=[],
        ),
    ]
    
    def raw(self, string):
        return string[1:-1]
    
    def loadCoords(self, filepath, delimiter, offset):
        if not os.path.isfile(filepath):
            return {}
        
        coordinates = {}
        
        with open(filepath, "r") as csvfile:
            markers = csv.reader(csvfile, delimiter=delimiter, quoting=csv.QUOTE_NONNUMERIC)
            for item in markers:
                if len(item) < 3:
                    print("Could not read GCP coordinates")
                    continue
                    
                coordinates[item[0]] = (item[1] + offset.x.value, item[2] + offset.y.value, item[3] + offset.z.value)
        
        return coordinates
    
    def lookupMarkers(self, marker_ids, coords):
        markers = {}
        for id in marker_ids.split(","):
            try:
                id = int(id)
            except:
                continue
            
            markers[id] = coords[id]
        
        return markers
    
    def buildMarkers(self, markers, precision = 3):
        cmd = " --markers"
        form = f" %d:%.{precision}f,%.{precision}f,%.{precision}f"
        
        for item in markers:
            cmd += form % (item, *markers[item])
        
        return cmd
    
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
        
        try:
            chunk.logManager.start(chunk.node.verboseLevel.value)
            chunk.logger.info("Loading marker coordinates")
            coords = self.loadCoords(chunk.node.coordinates.file.value, delimiter, chunk.node.coordinates.offset)
            markers = self.lookupMarkers(chunk.node.markers.value, coords)
            markers_cmd = self.buildMarkers(markers, chunk.node.precision.value)
        
        except Exception as e:
            chunk.logger.error(e)
        finally:
            chunk.logManager.end()
            
        
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