__version__ = "1.0"

from meshroom.core import desc

import os
import csv
import json
import struct

class ImportMarkerFeatures(desc.Node):
    category = 'Utils'
    size = desc.StaticNodeSize(1)
    parallelization = None
    gpu = desc.Level.NONE
    cpu = desc.Level.NORMAL
    ram = desc.Level.NORMAL
    documentation = '''
This node is a utility to help in the use of marker matches produced by third-party software.
Unfortunately the native Meshroom support for marker detection is lacking important parameters, and hard to predict.
Currently there is no way to manually register markers on images to enhance the reconstruction and georeferencing.

This node reads a formatted CSV file containing the data of markers, and produces cctag3 or cctag4 feature descriptors.
CCTag3 and 4 markers are represented by their single center point, and they are supported in both the Windows and Linux versions of Meshroom.
Practically any marker can be passed off as a CCTag marker, provided that its center point can be determined.
Each line of the CSV must define 1 marker on 1 image.

CSV format:

    markerX, markerY, imageFileName, markerID, markerSize
    
    markerX:            horizontal image coordinate of marker in pixels
    markerY:            vertical image coordinate of marker in pixels
    imageFileName:      name of image file including extension (case sensitive)
    markerID:           unique ID of marker
    markerSize:         size of marker in pixels
'''
    
    inputs = [
        desc.File(
            name = "input",
            label = "SfMData",
            description = "Input SfMData file.",
            value = "",
            uid = [0]
        ),
        desc.File(
            name = "matches",
            label = "Marker Features Data",
            description = "CSV file containing image coordinates of markers, marker ID and marker size (in pixels).",
            value = "",
            uid = [0]
        ),
        desc.ChoiceParam(
            name = "delimiter",
            label = "Delimiter",
            description = "Delimiter character used in the input CSV file.",
            value = "space",
            values = ["space", "tab", "comma", "colon", "semicolon"],
            exclusive = True,
            uid = [0]
        ),
        desc.ChoiceParam(
            name = "type",
            label = "Import As",
            description = "Descriptor type to create for the imported marker data.",
            value = "cctag3",
            values = ["cctag3", "cctag4"],
            exclusive = True,
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
        )
    ]
    
    outputs = [
        desc.File(
            name = "output",
            label = "Marker Features Folder",
            description = "Output path for the features and descriptors files (*.feat, *.desc).",
            value = desc.Node.internalFolder,
            uid = []
        )
    ]
    
    def load_images(self, chunk, filepath, delimiter):
        images = {}
        csv_data = []
        
        with open(filepath) as file:
            gcp_file = csv.reader(file, delimiter=delimiter)
            csv_data = [(row[2], float(row[0]), float(row[1]), float(row[4]), int(row[3])) for row in gcp_file]

        images.update({item[0]: [] for item in csv_data})

        for item in csv_data:
            images[item[0]].append([*item[1:]])
        
        chunk.logger.info("Loaded %d marker matches in %d image(s)" % (len(csv_data), len(images)))
            
        return images
    
    def load_viewids(self, chunk):
        if not os.path.isfile(chunk.node.input.value):
            raise Exception("View data file not found")
        
        views = []
        views_lookup = {}
        with open(chunk.node.input.value) as file:
            views = json.load(file)["views"]
        
        for item in views:
            views_lookup[os.path.basename(item["path"])] = item["viewId"]
        
        chunk.logger.info("Found %d view(s)" % len(views_lookup))
        
        return views_lookup
    
    def write_describers(self, chunk, images, lookup):
        chunk.logger.info("Writing %s descriptor files" % chunk.node.type.value)
        chunk.logManager.makeProgressBar(len(lookup))
        
        found_markers = {i: 0 for i in list(set([marker[3] for img in images for marker in images[img]]))}
        
        for i, img in enumerate(images):
            viewid = lookup.get(img)
            if not viewid:
                continue
            
            markers = images[img]
            
            feat = open(os.path.join(chunk.node.output.value, viewid + (".%s.feat" % chunk.node.type.value)), "w")
            desc = open(os.path.join(chunk.node.output.value, viewid + (".%s.desc" % chunk.node.type.value)), "wb")
            desc.write(struct.pack('<Q', len(markers)))
            
            for marker in markers:
                found_markers[marker[3]] += 1
                feat.write("%.2f %.2f %.4f 0\n" % (marker[0], marker[1], marker[2]))
                
                data = bytearray(128)
                data[marker[3]] = 255
                
                desc.write(data)
            
            desc.close()
            feat.close()
            
            chunk.logManager.updateProgressBar(i + 1)
            
        chunk.logger.info("Markers report:")
        for marker in found_markers:
            chunk.logger.info("\tFound marker %d in %d view(s)" % (marker, found_markers[marker]))
            
    
    def processChunk(self, chunk):
        delimiters_options = {
            "space": " ",
            "tab": "\t",
            "comma": ",",
            "colon": ":",
            "semicolon": ";"
        }
        
        try:
            chunk.logManager.start(chunk.node.verboseLevel.value)
            
            chunk.logger.info("Importing marker data")
            
            if not os.path.isfile(chunk.node.matches.value):
                raise OSError("Marker features list file not found")
            
            lookup = self.load_viewids(chunk)
            images = self.load_images(chunk, chunk.node.matches.value, delimiters_options[chunk.node.delimiter.value])
            self.write_describers(chunk, images, lookup)
            
            chunk.logger.info("Task done")
            
            
        except Exception as e:
            chunk.logger.error(e)
            raise
        finally:
            chunk.logManager.end()