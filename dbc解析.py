

import tkinter as tk

from tkinter import ttk

from tkinter import filedialog

import cantools

class App(tk.Tk):

    def __init__(self):

        super().__init__()


        self.geometry("800x400")

        self.title("DBC Signal Parser")


        self.dbc = None

        self.signals = []


        self.load_dbc_button = tk.Button(self, text="加载 DBC", command=self.load_dbc)

        self.load_dbc_button.pack()


        self.can_id_label = tk.Label(self, text="CAN ID:")

        self.can_id_label.pack()


        self.can_id_entry = tk.Entry(self)

        self.can_id_entry.pack()


        self.parse_button = tk.Button(self, text="解析 dbc", command=self.parse_signal)

        self.parse_button.pack()


        self.signal_label = tk.Label(self, text="信号:")

        self.signal_label.pack()


        self.signal_combo = ttk.Combobox(self, width=80)

        self.signal_combo.pack()


        self.unit_label = tk.Label(self, text="")

        self.unit_label.pack()


        self.range_label = tk.Label(self, text="")

        self.range_label.pack()


        self.value_label = tk.Label(self, text="输入数值:")

        self.value_label.pack()


        self.value_entry = tk.Entry(self)

        self.value_entry.pack()


        self.condition_label = tk.Label(self, text="条件:")

        self.condition_label.pack()


        self.condition_combo = ttk.Combobox(self, values=["等于", "大于", "小于"])

        self.condition_combo.pack()


        self.stop_button = tk.Button(self, text="停止信号", command=self.stop_signal)

        self.stop_button.pack()


    def load_dbc(self):

        file_path = filedialog.askopenfilename(filetypes=[("DBC 文件", "*.dbc")])


        if file_path:

            self.dbc = cantools.database.load_file(file_path)

            self.signals = []


    def parse_signal(self):

        can_id = int(self.can_id_entry.get(), 16)

        message = self.dbc.get_message_by_frame_id(can_id)


        if message:

            self.signals = message.signals

            self.signal_combo["values"] = [signal.name for signal in self.signals]

            self.signal_combo.bind("<<ComboboxSelected>>", self.on_signal_selected)

        else:

            self.signals = []

            self.signal_combo.set('')

            self.signal_combo["values"] = []


    def on_signal_selected(self, event):

        selected_signal_name = self.signal_combo.get()

        selected_signal = next((signal for signal in self.signals if signal.name == selected_signal_name), None)


        if selected_signal:

            self.unit_label["text"] = f"单位：{selected_signal.unit}"

            self.range_label["text"] = f"范围：{selected_signal.minimum}-{selected_signal.maximum}"

        else:

            self.unit_label["text"] = ""

            self.range_label["text"] = ""


    def stop_signal(self):
        input_value = float(self.value_entry.get())

        condition = self.condition_combo.get()

        selected_signal_name = self.signal_combo.get()

        selected_signal = next((signal for signal in self.signals if signal.name == selected_signal_name), None)


        if selected_signal:

            # Replace this with the actual value from the decoded signal

            decoded_signal_value = 0  # Example value


            if condition == "等于":

                if input_value == decoded_signal_value:

                    print("停止信号：等于")

            elif condition == "大于":

                if input_value > decoded_signal_value:

                    print("停止信号：大于")

            elif condition == "小于":

                if input_value < decoded_signal_value:

                    print("停止信号：小于")

            else:

                print("无效的条件")

        else:
            print("无效信号")
if __name__=="__main__":
    app= App()
    app.mainloop()
    

