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

def send_motor_command(command, value=None, host="127.0.0.1", port=5002):
    try:
        with socket.create_connection((host, port), timeout=5) as s:
            request = {"command": command}
            if command == "move_by":
                request["offset"] = value
            elif command == "move_to":
                request["position"] = value
            s.sendall(json.dumps(request).encode())
            response = s.recv(1024)
            return json.loads(response.decode())
    except Exception as e:
        return {"error": str(e)}

def get_position(host="127.0.0.1", port=5002):
    try:
        with socket.create_connection((host, port), timeout=5) as s:
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

        elif choice == "q":
            break
        else:
            print("Invalid choice.")
