from opcua import Server, ua
import threading
import time
import random
import logging

# Disable debug logs
logging.getLogger("opcua").setLevel(logging.ERROR)
stop_event = threading.Event()
# === GLOBAL Server Setup ===
OPC_HOST = "0.0.0.0"
OPC_PORT = 4840
ENDPOINT = f"opc.tcp://{OPC_HOST}:{OPC_PORT}"

server = Server()
server.set_endpoint(ENDPOINT)
server.set_server_name("KEPServerEX Mock")
uri = "http://example.com/opcua"
idx = server.register_namespace(uri)

# === GLOBAL start server ===
server.start()
print(f"✅ OPC UA Server started at {ENDPOINT}")

def smart_sleep(duration_sec):
    steps = int(duration_sec / 0.1)
    for _ in range(steps):
        if stop_event.is_set():
            break
        time.sleep(0.1)

# === MAIN Simulation Function ===
def start_line_simulation(line_no: int):
    try:
        # --- Create Folder for This Line ---
        folder_name = f"LINE{line_no:02d}-MP"
        line_folder = server.nodes.objects.add_folder(idx, folder_name)

        # --- Create 'ASRS' Subfolder ---
        asrs_folder = line_folder.add_folder(idx, "ASRS")

        # --- Create Variables inside 'ASRS' ---
        def add_custom_variable(name: str, datatype):
            node_id_str = f"{folder_name}.ASRS.{name}"
            node = asrs_folder.add_variable(ua.NodeId(node_id_str, idx), name, 0, datatype)
            node.set_writable()
            node.set_attribute(ua.AttributeIds.DisplayName, ua.DataValue(ua.LocalizedText(f"NS2|String|{node_id_str}")))
            return node

        # Variables
        d_registers = {
            "D0147": ua.VariantType.Int16,
            "D0148": ua.VariantType.Int16,
            "D0328": ua.VariantType.UInt16,
            "Distance_X": ua.VariantType.UInt32,
            "Distance_Y": ua.VariantType.UInt16,
            "PresentLevel": ua.VariantType.Int16,
            "ResetFlag": ua.VariantType.Int16,
            "D0130": ua.VariantType.Int16,
            "D0131": ua.VariantType.UInt32,
            "D0133": ua.VariantType.Int16,
            "D0134": ua.VariantType.Int16,
            "D0135": ua.VariantType.UInt32,
            "D0137": ua.VariantType.Int16,
            "D0149": ua.VariantType.Int16,
        }
        d_nodes = {name: add_custom_variable(name, vtype) for name, vtype in d_registers.items()}

        # X_MIN, X_MAX = 1800, 30000
        def get_x_min_max():
            x_min = d_nodes["D0131"].get_value()  # Bay Start
            x_max = d_nodes["D0135"].get_value()  # Bay End
            return x_min, x_max

        def get_level_start_end():
            level_start = d_nodes["D0133"].get_value()  # Level Start
            level_end = d_nodes["D0137"].get_value()    # Level End
            return level_start, level_end

        mode = "WAIT"
        current_level = None
        phase = None

        randomized_disx = random.randint(5000, 28000)
        randomized_disy = random.randint(3000, 6000)
        d_nodes["Distance_X"].set_value(randomized_disx)
        d_nodes["Distance_Y"].set_value(randomized_disy)
        calculated_level = ((randomized_disy - 500) // 1000) + 1
        calculated_level = max(1, min(20, calculated_level))
        d_nodes["PresentLevel"].set_value(calculated_level)

        print(f"[Line{line_no:02d}] 🎲 Random Start Distance_X: {randomized_disx}, Distance_Y: {randomized_disy}, Level: {calculated_level}")

        try:
            while not stop_event.is_set():
                X_STEP = random.randint(900, 1100)
                Y_STEP = random.randint(230, 270)
                X_MIN, X_MAX = get_x_min_max()
                level_start, level_end = get_level_start_end()
                d148 = d_nodes["D0148"].get_value()
                reset_flag = d_nodes["ResetFlag"].get_value()
                x = d_nodes["Distance_X"].get_value()

                if reset_flag == 1:
                    print(f"[Line{line_no:02d}] 🔄 RESET FLAG TRIGGERED!")
                    randomized_disx = random.randint(5000, 28000)
                    randomized_disy = random.randint(3000, 6000)
                    d_nodes["Distance_X"].set_value(randomized_disx)
                    d_nodes["Distance_Y"].set_value(randomized_disy)
                    calculated_level = ((randomized_disy - 500) // 1000) + 1
                    calculated_level = max(1, min(20, calculated_level))
                    d_nodes["PresentLevel"].set_value(calculated_level)
                    print(f"[Line{line_no:02d}] 🎲 Reset_flag Random Start Distance_X: {randomized_disx}, Distance_Y: {randomized_disy}, Level: {calculated_level}")
                    d_nodes["D0148"].set_value(0)
                    d_nodes["D0328"].set_value(0)
                    d_nodes["D0147"].set_value(0)
                    d_nodes["ResetFlag"].set_value(0)
                    d_nodes["D0130"].set_value(0)
                    d_nodes["D0131"].set_value(0)
                    d_nodes["D0133"].set_value(0)
                    d_nodes["D0134"].set_value(0)
                    d_nodes["D0135"].set_value(0)
                    d_nodes["D0137"].set_value(0)
                    current_level = None
                    mode = "WAIT"
                    continue

                if d148 == 36:
                    d_nodes["D0328"].set_value(76)
                    d_nodes["D0147"].set_value(76)
                    print(f"[Line{line_no:02d}] 🔄 Waiting mode triggered by D148 = 36 → Hold status 76")
                    smart_sleep(0.5)
                    continue

                if d148 == 37:
                    d_nodes["D0328"].set_value(0)
                    d_nodes["D0147"].set_value(0)
                    current_level = None
                    print(f"[Line{line_no:02d}] ⛔ Emergency STOP (D0148 = 37)")
                    smart_sleep(0.5)
                    d_nodes["D0148"].set_value(0)
                    mode = "WAIT"
                    continue

                if d148 == 10 and mode == "WAIT":
                    print(f"[Line{line_no:02d}] 🚀 Start moving to Start Bay/Level (D0148 = 10)")
                    mode = "Touring"
                    continue        

                if d148 == 35 and mode == "WAIT":
                    print(f"[Line{line_no:02d}] 🚀 Start Free Move (D0148 = 35)")
                    # อ่านจุดเป้าหมายปลายทางอย่างเดียว
                    free_move_end_x = d_nodes["D0135"].get_value()
                    free_move_end_level = d_nodes["D0137"].get_value()
                    free_move_end_y = 500 + (free_move_end_level - 1) * 1000

                    mode = "FREE_MOVING"
                    continue

                if d148 == 38 and mode == "READY_TO_MOVE":
                    print(f"[Line{line_no:02d}] 🚀 Starting MOVING phase after PREP")
                    d_nodes["D0328"].set_value(7)
                    d_nodes["D0147"].set_value(7)
                    mode = "MOVING"
                    continue

                if d148 == 38 and mode == "WAIT":
                    d_nodes["D0328"].set_value(78)
                    d_nodes["D0147"].set_value(78)
                    time.sleep(1)

                    start_level = level_start
                    target_level = level_end

                    if (
                        start_level <= 0 or target_level <= 0 or
                        start_level > 19 or target_level > 19 or
                        start_level > target_level
                    ):
                        print(f"[Line{line_no:02d}] ❌ Invalid level range")
                        d_nodes["D0133"].set_value(0)
                        d_nodes["D0137"].set_value(0)
                        d_nodes["D0148"].set_value(0)
                        continue

                    current_level = start_level
                    start_y_position = 500 + (start_level - 1) * 1000
                    d_nodes["PresentLevel"].set_value(current_level)
                    d_nodes["Distance_Y"].set_value(start_y_position)
                    d_nodes["D0328"].set_value(2)
                    d_nodes["D0147"].set_value(2)
                    print(f"[Line{line_no:02d}] 🎲 PREP START: Distance_X = {randomized_disx} → Decrease to 1800")
                    mode = "PREP"
                    continue

                if mode == "PREP":
                    if x > X_MIN:
                        new_x = max(X_MIN, x - X_STEP)
                        d_nodes["Distance_X"].set_value(new_x)
                        print(f"[Line{line_no:02d}] ⬅️ PREP: Distance_X → {new_x}")
                    else:
                        print(f"[Line{line_no:02d}] ✅ Ready to start MOVING")
                        d_nodes["D0328"].set_value(7)
                        d_nodes["D0147"].set_value(7)
                        phase = "MOVE_X"
                        mode = "MOVING"
                    smart_sleep(0.5)
                    continue

                if mode == "MOVING":
                    if phase == "MOVE_X":
                        relative_index = current_level - level_start
                        direction = "RIGHT" if relative_index % 2 == 0 else "LEFT"
                        x_target = X_MAX if direction == "RIGHT" else X_MIN
                        print(f"[Line{line_no:02d}] MOVE_X → level: {current_level}, x: {x}, direction: {direction}, x_target: {x_target}, phase: {phase}, mode: {mode}")

                        if (direction == "RIGHT" and x < x_target) or (direction == "LEFT" and x > x_target):
                            step = X_STEP if direction == "RIGHT" else -X_STEP
                            new_x = min(X_MAX, x + step) if step > 0 else max(X_MIN, x + step)
                            d_nodes["Distance_X"].set_value(new_x)
                            d_nodes["D0147"].set_value(7)
                            d_nodes["D0328"].set_value(7)
                            #print(f"{'➡️' if direction == 'RIGHT' else '⬅️'} MOVE_X → {new_x}")
                        else:
                            if current_level >= level_end:
                                print(f"[Line{line_no:02d}] 🏁 Reached final level → STOPPED")
                                d_nodes["D0328"].set_value(0)
                                d_nodes["D0147"].set_value(0)
                                mode = "STOPPED"
                            else:
                                phase = "MOVE_Y"
                                print(f"[Line{line_no:02d}] ↕️ Start MOVE_Y (ขึ้นชั้น)")
                        smart_sleep(0.5)
                        continue

                    if phase == "MOVE_Y":
                        y_current = d_nodes["Distance_Y"].get_value()
                        next_level = current_level + 1
                        y_target = start_y_position + (next_level - level_start) * 1000
                        print(f"[Line{line_no:02d}] MOVE_Y → level: {current_level}, Target level: {next_level}, y: {y_current}, y_target: {y_target}, phase: {phase}, mode: {mode}")
                        if y_current < y_target:
                            new_y = min(y_target, y_current + Y_STEP)
                            d_nodes["Distance_Y"].set_value(new_y)
                            calculated_level = int((new_y - 500) / 1000) + 1
                            calculated_level = max(1, min(20, calculated_level))
                            d_nodes["PresentLevel"].set_value(calculated_level)
                            d_nodes["D0147"].set_value(2)
                            d_nodes["D0328"].set_value(2)
                            #print(f"⬆️ MOVE_Y → {new_y}")
                        else:
                            current_level = next_level
                            d_nodes["PresentLevel"].set_value(current_level)
                            d_nodes["D0147"].set_value(7)
                            d_nodes["D0328"].set_value(7)
                            print(f"[Line{line_no:02d}] ✅ Reached Level {current_level} → Back to MOVE_X")
                            phase = "MOVE_X"
                        smart_sleep(0.5)
                        continue

                if mode == "Touring":
                    x_target = d_nodes["D0131"].get_value()
                    level_target = d_nodes["D0133"].get_value()
                    expected_y = 500 + (level_target - 1) * 1000

                    x_current = d_nodes["Distance_X"].get_value()
                    y_current = d_nodes["Distance_Y"].get_value()

                    # --- Step 1: ขยับ X ให้ตรงเป้า ---
                    if x_current != x_target:
                        step = X_STEP if x_current < x_target else -X_STEP
                        next_x = x_current + step

                        # ✅ ถ้าขยับแล้วเกินเป้า ให้ตั้งตรงเป้าเลย
                        if (step > 0 and next_x > x_target) or (step < 0 and next_x < x_target):
                            next_x = x_target

                        d_nodes["Distance_X"].set_value(next_x)
                        d_nodes["D0147"].set_value(2)
                        d_nodes["D0328"].set_value(2)
                        print(f"[Line{line_no:02d}] ➡️ Touring Moving X: {next_x}")

                    # --- Step 2: พอ X ถึงแล้ว ขยับ Y ---
                    elif y_current != expected_y:
                        step = Y_STEP if y_current < expected_y else -Y_STEP
                        next_y = y_current + step

                        # ✅ ถ้าขยับแล้วเกินเป้า ให้ตั้งตรงเป้าเลย
                        if (step > 0 and next_y > expected_y) or (step < 0 and next_y < expected_y):
                            next_y = expected_y

                        d_nodes["Distance_Y"].set_value(next_y)

                        # อัปเดต PresentLevel ด้วย (เพื่อความแม่น)
                        calculated_level = int((next_y - 500) / 1000) + 1
                        calculated_level = max(1, min(20, calculated_level))
                        d_nodes["PresentLevel"].set_value(calculated_level)

                        d_nodes["D0147"].set_value(2)
                        d_nodes["D0328"].set_value(2)
                        print(f"[Line{line_no:02d}] ⬆️ Touring Moving Y: {next_y}")

                    # --- Step 3: X,Y ถึงเป้าแล้ว ---
                    else:
                        print(f"[Line{line_no:02d}] 🎯 Touring Completed. Reset D0148, D0147, D0328")
                        d_nodes["D0148"].set_value(0)
                        d_nodes["D0147"].set_value(0)
                        d_nodes["D0328"].set_value(0)
                        mode = "WAIT"
                        phase = None

                    smart_sleep(0.5)
                    continue

                if mode == "FREE_MOVING":
                    moved = False

                    x_current = d_nodes["Distance_X"].get_value()
                    y_current = d_nodes["Distance_Y"].get_value()

                    if x_current != free_move_end_x:
                        X_STEP = random.randint(900, 1100)
                        step = X_STEP if x_current < free_move_end_x else -X_STEP
                        next_x = x_current + step

                        if (step > 0 and next_x > free_move_end_x) or (step < 0 and next_x < free_move_end_x):
                            next_x = free_move_end_x

                        d_nodes["Distance_X"].set_value(next_x)
                        d_nodes["D0147"].set_value(2)
                        d_nodes["D0328"].set_value(2)
                        print(f"[Line{line_no:02d}] ➡️ Free Moving X: {next_x}")
                        moved = True

                    if y_current != free_move_end_y:
                        Y_STEP = random.randint(230, 270)
                        step = Y_STEP if y_current < free_move_end_y else -Y_STEP
                        next_y = y_current + step

                        if (step > 0 and next_y > free_move_end_y) or (step < 0 and next_y < free_move_end_y):
                            next_y = free_move_end_y

                        d_nodes["Distance_Y"].set_value(next_y)
                        calculated_level = int((next_y - 500) / 1000) + 1
                        calculated_level = max(1, min(20, calculated_level))
                        d_nodes["PresentLevel"].set_value(calculated_level)
                        d_nodes["D0147"].set_value(2)
                        d_nodes["D0328"].set_value(2)
                        print(f"[Line{line_no:02d}] ⬆️ Free Moving Y: {next_y}")
                        moved = True

                    if moved:
                        smart_sleep(0.5)
                    else:
                        print(f"[Line{line_no:02d}] 🎯 Free Move Completed. Reset only status")
                        d_nodes["D0147"].set_value(0)
                        d_nodes["D0328"].set_value(0)
                        d_nodes["D0148"].set_value(0)
                        mode = "WAIT"
                        phase = None
                    continue

                if current_level is not None and current_level > level_end:
                    # ✅ ดักทิศของชั้นสุดท้าย
                    final_level = level_end
                    final_direction = "RIGHT" if final_level % 2 == 1 else "LEFT"
                    stop_at_x = X_MAX if final_direction == "RIGHT" else X_MIN

                    if (final_direction == "RIGHT" and x < stop_at_x) or (final_direction == "LEFT" and x > stop_at_x):
                        # ยังเดินไปไม่สุด → ดำเนินต่อ
                        step = X_STEP if final_direction == "RIGHT" else -X_STEP
                        new_x = x + step
                        d_nodes["Distance_X"].set_value(new_x)
                        print(f"[Line{line_no:02d}] ⏩ Final Step → Distance_X = {new_x}")
                    else:
                        # ✅ หยุดทันทีเมื่อถึงปลายทางที่ถูกต้อง
                        d_nodes["D0328"].set_value(0)
                        d_nodes["D0147"].set_value(0)
                        print(f"[Line{line_no:02d}] 🏁 Reached final X at final Level → STOPPED")
                        mode = "STOPPED"

                smart_sleep(0.5)
                continue

        except KeyboardInterrupt:
            print("🛑 Server Interrupted by Keyboard")
            return 
    except Exception as e:
        print(f"❌ Error on Line {line_no}: {e}")
        return

# === Start 8 Threads ===
threads = []
for line_no in range(1, 9):
    t = threading.Thread(target=start_line_simulation, args=(line_no,))
    t.daemon = True
    t.start()
    threads.append(t)

# === Keep Running ===
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("🛑 Main Thread: KeyboardInterrupt detected → Sending stop event...")
    stop_event.set()
finally:
    server.stop()
    print("✅ OPC UA Server stopped")
