import sys
import os
import dataclasses
import pathlib
import threading
import time

import paramiko

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import polarimeter.polarimeter as scpi_polarimeter
import motor.motor as thorlabs_motor
import polarisation_compensation.pol_compensation

@dataclasses.dataclass
class SSHDetails:
    hostname: str
    username: str
    password: str | None = None

mothership_details = SSHDetails(
    hostname='137.195.63.6',
    username='ap2055',
    password='EMQuantumg35'
)

dropship_details = SSHDetails(
    hostname='137.195.89.222',
    username='emqlab-5',
    password='EMQuantumg35'
)

win11vm_details = SSHDetails(
    hostname='192.168.122.95',
    username='Faris Redza',
)

work_laptop = SSHDetails(
    hostname='137.195.112.191',
    username='faris',
    password='Woodlands101'
)

server_details = work_laptop

def main():
    motors = [
        '55356974',
        '55353314'
    ]
    acceleration = thorlabs_motor.MAX_ACCELERATION
    max_velocity = thorlabs_motor.MAX_VELOCITY

    client, server_os = connect_to_server(server_details=server_details)
    # server_motors = list_motors(
    #     client=client,
    #     server_os=server_os
    # )
    # print(f'Server: {server_motors}')

    # move_by(
    #     client=client,
    #     server_os=server_os,
    #     serial_no='55356974',
    #     angle=45,
    #     acceleration=10,
    #     max_velocity=10
    # )
    print('Connection established')
    print(f'Host: {server_details.hostname}')
    print(f'System: {server_os}')

    hwp = '55356974'
    pax = scpi_polarimeter.Polarimeter(
        id='1313:8031',
        serial_number='M00910360'
    )
    while True:
        data = pax.measure().to_data()
        print(data.azimuth)
        if data.azimuth > 5:
            jog(
                client=client,
                server_os=server_os,
                serial_no=hwp,
                direction=thorlabs_motor.MotorDirection.FORWARD
            )
        elif data.azimuth < -5:
            jog(
                client=client,
                server_os=server_os,
                serial_no=hwp,
                direction=thorlabs_motor.MotorDirection.FORWARD
            )
        else:
            stop(
                client=client,
                server_os=server_os,
                serial_no=hwp
            )
        time.sleep(1)


    # print('Jogging motor')
    # jog(
    #     client=client,
    #     server_os=server_os,
    #     serial_no='55356974',
    #     direction=thorlabs_motor.MotorDirection.BACKWARD
    # )
    # for i in range(1,5+1):
    #     print(5+1-i)
    #     time.sleep(1)

    # print('Stopping motor')
    # stop(
    #     client=client,
    #     server_os=server_os,
    #     serial_no='55356974'
    # )

    # thread = threading.Thread(
    #     target=move_motor,
    #     args=(client, server_os, '55356974', 20, acceleration, max_velocity)
    # )
    # thread.start()
    # # time.sleep(1)
    # move_motor(
    #     client=client,
    #     server_os=server_os,
    #     serial_no='55356974',
    #     angle=10,
    #     acceleration=acceleration,
    #     max_velocity=max_velocity
    # )
    # thread.join()

    # move_motor(
    #     client=client,
    #     server_os=server_os,
    #     serial_no='55356974',
    #     angle=45,
    #     acceleration=acceleration,
    #     max_velocity=max_velocity
    # )
    # move_motor(
    #     client=client,
    #     server_os=server_os,
    #     serial_no='55353314',
    #     angle=45,
    #     acceleration=acceleration,
    #     max_velocity=max_velocity
    # )
    client.close()

def list_motors(client: paramiko.SSHClient, server_os: str) -> str:
    server_motors = send_python_command(
        client=client,
        server_os=server_os,
        python_command='list_motors'
    )
    return server_motors

def move_by(
        client: paramiko.SSHClient,
        server_os: str,
        serial_no: str,
        angle: float,
        acceleration: float,
        max_velocity: float
    ) -> None:
    command = f'move_by {serial_no} {angle} {acceleration} {max_velocity}'
    result = send_python_command(
        client=client,
        server_os=server_os,
        python_command=command
    )
    # print(f'Server: {result}')

def jog(
        client: paramiko.SSHClient,
        server_os: str,
        serial_no: str,
        direction: thorlabs_motor.MotorDirection
    ) -> str:
    command = f'jog {serial_no} {direction.value}'
    result = send_python_command(
        client=client,
        server_os=server_os,
        python_command=command
    )
    print(f'Server: {result}')

def stop(
        client: paramiko.SSHClient,
        server_os: str,
        serial_no: str,
    ) -> str:
    command = f'stop {serial_no}'
    result = send_python_command(
        client=client,
        server_os=server_os,
        python_command=command
    )
    print(f'Server: {result}')
    

def send_python_command(client: paramiko.SSHClient, server_os: str, python_command: str) -> str:
    script_name = 'motor_server.py'
    script_dir = pathlib.PurePath('Projects', 'polarisation_compensation')

    match server_os:
        case 'Windows':
            server_dir = pathlib.PureWindowsPath(r'%HOMEDRIVE%%HOMEPATH%', script_dir)
            python_script = ' '.join(
                [
                    f'"{pathlib.PureWindowsPath(server_dir, ".venv", "Scripts", "activate.bat")}"',
                    '&&',
                    'python',
                    f'"{pathlib.PureWindowsPath(server_dir, "ssh", script_name)}"'
                ]
            )

        case 'Linux':
            server_dir = pathlib.PurePosixPath('$HOME', script_dir)
            python_script = ' '.join(
                [
                    f'"{pathlib.PurePosixPath(server_dir, ".venv", "bin", "python3")}"',
                    f'"{pathlib.PurePosixPath(server_dir, "ssh", script_name)}"'
                ]
            )

        case _:
            raise NotImplementedError(f'Unsupported system: {server_os}')

    command = ' '.join([
        python_script,
        python_command
    ])
    return ssh_command(client=client, command=command)

def connect_to_server(server_details: SSHDetails) -> tuple[paramiko.SSHClient, str]:
    client = paramiko.SSHClient()
    client.load_host_keys(pathlib.Path.home() / '.ssh' / 'known_hosts')
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=server_details.hostname,
            username=server_details.username,
            password=server_details.password,
            look_for_keys=True,
            timeout=10
        )
    except paramiko.SSHException as e:
        raise ConnectionError(f'SSH connection failed: {e}')

    output = ssh_command(client=client, command='uname')
    if output:
        if output == 'Linux':
            return client, 'Linux'
        else:
            raise NotImplementedError(f'Unknown posix system')
        
    output = ssh_command(client=client, command='ver')
    if output:
        return client, 'Windows'

    raise NotImplementedError(f'Unknown system')

def ssh_command(client: paramiko.SSHClient, command: str) -> str:
    ssh_stdin, ssh_stdout, ssh_stderr = client.exec_command(command)
    return ssh_stdout.read().decode().strip()


if __name__ == '__main__':
    main()