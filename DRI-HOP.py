# DRI-HOP.py
#  "Direct Relief Integration for higher optical performance"

# code to take a GeMS geodatabase (MUP feature class, DMU table) and a hillshaded DEM,
# assume Symbol values in DMU table are for WPGCMYK, and that there is an extra column
#   "ValBump" in the DMU
# and make an HSV stack with stretched and "bumped" VALs for specified units,
# ready for display with the raster HSV function

versionString = 'DRI-HOP.py, version of 28 March 2018'

import arcpy, os.path, sys
from arcpy.sa import *
from wpgdict import wpgcmykgdict

################### Utility functions ##################
def addMsgAndPrint(msg, severity=0): 
    # prints msg to screen and adds msg to the geoprocessor (in case this is run as a tool) 
    #print msg 
    try: 
        for string in msg.split('\n'): 
            # Add appropriate geoprocessing message 
            if severity == 0: 
                arcpy.AddMessage(string) 
            elif severity == 1: 
                arcpy.AddWarning(string) 
            elif severity == 2: 
                arcpy.AddError(string) 
    except: 
        pass

def forceExit():
    addMsgAndPrint( 'Forcing exit by raising ExecuteError' )
    raise arcpy.ExecuteError

def testAndDelete(fc):
    if arcpy.Exists(fc):
        arcpy.Delete_management(fc)

def fieldNameList(aTable):
    fns = arcpy.ListFields(aTable)
    fns2 = []
    for fn in fns:
        fns2.append(fn.name)
    return fns2

###################################

gdb = 'C:/arcdata/scratch/BSLW.gdb'
hillshade = 'D:/PnwLidar/2013Bellingham.gdb/bellingham_be_ne'

stretch = 0.9 # factor by which we stretch the input hillshade, is floating point  
newMean = 225 # mean value of new hillshade, needs be integer 0..255
floor = 200   # smallest allowable brightness in new hillshade, needs be integer 0..255


## read inputs from ArcMap tool interface
hillshade = sys.argv[1]
gdb = sys.argv[2]
if sys.argv[3] == 'true':
    assayHillshade = True
else:
    assayHillshade = False

stretch = float(sys.argv[4])
newMean = int(sys.argv[5])
floor = int(sys.argv[6])
cellMultiplier = float(sys.argv[7])
if sys.argv[8] == 'true':
    forceFailure = True
else:
    forceFailure = False



inDmu = gdb+'/DescriptionOfMapUnits'
mup = gdb+'/GeologicMap/MapUnitPolys'

##### test for inputs, including ValBump field in DMU. If not present, bail.
if not arcpy.Exists(inDmu):
    addMsgAndPrint('cannot find DMU table in '+gdb)
    forceExit()
if not arcpy.Exists(mup):
    addMsgAndPrint('cannot find MapUnitPolys in '+gdb)
    forceExit()
if not arcpy.Exists(hillshade):
    addMsgAndPrint('cannot find hillshade '+hillshade)
    forceExit()
fList = fieldNameList(inDmu)

# we assume hosting workspace for gdb is writable
scratchDir = os.path.dirname(gdb)
scratch = scratchDir+'/xxxscratch.gdb'
testAndDelete(scratch)
arcpy.CreateFileGDB_management(scratchDir, 'xxxscratch.gdb')

arcpy.CheckOutExtension("Spatial")

addMsgAndPrint('Getting hillshade properties')
desc = arcpy.Describe(hillshade)
cellSize = desc.meanCellWidth
spatialRef = desc.spatialReference
mean = float(arcpy.GetRasterProperties_management(hillshade, 'MEAN').getOutput(0))
if assayHillshade:
    stDev = float(arcpy.GetRasterProperties_management(hillshade,'STD').getOutput(0))
    addMsgAndPrint(hillshade)
    addMsgAndPrint('  mean =      '+str(mean))
    addMsgAndPrint('  st dev =    '+str(stDev))
    addMsgAndPrint('  cell size = '+str(cellSize))
    addMsgAndPrint('==========NOTHING IS WRONG==========')
    forceExit()
    
#### get unit color info
# copy DMU into scratch
dmu = scratch+'/DescriptionOfMapUnits'
arcpy.Copy_management(inDmu,dmu)

# add R G B fields to scratchDMU
for f in ['Red','Blue','Green']:
    arcpy.AddField_management(dmu,f,'SHORT')

# open update cursor on scratchDMU, calculate Hue, Sat, Val values from Symbol,
#  and update
addMsgAndPrint('Updating '+scratch+'/DMU')
fields = ['Symbol','Red','Green','Blue','MapUnit']
with arcpy.da.UpdateCursor(dmu, fields) as cursor:
    for row in cursor:
      if row[0] <> None and str(row[0]) <> "<Null>":
        #addMsgAndPrint(str(row[4])+'=='+str(row[0]))
        wpgNum = int(row[0])  # Symbol is text, wpgNum needs to be integer
        RGB = wpgcmykgdict[wpgNum][0]
        addMsgAndPrint('  '+str(row[4])+', '+str(wpgNum)+', '+RGB)
        rgb = RGB.split(',')
        
        row[1] = int(rgb[0])
        row[2] = int(rgb[1])
        row[3] = int(rgb[2])
        cursor.updateRow(row) 

##### make some grids
## Set environment
arcpy.env.outputCoordinateSystem = hillshade
arcpy.env.cellSize = cellSize * cellMultiplier
arcpy.env.snapRaster = hillshade
arcpy.env.extent = mup

# turn MUP into scratch rasters for Hue, Sat, Val, ValBump
if 'ValBump' in fieldNameList(dmu):
    ValBumpExists = True
else:
    ValBumpExists = False
    ValBump = 0
arcpy.MakeFeatureLayer_management ( mup, "polylayer")
arcpy.AddJoin_management( "polylayer", "MapUnit", dmu, "MapUnit")
for attrib in ['Red','Green','Blue']:
    addMsgAndPrint('Making '+attrib+' raster')
    arcpy.FeatureToRaster_conversion('polylayer','DescriptionOfMapUnits.'+attrib,scratch+'/'+attrib)
if ValBumpExists:
    addMsgAndPrint('Making ValBump raster')
    arcpy.FeatureToRaster_conversion('polylayer','DescriptionOfMapUnits.ValBump',scratch+'/ValBump')

addMsgAndPrint('Calculating new hillshade')
addMsgAndPrint('  turn hillshade nulls white')
newShade1 = Con(IsNull(hillshade),255,hillshade)
newShade1.save(scratch+'/newshade1')
# stretch and shift, add ValBump, +0.5 to turn Int into Round
addMsgAndPrint('  stretch and shift hillshade')
newShade2 = Int((newShade1 - mean) * stretch + newMean + Raster(scratch+'/ValBump') + 0.5)
newShade2.save(scratch+'/newshade2')
testAndDelete(newShade1)
addMsgAndPrint('  truncate newShade at upper limit = 255')
newShade3 = Con(newShade2, 255, newShade2, "VALUE > 255")
testAndDelete(newShade2)
addMsgAndPrint('  truncate newShade at lower limit = '+str(floor))
newShade4 = Con(newShade3, floor, newShade3, "VALUE < "+str(floor))
testAndDelete(newShade3)

addMsgAndPrint('Calculating newRed')
newRed0 = Raster(scratch+'/Red') - 255 + newShade4
newRed1 = Con(newRed0,0,newRed0, "VALUE < 0")
newRed = Con(IsNull(newRed1),255,newRed1)
addMsgAndPrint('  saving newRed')
newRed.save(scratch+'/newRed')

addMsgAndPrint('Calculating newGreen')
newGreen0 = Raster(scratch+'/Green') - 255 + newShade4
newGreen1 = Con(newGreen0,0,newGreen0, "VALUE < 0")
newGreen = Con(IsNull(newGreen1),255,newGreen1)
addMsgAndPrint('  saving newGreen')
newGreen.save(scratch+'/newGreen')

addMsgAndPrint('Calculating newBlue')
newBlue0 = Raster(scratch+'/Blue') - 255 + newShade4
newBlue1 = Con(newBlue0,0,newBlue0, "VALUE < 0")
newBlue = Con(IsNull(newBlue1),255,newBlue1)
addMsgAndPrint('  saving newBlue')
newBlue.save(scratch+'/newBlue')

# make multiband RGB raster ( arcpy.CompositeBands_management)
#testAndDelete(scratchDir+'/rgbComposite.tif')
addMsgAndPrint('Compositing rasters')
rasterName = os.path.basename(gdb)[:-4]+'_rgbComposite.png'
testAndDelete(scratchDir+'/'+rasterName)
#arcpy.CompositeBands_management([scratch+'/newRed',scratch+'/newGreen',scratch+'/newBlue'],scratch+'/rgbComposite')
arcpy.CompositeBands_management([newRed,newGreen,newBlue],scratchDir+'/'+rasterName)

arcpy.CheckInExtension("Spatial")

pgw = open(scratchDir+'/'+rasterName[:-4]+'.pgw','a')
pgw.write('\n\n'+versionString+'\n')
pgw.write('mup = '+mup+'\n')
pgw.write('hillshade = '+hillshade+'\n')
pgw.write('stretch = '+str(stretch)+'\n')
pgw.write('newMean = '+str(newMean)+'\n')
pgw.write('floor = '+str(floor)+'\n')
pgw.write('cellMultiplier = '+str(cellMultiplier)+'\n')
pgw.close()    

# delete intermediate stuff:
for r in newGreen0, newRed0, newBlue0, newGreen1, newRed1, newBlue1, newRed, newGreen, newBlue, newShade4:
    testAndDelete(r)



addMsgAndPrint("Done")
if forceFailure:
    addMsgAndPrint('==========NOTHING IS WRONG==========')
    forceExit()
    
