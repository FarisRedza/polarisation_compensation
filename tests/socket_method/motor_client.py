import sys
import os
import socket
import threading
import json
import time

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import motor.motor as thorlabs_motor

# def send_motor_command(command, value=None, host="127.0.0.1", port=5002):
def send_motor_command(command, value=None, host="137.195.89.222", port=5002):
    try:
        with socket.create_connection((host, port), timeout=5) as s:
            request = {"command": command}
            if command == "move_by":
                request["offset"] = value
            elif command == "move_to":
                request["position"] = value
            elif command == "jog":
                request["direction"] = value
            s.sendall(json.dumps(request).encode())
            response = s.recv(1024)
            return json.loads(response.decode())
    except Exception as e:
        return {"error": str(e)}

# def get_position(host="127.0.0.1", port=5002):
def get_position(host="137.195.89.222", port=5002):
    try:
        with socket.create_connection((host, port)) as s:
            request = {"command": "get_position"}
            s.sendall(json.dumps(request).encode())
            response = s.recv(1024)
            return json.loads(response.decode())
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    while True:
        print("\nChoose a motor command:")
        print("1. Move by offset")
        print("2. Move to position")
        print("3. Jog motor")
        print("4. Stop motor")
        print("q. Quit")

        choice = input("Your choice: ").strip().lower()
        if choice in ("1", "2"):
            val = input("Enter value: ")
            command = "move_by" if choice == "1" else "move_to"
            result = send_motor_command(command, float(val))
            print("Command sent:", result.get("status") or result.get("error"))

            # Start polling for position updates
            while True:
                update = get_position()
                if "error" in update:
                    print("Error:", update["error"])
                    break
                print(f"Position: {update['position']:.3f}  |  Moving: {update['moving']}")
                if not update["moving"]:
                    break
                time.sleep(1)
        
        elif choice == "3":
            print("\nChoose direction")
            print("1. Forward")
            print("2. Backward")
            val = input()
            command = "jog"
            if val in ("1", "2"):
                if val == "1":
                    direction = thorlabs_motor.MotorDirection.FORWARD
                else:
                    direction = thorlabs_motor.MotorDirection.BACKWARD
                result = send_motor_command(command=command, value=direction.value)
                print("Command sent:", result.get("status") or result.get("error"))
            else:
                print("Invalid choice.")

        elif choice == "4":
            command = "stop"
            result = send_motor_command(command=command)
            print("Command sent:", result.get("status") or result.get("error"))

        elif choice == "q":
            break
        else:
            print("Invalid choice.")
