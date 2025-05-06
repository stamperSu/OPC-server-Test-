import flet as ft
from opcua import Client
import asyncio
import signal
import sys
import atexit

OPC_URL = "opc.tcp://191.20.110.47:4840"
NAMESPACE = 2

# ✅ ตัวแปรควบคุม Task และ Client
should_run = True
client = None
status_task = None

def graceful_exit():
    global should_run, client, status_task
    print("🛑 Graceful shutdown...")
    should_run = False
    try:
        if status_task:
            status_task.cancel()
    except:
        pass
    try:
        if client and client.uaclient.session:
            client.disconnect()
    except:
        pass

def main(page: ft.Page):
    global client, status_task, should_run

    page.title = "🔧 SRM Control Panel"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    # ✅ สถานะเชื่อมต่อ
    status_text = ft.Text("🔄 Connecting to OPC UA...", color=ft.Colors.ORANGE)
    page.update()

    try:
        client = Client(OPC_URL)
        client.connect()
        status_text.value = "✅ Connected to OPC UA"
        status_text.color = ft.Colors.GREEN
        page.update()
    except Exception as e:
        status_text.value = f"❌ Failed to connect: {e}"
        status_text.color = ft.Colors.RED
        page.update()
        return

    # ✅ Node Access
    def get_node(name):
        return client.get_node(f"ns={NAMESPACE};s=LINE04-MP.ASRS.{name}")

    d148_node = get_node("D0148")
    reset_flag_node = get_node("ResetFlag")
    level_start_node = get_node("LevelStart")
    level_end_node = get_node("LevelEnd")
    d328_node = get_node("D0328")
    Disx_node = get_node("Distance_X")
    Disy_node = get_node("Distance_Y")
    present_level_node = get_node("PresentLevel")

    title_text = ft.Text("🔧 SRM CONTROL PANEL", size=28, weight="bold", color=ft.Colors.BLUE_800)
    dropdown_start = ft.Dropdown(label="Level Start", width=200, dense=True)
    dropdown_end = ft.Dropdown(label="Level End", width=200, dense=True)
    cmd_dropdown = ft.Dropdown(
        label="CMD (D0148)", width=200, dense=True,
        options=[
            ft.dropdown.Option(text="36 - รอระบบ Audit สั่งการต่อ", key="36"),
            ft.dropdown.Option(text="37 - จบคำสั่งการทำงาน", key="37"),
            ft.dropdown.Option(text="38 - ระบบ Audit ทำงาน", key="38"),
        ]
    )

    status_d328_text = ft.Text("")
    status_x_text = ft.Text("")
    status_y_text = ft.Text("")
    present_level_text = ft.Text("")
    explanation_text = ft.Text(
        "- 36 → รอระบบ Audit สั่งการต่อ\n"
        "- 37 → จบคำสั่งการทำงาน\n"
        "- 38 → ระบบ Audit ทำงาน",
        size=14
    )

    def update_start(e=None):
        if dropdown_end.value:
            end = int(dropdown_end.value)
            dropdown_start.options = [
                ft.dropdown.Option(str(i)) for i in range(1, 21) if i <= end
            ]
        else:
            dropdown_start.options = [ft.dropdown.Option(str(i)) for i in range(1, 21)]
        page.update()

    def update_end(e=None):
        if dropdown_start.value:
            start = int(dropdown_start.value)
            dropdown_end.options = [
                ft.dropdown.Option(str(i)) for i in range(1, 21) if i >= start
            ]
        else:
            dropdown_end.options = [ft.dropdown.Option(str(i)) for i in range(1, 21)]
        page.update()

    dropdown_start.on_change = update_end
    dropdown_end.on_change = update_start

    def send_command(e):
        try:
            if not dropdown_start.value or not dropdown_end.value or not cmd_dropdown.value:
                status_text.value = "⚠️ กรุณาเลือกค่าทั้งหมด"
                return

            start = int(dropdown_start.value)
            end = int(dropdown_end.value)

            if start > end:
                status_text.value = f"❌ Start ({start}) ต้องไม่มากกว่า End ({end})"
                return

            d148_node.set_value(int(cmd_dropdown.value))
            level_start_node.set_value(start)
            level_end_node.set_value(end)
            status_text.value = f"✅ CMD={cmd_dropdown.value}, Start={start}, End={end} ส่งแล้ว"
            update_status_desc()
        except Exception as err:
            status_text.value = f"❌ Error: {err}"
        page.update()

    def trigger_reset(e):
        try:
            reset_flag_node.set_value(1)
            dropdown_start.value = None
            dropdown_end.value = None
            cmd_dropdown.value = None
            status_text.value = "🔁 Reset flag triggered"
            status_text.color = ft.Colors.GREEN
            update_status_desc()
        except Exception as err:
            status_text.value = f"❌ Error: {err}"
            status_text.color = ft.Colors.RED
        page.update()

    def update_status_desc():
        try:
            d328_value = d328_node.get_value()
            disx_value = Disx_node.get_value()
            disy_value = Disy_node.get_value()
            present_level_value = present_level_node.get_value()
            status_d328_text.value = f"D0328 Status: {d328_value}"
            status_x_text.value = f"Distance X: {disx_value}"
            status_y_text.value = f"Distance Y: {disy_value}"
            present_level_text.value = f"Present Level: {present_level_value}"
        except Exception as err:
            status_d328_text.value = f"❌ Error reading D0328: {err}"
            status_x_text.value = f"❌ Error reading Distance X: {err}"
            status_y_text.value = f"❌ Error reading Distance Y: {err}"
            present_level_text.value = f"❌ Error reading Present Level: {err}"

    async def auto_update_status():
        global should_run
        try:
            while should_run:
                update_status_desc()
                page.update()
                await asyncio.sleep(0.5 if should_run else 0.1)
        except asyncio.CancelledError:
            print("🛑 auto_update_status cancelled.")

    def on_disconnect(e):
        global should_run, status_task
        print("🛑 Disconnecting cleanly...")
        should_run = False
        try:
            if status_task:
                status_task.cancel()
        except:
            pass
        try:
            client.disconnect()
        except:
            pass

    update_start()
    update_end()
    update_status_desc()
    atexit.register(graceful_exit)  # เมื่อกด X
    page.on_disconnect = on_disconnect
    global status_task
    status_task = page.run_task(auto_update_status)

    page.add(
        ft.Row([
            ft.Column([
                title_text,
                dropdown_start,
                dropdown_end,
                cmd_dropdown,
                ft.Row([
                    ft.ElevatedButton("Send CMD", on_click=send_command, width=100),
                    ft.ElevatedButton("Reset", on_click=trigger_reset, bgcolor="red", width=100)
                ], alignment=ft.MainAxisAlignment.CENTER),
                status_text
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ft.VerticalDivider(width=40),
            ft.Column([
                ft.Text("📘 คำอธิบายคำสั่ง:", weight="bold"),
                explanation_text,
                ft.Text("📊 สถานะปัจจุบันของเครน:", weight="bold"),
                status_d328_text,
                status_x_text,
                status_y_text,
                present_level_text
            ], alignment=ft.MainAxisAlignment.START)
        ], alignment=ft.MainAxisAlignment.CENTER)
    )

ft.app(
    target=main,
    view=ft.WEB_BROWSER,     # ← รับทุก IP ที่เข้ามา
    host="0.0.0.0",
    port=7000,        # ← เปลี่ยน port ตามที่ต้องการ
)
