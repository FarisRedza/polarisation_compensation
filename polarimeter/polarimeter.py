import math
import dataclasses
import typing
import pprint
import enum

import pyvisa

Percent = typing.NewType('Percent', float)
Degrees = typing.NewType('Degrees', float)
Radians = typing.NewType('Radians', float)
Watts = typing.NewType('Watts', float)
Metres = typing.NewType('Metres', float)
DecibelMilliwatts = typing.NewType('DecibelMilliwatts', float)

def decibel_milliwatts(power: Watts) -> DecibelMilliwatts:
    if power > 0:
        return 10 * math.log10(power / 1e-3)
    else:
        return 0.0

@dataclasses.dataclass
class DeviceInfo:
    manufacturer: str
    model: str
    serial_number: str
    firmware_version: str

class SCPIDevice:
    def __init__(
            self,
            id: str | None = None,
            serial_number: str | None = None
    ) -> None:
        if id and serial_number:
            id_parts = id.split(':')
            resource_name=f'USB0::0x{id_parts[0]}::0x{id_parts[1]}::{serial_number}::0::INSTR'
        else:
            raise NameError('Device not found')

        self._instrument = pyvisa.ResourceManager().open_resource(
            resource_name=resource_name
        )
        self._check_connection()
        self._reset_command()

    def _check_connection(self) -> None:
        idn = self._identification_query()
        idn_parts = idn.removesuffix('\n').split(',')
        if idn:
            self.device_info = DeviceInfo(
                manufacturer=idn_parts[0],
                model=idn_parts[1],
                serial_number=idn_parts[2],
                firmware_version=idn_parts[3]
            )
            print(f'Connected to {idn}')
        else:
            self.disconnect()
            print(f'Instrument could not be identified')

    def disconnect(self) -> None:
        self._instrument.close()

    def write(self, command: str) -> None:
        self._instrument.write(command)
        
    def query(self, command: str) -> str:
        return str(self._instrument.query(command))

    def _clear_status_command(self) -> None:
        self._instrument.write('*CLS')

    def _standard_event_status_enable_command(self) -> None:
        self._instrument.write('*ESE')
        

    def _standard_event_status_enable_query(self) -> str:
        return str(self._instrument.query('*ESE?'))
    
    def _standard_event_status_register_query(self) -> str:
        return str(self._instrument.query('*ESR?'))
    
    def _identification_query(self) -> str:
        return str(self._instrument.query('*IDN?'))
    
    def _operation_complete_command(self) -> None:
        self._instrument.write('*OPC')
    
    def _operation_complete_query(self) -> str:
        return str(self._instrument.query('*OPC?'))
    
    def _reset_command(self) -> None:
        self._instrument.write('*RST')
        
    def _service_request_enable_command(self) -> None:
        self._instrument.write('*SRE')

    def _service_request_enable_query(self) -> str:
        return str(self._instrument.query('*SRE?'))
    
    def _read_status_byte_query(self) -> str:
        return str(self._instrument.query('*STB?'))
    
    def _self_test_query(self) -> str:
        return str(self._instrument.query('*TST?'))
    
    def _wait_to_continue_command(self) -> None:
        self._instrument.write('*WAI')

    # def cal(self) -> str:
    #     return str(self._instrument.query('*CAL?')

    # def ddt(self) -> str:
    #     return str(self._instrument.query('*DDT?')

    # def emc(self) -> str:
    #     return str(self._instrument.query('*EMC?')

    # def gmc(self) -> str:
    #     return str(self._instrument.query('*GMC?')

    # def ist(self) -> str:
    #     return str(self._instrument.query('*IST?')

    # def lmc(self) -> str:
    #     return str(self._instrument.query('*LMC?')

    # def lrn(self) -> str:
    #     return str(self._instrument.query('*LRN?')

    # def opt(self) -> str:
    #     return str(self._instrument.query('*OPT?')

    # def pre(self) -> str:
    #     return str(self._instrument.query('*PRE?')

    # def psc(self) -> str:
    #     return str(self._instrument.query('*PSC?')

    # def pud(self) -> str:
    #     return str(self._instrument.query('*PUD?')

    # def rdt(self) -> str:
    #     return str(self._instrument.query('*RDT?')

@dataclasses.dataclass
class Data:
    timestamp: float = 0.0
    wavelength: Metres = 0.0
    azimuth: Degrees = 0.0
    ellipticity: Degrees = 0.0
    degree_of_polarisation: Percent = 0.0
    degree_of_linear_polarisation: Percent = 0.0
    degree_of_circular_polarisation: Percent = 0.0
    power: DecibelMilliwatts = 0.0
    power_polarised: DecibelMilliwatts = 0.0
    power_unpolarised: DecibelMilliwatts = 0.0
    normalised_s1: float = 0.0
    normalised_s2: float = 0.0
    normalised_s3: float = 0.0
    S0: Watts = 0.0
    S1: Watts = 0.0
    S2: Watts = 0.0
    S3: Watts = 0.0
    power_split_ratio: float = 0.0
    phase_difference: Degrees = 0.0
    circularity: Percent = 0.0

@dataclasses.dataclass
class RawData:
    """
    wavelength (m)
    revs: number of measurement cycles
    timestamp: milliseconds since start?
    paxOpMode: operation mode of the polarimeter
    paxFlags: status and error flags
    paxTIARange: current setting of the transimpedance amplifier TIA - indicates gain level (e.g low/medium/high sensitivity)
    adcMin/Max: min and max raw ADC values across detectors - for monitor saturation or signal range
    revTime: time for one measurement cycle
    misAdj: misalignment adjustment metric/quality metric
    theta: orientation angle of the polarisation ellipse
    eta: ellipticity angle of the polarisation ellipse
    dop: degree of polarisation
    ptotal: total optical power
    """
    wavelength: str
    revs: str
    timestamp: str
    paxOpMode: str
    paxFlags: str
    paxTIARange: str
    adcMin: str
    adcMax: str
    revTime: str
    misAdj: str
    theta: str
    eta: str
    dop: str
    ptotal: str
    
    def to_data(self) -> Data:
        wavelength = float(self.wavelength)
        revs = float(self.revs)
        timestamp = float(self.timestamp)
        paxOpMode = float(self.paxOpMode)
        paxFlags = float(self.paxFlags)
        paxTIARange = float(self.paxTIARange)
        adcMin = float(self.adcMin)
        adcMax = float(self.adcMax)
        revTime = float(self.revTime)
        misAdj = float(self.misAdj)
        theta = float(self.theta)
        eta = float(self.eta)
        dop = float(self.dop)
        ptotal = float(self.ptotal)

        S0=ptotal
        S1=ptotal * dop * math.cos(2*theta) * math.cos(2*eta)
        S2=ptotal * dop * math.sin(2*theta) * math.cos(2*eta)
        S3=ptotal * dop * math.sin(2*eta)

        return Data(
            timestamp=timestamp,
            wavelength=wavelength,
            azimuth=math.degrees(theta),
            ellipticity=math.degrees(eta),
            degree_of_polarisation=dop * 100,
            degree_of_linear_polarisation=math.sqrt(S1**2 + S2**2)/S0 * 100,
            degree_of_circular_polarisation=abs(S3)/S0 * 100,
            power=decibel_milliwatts(ptotal),
            power_polarised=decibel_milliwatts(dop*ptotal),
            power_unpolarised=decibel_milliwatts((1-dop)*ptotal),
            normalised_s1=S1/S0,
            normalised_s2=S2/S0,
            normalised_s3=S3/S0,
            S0=S0,
            S1=S1,
            S2=S2,
            S3=S3,
            power_split_ratio=math.tan(eta)**2,
            phase_difference=math.degrees(math.atan2(S3,S2)),
            circularity=abs(math.tan(eta)) * 100
        )


class Polarimeter(SCPIDevice):
    class WaveplateRotation(enum.Enum):
        OFF = '0'
        ON = '1'

    class AveragingMode(enum.Enum):
        H512 = '1' # (half waveplate rotation with 512 point FFT)
        H1024 = '2'
        H2048 = '3'
        F512 = '4'
        F1024 = '5' # (one full waveplate rotation with 1024 point FFT)
        F2048 = '6'
        D512 = '7'
        D1024 = '8'
        D2048 = '9' # (two waveplate rotations with 2048 point FFT)

    class AutoRange(enum.Enum):
        OFF = '0'
        ON = '1'
        ONCE = '2'

    def __init__(
            self,
            id: str | None = None,
            serial_number: str | None = None,
            waveplate_rotation: WaveplateRotation = WaveplateRotation.ON,
            averaging_mode: AveragingMode = AveragingMode.F1024
        ):
        super().__init__(
            id=id,
            serial_number=serial_number
        )
        self._input_rotation_state(state=waveplate_rotation.value)
        self._sense_calculate_mode(mode=averaging_mode.value)

    def disconnect(self) -> None:
        self._input_rotation_state(state=self.WaveplateRotation.OFF.value)
        super().disconnect()

    def measure(self) -> RawData:
        wavelength = self._sense_correction_wavelength_query().removesuffix('\n')
        response = self._sense_data_latest().removesuffix('\n').split(',')
        return RawData(
            wavelength=wavelength,
            revs=response[0],
            timestamp=response[1],
            paxOpMode=response[2],
            paxFlags=response[3],
            paxTIARange=response[4],
            adcMin=response[5],
            adcMax=response[6],
            revTime=response[7],
            misAdj=response[8],
            theta=response[9],
            eta=response[10],
            dop=response[11],
            ptotal=response[12]
        )
    
    def set_wavelength(self, wavelength: Metres) -> None:
        self._sense_correction_wavelength(wavelength=str(wavelength))

    def _system_error_next(self) -> str:
        return str(self._instrument.query('SYST:ERR:NEXT?'))
    
    def _system_version(self) -> str:
        return str(self._instrument.query('SYST:VERS?'))
    
    def _status_operation_event(self) -> str:
        return str(self._instrument.query('STAT:OPER:EVEN?'))
    
    def _status_operation_condition(self) -> str:
        return str(self._instrument.query('STAT:OPER:COND?'))
    
    def _status_operation_enable_query(self) -> str:
        return str(self._instrument.query('STAT:OPER:ENAB?'))
    
    def _status_questionable_event(self) -> str:
        return str(self._instrument.query('STAT:QUES:EVEN?'))
    
    def _status_questionable_condition(self) -> str:
        return str(self._instrument.query('STAT:QUES:COND?'))
    
    def _status_questionable_enable_query(self) -> str:
        return str(self._instrument.query('STAT:QUES:ENAB?'))
    
    def _status_auxiliary_event(self) -> str:
        return str(self._instrument.query('STAT:AUX:EVEN?'))
    
    def _status_auxiliary_condition(self) -> str:
        return str(self._instrument.query('STAT:AUX:CON?'))
    
    def _status_auxiliary_enable_query(self) -> str:
        return str(self._instrument.query('STAT:AUX:ENAB?'))

    def _sense_calculate_mode(self, mode: str) -> None:
        self._instrument.write(f'SENS:CALC:MOD {mode}')

    def _sense_calculate_mode_query(self) -> str:
        return str(self._instrument.query('SENS:CALC:MOD?'))
    
    def _sense_correction_wavelength(self, wavelength: str) -> None:
        self._instrument.write(f'SENS:CORR:WAV {wavelength}')
    
    def _sense_correction_wavelength_query(self) -> str:
        return str(self._instrument.query('SENS:CORR:WAV?'))
    
    def _sense_power_range_upper(self, value: str) -> None:
        self._instrument.write(f'SENS:POW:RANG:UPP {value}')
    
    def _sense_power_range_upper_query(self) -> str:
        return str(self._instrument.query('SENS:POW:RANG:UPP?'))
    
    def _sense_power_range_auto(self, value: str) -> None:
        self._instrument.write(f'SENS:POW:RANG:AUTO {value}')
    
    def _sense_power_range_auto_query(self) -> str:
        return str(self._instrument.query('SENS:POW:RANG:AUTO?'))
    
    def _sense_power_range_index_query(self) -> str:
        return str(self._instrument.query('SENS:POW:RANG:IND?'))
    
    def _sense_power_range_nominal_query(self) -> str:
        return str(self._instrument.query('SENS:POW:RANG:NOM?'))
    
    def _sense_data_latest(self) -> str:
        return str(self._instrument.query('SENS:DATA:LAT?'))

    def _calibration_string(self) -> str:
        return str(self._instrument.query('CAL:STR?'))
    
    def _input_rotation_state(self, state: str) -> None:
        self._instrument.write(f'INP:ROT:STAT {state}')

    def _input_rotation_state_query(self) -> str:
        return str(self._instrument.query('INP:ROT:STAT?'))
    
    def _input_rotation_velocity_query(self) -> str:
        return str(self._instrument.query('INP:ROT:VEL?'))
    
    def _input_rotation_velocity_limits(self) -> str:
        return str(self._instrument.query('INP:ROT:VEL:LIM?'))


if __name__ == '__main__':
    pax = Polarimeter(id='1313:8031', serial_number='M00910360')
    pprint.pprint(pax.device_info)
    