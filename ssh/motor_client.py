import sys
import os
import dataclasses
import pathlib
import threading

import paramiko

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import polarimeter.polarimeter as scpi_polarimeter
import motor.motor as thorlabs_motor

@dataclasses.dataclass
class SSHDetails:
    hostname: str
    username: str
    password: str = None

mothership_details = SSHDetails(
    hostname='137.195.63.6',
    username='ap2055',
    password='EMQuantumg35'
)

win11vm_details = SSHDetails(
    hostname='192.168.122.95',
    username='Faris Redza',
)

server_details = win11vm_details

def main():
    motors = [
        '55356974',
        '55353314'
    ]
    acceleration = thorlabs_motor.MAX_ACCELERATION
    max_velocity = thorlabs_motor.MAX_VELOCITY

    client, server_os = connect_to_server(server_details=server_details)
    server_motors = list_motors(
        client=client,
        server_os=server_os
    )
    print(f'Server: {server_motors}')

    thread = threading.Thread(
        target=move_motor,
        args=(client, server_os, '55356974', 20, acceleration, max_velocity)
    )
    thread.start()
    # time.sleep(1)
    move_motor(
        client=client,
        server_os=server_os,
        serial_no='55356974',
        angle=10,
        acceleration=acceleration,
        max_velocity=max_velocity
    )
    thread.join()

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

def list_motors(client: paramiko.SSHClient, server_os: str) -> list[str]:
    server_motors = send_python_command(
        client=client,
        server_os=server_os,
        python_command='list_motors'
    )
    return server_motors

def move_motor(
        client: paramiko.SSHClient,
        server_os: str,
        serial_no: str,
        angle: float,
        acceleration: float,
        max_velocity: float
    ) -> None:
    command = f'move_motor {serial_no} {angle} {acceleration} {max_velocity}'
    result = send_python_command(
        client=client,
        server_os=server_os,
        python_command=command
    )
    print(f'Server: {result}')

def send_python_command(client: paramiko.SSHClient, server_os: str, python_command: str) -> str:
    script_name = 'motor_server.py'
    script_dir = pathlib.PurePath('Projects', 'polarisation')

    match server_os:
        case 'Windows':
            server_dir = pathlib.PureWindowsPath(r'%HOMEDRIVE%%HOMEPATH%', script_dir)
            python_script = ' '.join(
                [
                    rf'"{pathlib.PureWindowsPath(server_dir, '.venv', 'Scripts', 'activate.bat')}"',
                    '&&',
                    'python',
                    rf'"{pathlib.PureWindowsPath(server_dir, script_name)}"'
                ]
            )

        case 'Linux':
            server_dir = pathlib.PurePosixPath('$HOME', script_dir)
            python_script = ' '.join(
                [
                    rf'"{pathlib.PurePosixPath(server_dir, '.venv', 'bin', 'python3')}"',
                    rf'"{pathlib.PurePosixPath(server_dir, script_name)}"'
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