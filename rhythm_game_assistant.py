import tkinter as tk
from tkinter import ttk
import mss
import numpy as np
import pydirectinput
import threading
import time

# 【关键破壁：解除底层封印】强制取消按键后的隐藏延迟！
pydirectinput.PAUSE = 0

class RhythmGameAssistantRGB_Pro:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("音游视觉辅助系统 - 极限竞速版")
        self.root.geometry("800x450")

        self.monitoring = False
        self.threshold = 140 
        self.cooldown_ms = 40 # 极速冷却时间
        
        self.tracks = {
            'Top': {"name": "上轨", "region": {"top": 200, "left": 400, "width": 15, "height": 50}, "overlay": None, "color": "red"},
            'Mid': {"name": "中轨", "region": {"top": 300, "left": 400, "width": 15, "height": 50}, "overlay": None, "color": "green"},
            'Bot': {"name": "下轨", "region": {"top": 400, "left": 400, "width": 15, "height": 50}, "overlay": None, "color": "blue"}
        }
        self.ui_vars = {}
        self.setup_gui()

    def setup_gui(self):
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(top_frame, text="亮度阈值:").pack(side="left")
        self.threshold_var = tk.IntVar(value=self.threshold)
        ttk.Entry(top_frame, textvariable=self.threshold_var, width=5).pack(side="left", padx=5)

        # 新增冷却时间控制，应对高难度密谱
        ttk.Label(top_frame, text="冷却防抖(ms):").pack(side="left", padx=(10,0))
        self.cooldown_var = tk.IntVar(value=self.cooldown_ms)
        ttk.Entry(top_frame, textvariable=self.cooldown_var, width=5).pack(side="left", padx=5)
        
        self.start_button = ttk.Button(top_frame, text="▶ 开始极速监控", command=self.toggle_monitoring)
        self.start_button.pack(side="right", padx=10)

        track_container = ttk.Frame(self.root)
        track_container.pack(fill="both", expand=True, padx=10)

        for track_id in ['Top', 'Mid', 'Bot']:
            t_data = self.tracks[track_id]
            frame = ttk.LabelFrame(track_container, text=f"{t_data['name']}设置", padding=10)
            frame.pack(side="left", fill="both", expand=True, padx=5)
            
            self.ui_vars[track_id] = {
                'x': tk.IntVar(value=t_data["region"]["left"]), 'y': tk.IntVar(value=t_data["region"]["top"]),
                'w': tk.IntVar(value=t_data["region"]["width"]), 'h': tk.IntVar(value=t_data["region"]["height"])
            }
            
            ttk.Label(frame, text="X / Y:").grid(row=0, column=0, sticky="w")
            ttk.Entry(frame, textvariable=self.ui_vars[track_id]['x'], width=5).grid(row=0, column=1)
            ttk.Entry(frame, textvariable=self.ui_vars[track_id]['y'], width=5).grid(row=0, column=2)
            
            ttk.Label(frame, text="宽 / 高:").grid(row=1, column=0, sticky="w", pady=5)
            ttk.Entry(frame, textvariable=self.ui_vars[track_id]['w'], width=5).grid(row=1, column=1)
            ttk.Entry(frame, textvariable=self.ui_vars[track_id]['h'], width=5).grid(row=1, column=2)
            
            ttk.Button(frame, text="应用位置", command=lambda tid=track_id: self.apply_pos(tid)).grid(row=2, column=0, columnspan=3, pady=5)
            ttk.Button(frame, text=f"显示判定框", command=lambda tid=track_id: self.toggle_overlay(tid)).grid(row=3, column=0, columnspan=3)

        self.status_label = ttk.Label(self.root, text="系统就绪：已解除攻速限制，等待指令。", font=("", 10, "bold"))
        self.status_label.pack(pady=10)

    def apply_pos(self, tid):
        self.tracks[tid]["region"].update({
            "left": self.ui_vars[tid]['x'].get(), "top": self.ui_vars[tid]['y'].get(),
            "width": self.ui_vars[tid]['w'].get(), "height": self.ui_vars[tid]['h'].get()
        })
        if self.tracks[tid]["overlay"]:
            reg = self.tracks[tid]["region"]
            self.tracks[tid]["overlay"].geometry(f"{reg['width']}x{reg['height']}+{reg['left']}+{reg['top']}")

    def toggle_overlay(self, tid):
        if self.tracks[tid]["overlay"]:
            self.tracks[tid]["overlay"].destroy()
            self.tracks[tid]["overlay"] = None
        else:
            self.tracks[tid]["overlay"] = tk.Toplevel(self.root)
            self.tracks[tid]["overlay"].attributes("-alpha", 0.5, "-topmost", True)
            self.tracks[tid]["overlay"].overrideredirect(True)
            reg = self.tracks[tid]["region"]
            self.tracks[tid]["overlay"].geometry(f"{reg['width']}x{reg['height']}+{reg['left']}+{reg['top']}")
            self.tracks[tid]["overlay"].configure(bg=self.tracks[tid]["color"])
            self.tracks[tid]["overlay"].bind("<B1-Motion>", lambda e, t=tid: self.drag_overlay(e, t))

    def drag_overlay(self, event, tid):
        win = self.tracks[tid]["overlay"]
        new_x, new_y = win.winfo_x() + event.x, win.winfo_y() + event.y
        win.geometry(f"+{new_x}+{new_y}")
        self.ui_vars[tid]['x'].set(new_x)
        self.ui_vars[tid]['y'].set(new_y)
        self.tracks[tid]["region"].update({"left": new_x, "top": new_y})

    def toggle_monitoring(self):
        if self.monitoring:
            self.monitoring = False
            self.start_button.config(text="▶ 开始极速监控")
            self.status_label.config(text="已停止", foreground="black")
        else:
            self.monitoring = True
            self.start_button.config(text="⏹ 停止")
            self.status_label.config(text="全功率运行中：帧级色彩捕捉已激活...", foreground="green")
            
            for track_id in ['Top', 'Mid', 'Bot']:
                threading.Thread(target=self.monitor_task, args=(track_id,), daemon=True).start()

    def monitor_task(self, tid):
        with mss.mss() as sct:
            region = self.tracks[tid]["region"]
            last_trigger_time = 0
            
            while self.monitoring:
                img = np.array(sct.grab(region))
                gray = np.mean(img[:, :, :3], axis=2)
                max_brightness = np.max(gray)

                if max_brightness > self.threshold_var.get():
                    current_time = time.time() * 1000
                    
                    # 使用UI面板上设定的极速冷却时间
                    if current_time - last_trigger_time > self.cooldown_var.get():
                        
                        b_mean = np.mean(img[:, :, 0])
                        g_mean = np.mean(img[:, :, 1])
                        r_mean = np.mean(img[:, :, 2])

                        target_key = None
                        # 【合键逻辑优化】加入明确的色差阈值，防止高光白斑干扰
                        if g_mean > r_mean + 15 and g_mean > b_mean + 15:
                            target_key = "both"
                        elif r_mean > b_mean + 10:
                            target_key = "j"   # 粉色高亮
                        else:
                            target_key = "f"   # 蓝色高亮

                        # 【毫秒级无延迟按键】
                        if target_key == "both":
                            pydirectinput.keyDown('f')
                            pydirectinput.keyDown('j')
                            pydirectinput.keyUp('f')
                            pydirectinput.keyUp('j')
                        else:
                            pydirectinput.press(target_key)
                            
                        last_trigger_time = current_time

                time.sleep(0.002) # 仅休眠2毫秒，防止CPU占满，释放极速潜能

if __name__ == "__main__":
    app = RhythmGameAssistantRGB_Pro()
    app.root.mainloop()