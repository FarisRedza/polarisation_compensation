import sys
import os
import time

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import quTAG.QuTAG_HR as QuTAG_HR

def init_qutag() -> QuTAG_HR.QuTAG:
    qutag = QuTAG_HR.QuTAG()
    # for channel in range(1, 5):
    #     qutag.setSignalConditioning(
    #         channel=channel,
    #         conditioning=3,
    #         edge=True,
    #         threshold=1
    #     )
    return qutag

if __name__ == '__main__':
    qutag = init_qutag()
    print(qutag.getDeviceInfo(deviceNumber=0))
    
    # for _ in range(0, 10):
    #     data = qutag.getLastTimestamps(reset=True)
    #     print(data)
    #     time.sleep(1)