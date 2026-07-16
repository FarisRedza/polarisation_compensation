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

import matplotlib.pyplot as plt
from matplotlib import style
import numpy as np # for a array to set a channel delay 

import QuTAG

# initialize device
qutag = QuTAG.QuTAG()

# define channels
start = 0
stop = 1

# define lifetime histogram
binwidth = 1
bincount = 100


# Let's set some channel delays for adjusting the lifetime curve to the propper starting point at time difference zero
delays = np.zeros(int(8), dtype=np.int32)
delays[0] = 140 # ps
qutag.setChannelDelays(delays)



# enable lifetime
print("Enable: ", qutag.enableLFT(True))

# liftetime start input
qutag.setLFTStartInput(start) 

# set the parameters for the lifetime histigram
qutag.setLFTParams(binwidth, bincount)

# add the histogram with the desired stop channel and the before defined start input
qutag.addLFTHistogram(stop,True)


# create function
lftfunction = qutag.createLFTFunction()


params = qutag.getLFTParams()
print("params: ", params)

# get the lifetime histogram
histo  = qutag.getLFTHistogram(stop,True,lftfunction)
print("histo: ", histo)

# let's have a look at the histogram by the analyse function. It disassembles a function description object to its components. The object itself stays valid. May be useful for non-C/C++ programmers, e.g. here in Python.
# for more information, see: https://qutools.com/files/quTAG/documentation/tdclifetm_8h.html#a3e032338d4f6ccf6fba683258e18d601
analyse = qutag.analyseLFTFunction(lftfunction)
print("analyse: ", analyse)


qutag.deInitialize()


# Plotting with mathplotlib
style.use('fivethirtyeight')
fig = plt.figure()
fig.set_size_inches(10,7)
ax1 = fig.add_subplot(1,1,1)
plt.cla() # clear old plotting data
# plot the datapoints
plt.ticklabel_format(axis="y", style="sci", scilimits=(0,0))
plt.plot(analyse[3])
ax1.set_title('quTAG Lifetime')		
plt.pause(0.05)
