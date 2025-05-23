import sys
import os
import socket
import threading
import json

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import motor.motor as thorlabs_motor

motor = thorlabs_motor.Motor(serial_number='55356974')

def handle_client(conn, addr):
    print(f"Connected by {addr}")
    with conn:
        while True:
            try:
                data = conn.recv(1024).decode()
                if not data:
                    break
                request = json.loads(data)
                command = request.get("command")

                if command == "move_by":
                    offset = float(request.get("offset", 0))
                    motor.threaded_move_by(angle=offset)
                    response = {"status": f"Moving by {offset}"}

                elif command == "move_to":
                    position = float(request.get("position", 0))
                    motor.threaded_move_to(position=position)
                    response = {"status": f"Moving to {position}"}

                elif command == "jog":
                    direction = thorlabs_motor.MotorDirection(
                        request.get("direction", 0)
                    )
                    motor.jog(direction=direction)
                    response = {"status": f"Jogging in direction {direction.name}"}

                elif command == "stop":
                    motor.stop()
                    response = {"status": "Stopping motor"}

                elif command == "get_position":
                    pos = motor.position
                    moving = motor.is_moving
                    response = {
                        "position": pos,
                        "moving": moving
                    }

                else:
                    response = {"error": "Unknown command"}

                conn.sendall(json.dumps(response).encode())
            except Exception as e:
                conn.sendall(json.dumps({"error": str(e)}).encode())
                break

def start_server(host="0.0.0.0", port=5002):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen()
    print(f"Motor server listening on {host}:{port}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()
