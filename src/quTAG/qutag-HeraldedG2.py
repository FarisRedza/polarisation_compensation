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



# This code shows different device settings and their usage. For additional information see the documentation of TDCBase.


try:
        import QuTAG
except:
        print("Time Tagger wrapper QuTAG.py is not in the search path / same folder.")

# Initialize device
qutag = QuTAG.QuTAG()


rc = qutag.enableHg2(True)
print("enableHg2 rc: ", rc)

rc = qutag.setHg2Params(1, 1000)
print("setHg2Params rc: ", rc)

rc = qutag.getHg2Params()
print("getHg2Params rc: ", rc)

rc = qutag.setHg2Input(1, 2, 3)
print("setHg2Input rc: ", rc)

rc = qutag.getHg2Input()
print("getHg2Input rc: ", rc)

rc = qutag.resetHg2Correlations()
print("resetHg2Correlations rc: ", rc)

rc = qutag.calcHg2G2(False)
print("calcHg2G2 rc: ", rc)


rc = qutag.calcHg2Tcp1D(False)
print("calcHg2Tcp1D rc: ", len(rc))

rc = qutag.getHg2Raw()
print("getHg2Raw rc: ", rc)



qutag.deInitialize()
