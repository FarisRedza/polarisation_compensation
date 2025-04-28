"""
Script that runs a proportional controller on the waveplates based on the Qber and Qx from the UQD.
"""

# import clr
import threading
import time 
import os, sys
import numpy as np

# # Write in file paths of dlls needed. 
# clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.DeviceManagerCLI.dll")
# clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.GenericMotorCLI.dll")
# clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\ThorLabs.MotionControl.IntegratedStepperMotorsCLI.dll")

# # Import functions from dlls. 
# from Thorlabs.MotionControl.DeviceManagerCLI import *
# from Thorlabs.MotionControl.GenericMotorCLI import *
# from Thorlabs.MotionControl.GenericMotorCLI import MotorDirection
# from Thorlabs.MotionControl.IntegratedStepperMotorsCLI import *
# from System import Decimal



# import a bunch of things
import os, sys
from decimal import Decimal

import numpy as np
from pathos import multiprocessing as mp
from pylablib.devices import Thorlabs

# load Ttag library
sys.path.append(os.environ['TTAG'])
# from ttag import *
from ttag.python.ttag import *

# initiate Ttag buffer
if getfreebuffer() == 0:
    buf = TTBuffer(0)
else:
    buf = TTBuffer(getfreebuffer() - 1)

# check if Ttag started
if buf.getrunners() == 0:
    buf.start()
pool = mp.Pool(8)
t_meas = 0.1
t_window = 1.00e-9

#time delays for the 8 detectors.
channel_delays = {
    0:   0e-9, # H780
    1:   0e-9, # V780
    2:   0e-9, # D780
    3:   0e-9, # A780
    4:   0e-9, # H1560
    5:   0e-9, # V1560
    6:   0e-9, # D1560
    7:   0e-9  # A1560
} # 18/01/2025  2-FOLDS

# 780 detectors
patterns = [
    [0, 4], # HH
    [0, 5], # HV
    [1, 4], # VH
    [1, 5], # VV
    [2, 6], # DD
    [2, 7], # DA
    [3, 6], # AD
    [3, 7]  # AA
]

pattern_delays = [[channel_delays[p[0]],channel_delays[p[1]]] for p in patterns]

def init_state():
    # this function prints the Qber and Qx until you press a button.
    stop = False
    def wait_for_input():
        global stop
        input("When you're done manually preparing the state, press Enter to activate the control loop...\n")  # Wait for input
        stop = True
    thread = threading.Thread(target=wait_for_input)
    thread.start()

    while not stop:
        # show the qber and qx
        # time.sleep(0.1)
        twofolds = pool.map(lambda i: buf.multicoincidences(t_meas,t_window,patterns[i],pattern_delays[i]), range(len(patterns)))
        Qber = np.sum(twofolds[1:3])/np.sum(twofolds[:4])
        Qx = np.sum(twofolds[5:7])/np.sum(twofolds[4:])
        print(f"Qber= {Qber} | Qx= {Qx}")
    return Qber, Qx

def main(Qber_ref, Qx_ref):
    """The main entry point for the application"""
    # try:
        # connect to the waveplates  
        # print("Connecting to the waveplates...")
        # DeviceManagerCLI.BuildDeviceList()
        # serial_no_HWP = "55356974"  
        # serial_no_QWP = "55353314"  
        # device_HWP = CageRotator.CreateCageRotator(serial_no_HWP)
        # device_QWP = CageRotator.CreateCageRotator(serial_no_QWP)
        # device_HWP.Connect(serial_no_HWP)
        # device_QWP.Connect(serial_no_QWP)
        # Ensure that the device settings have been initialized.
        # while not (device_HWP.IsSettingsInitialized() and device_QWP.IsSettingsInitialized()):
        #     device_QWP.WaitForSettingsInitialized(200)  # in ms
        #     device_HWP.WaitForSettingsInitialized(200)
        # # Start polling loop and enable device.
        # device_HWP.StartPolling(250)  #250ms polling rate.
        # device_QWP.StartPolling(250)  #250ms polling rate.
        # time.sleep(0.25)
        # device_HWP.EnableDevice()
        # device_QWP.EnableDevice()
        # time.sleep(0.25)  # Wait for device to enable.
        # # Get Device Information and display description.
        # print(device_HWP.GetDeviceInfo().Description)
        # print(device_QWP.GetDeviceInfo().Description)
        # # Load any configuration settings needed by the controller/stage.

        # # can we set the speed higher?

        # device_HWP.LoadMotorConfiguration(serial_no_HWP, DeviceConfiguration.DeviceSettingsUseOptionType.UseDeviceSettings)
        # motor_config_HWP = device_HWP.LoadMotorConfiguration(serial_no_HWP)
        # device_QWP.LoadMotorConfiguration(serial_no_QWP, DeviceConfiguration.DeviceSettingsUseOptionType.UseDeviceSettings)
        # motor_config_QWP = device_QWP.LoadMotorConfiguration(serial_no_QWP)

    # except Exception as e:
    #     print("something prevented initialisation..")
      
    # print("Ready to correct!")

    motor = Thorlabs.KinesisMotor(
        conn='/dev/ttyUSB0',
        scale='K10CR1',
        default_channel=1,
        is_rack_system=False
    )

    motor.setup_velocity(
        acceleration=20,
        max_velocity=25,
        channel=1,
        scale=True
    )

    stop = False
    def wait_for_input():
        global stop
        input("When you're done marvelling at this control, press Enter exit the loop...\n")  # Wait for input
        stop = True
    thread = threading.Thread(target=wait_for_input)
    thread.start()
    sign_hwp = 1
    sign_qwp = 1
    error_signal = 0
    while not stop:
        # first move HWP
        motor.move_by(Decimal(error_signal * 100 * sign_hwp))
        # device_HWP.SetMoveRelativeDistance(Decimal(error_signal*100*sign_hwp))  # in deg
        device_HWP.MoveRelative(60000) # the timeout value we need to accept adn hope the motor is quick enough
        time.sleep(0.1)# give the motor some time to move
        # read out current state
        twofolds = pool.map(lambda i: buf.multicoincidences(t_meas,t_window,patterns[i],pattern_delays[i]), range(len(patterns)))
        Qber = np.sum(twofolds[1:3])/np.sum(twofolds[:4])
        Qx = np.sum(twofolds[5:7])/np.sum(twofolds[4:])
        print(f"Qber= {Qber} | Qx= {Qx}")
        error_signal_new = Qber - Qber_ref + Qx - Qx_ref
        if error_signal_new > error_signal: sign_hwp *= -1  # going the wrong way
        error_signal = error_signal_new

        # then move QWP
        device_QWP.SetMoveRelativeDistance(Decimal(error_signal*100*sign_qwp))  # in deg
        device_QWP.MoveRelative(60000)
        time.sleep(0.1)
        # read out current state
        twofolds = pool.map(lambda i: buf.multicoincidences(t_meas,t_window,patterns[i],pattern_delays[i]), range(len(patterns)))
        Qber = np.sum(twofolds[1:3])/np.sum(twofolds[:4])
        Qx = np.sum(twofolds[5:7])/np.sum(twofolds[4:])
        print(f"Qber= {Qber} | Qx= {Qx}")
        error_signal_new = Qber - Qber_ref + Qx - Qx_ref
        if error_signal_new > error_signal: sign_qwp *= -1  # going the wrong way
        error_signal = error_signal_new
        

    # disconnect because i need to re-init later
    device_QWP.StopPolling()
    device_QWP.Disconnect()
    device_HWP.StopPolling()
    device_HWP.Disconnect()
    print("hey")
    print(time.time()-start, "seconds expired")



if __name__ == "__main__":
    # start with the manual calibration phase
    Qber_ref, Qx_ref = init_state()
    main(Qber_ref, Qx_ref)


## device.MoveContinuousAtVelocity('Forward', new_velocity) 
## device_QWP.MoveTo(Decimal(WP_settings[basis][0]),60000)