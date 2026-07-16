# Example for using the Coincidence Counters with python + quTAG
#
# Author: qutools GmbH
# Last edited: June 2021
#
# Tested with python 3.7 (32bit & 64bit), Windows 10 (64bit)
#
# This is demo code. Use at your own risk. No warranties.
#
# It may be used and modified with no restriction; raw copies as well as 
# modified versions may be distributed without limitation.

import QuTAG
import time

# initialize device
qutag = QuTAG.QuTAG()


### Let's search for quTAG devices connected via USB.
# The following function initializes the library and searches for connected TDC devices. All existing device connections are closed.
numberOfDevices = qutag.discover()
print("Numer of Devices found: "+str(numberOfDevices))


# The following if condition is only for adressing individual devices 0 and 1, without throwing an error
if (numberOfDevices > 1):
        ### Now connect to all devices found.
        for i in range(numberOfDevices):
                print("Connecting to device "+str(i))
                # Connect to a divice by device number. The device number are given by: 0 ≤ "device number" < "discovered devices"
                qutag.connect(i)
	

        ### Now let's change some settings in the first two devices
        # Therefore we address the first device. The following command selects the device as the target of the following function calls.
        qutag.addressDevice(0)
        # Let's change for the first device e.g. the exposure time (or integration time) of the internal coincidence counters in milliseconds, range = 0...65535
        qutag.setExposureTime(100) # 100 ms exposure time


        ### Then the next device.
        qutag.addressDevice(1)
        qutag.setExposureTime(200) # 200 ms exposure time


        print("Sleep for accumulating data")
        time.sleep(1)


        # Let's retrieve countrates of both devices.
        qutag.addressDevice(0)
        data,updates = qutag.getCoincCounters()
        print("Device 0 - Data: ", data)

        qutag.addressDevice(1)
        data,updates = qutag.getCoincCounters()
        print("Device 1 - Data: ", data)



        ## Deinitialize all devices individually devices
        #for i in range(numberOfDevices):
        #        print("Disconnecting device "+str(i))
        #        qutag.disconnect(i)


### An alternative to disconnect from all devices at the same time:
qutag.deInitialize()
