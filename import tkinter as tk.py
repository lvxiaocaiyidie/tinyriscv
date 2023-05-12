import tkinter as tk
import tkinter.messagebox
import pyvisa
import can
import cantools
import time
from tkinter import ttk,StringVar
import os
os.add_dll_directory('C:\\Program Files (x86)\\Keysight\\IO Libraries Suite\\bin')
import datetime
import threading
stop_requested=False
# PowerSupplyController 类
class PowerSupplyController:
    def __init__(self, address):
        self.rm = pyvisa.ResourceManager()
        self.device = self.rm.open_resource(address)
    
    def set_output_voltage(self, voltage):
        self.device.write(f'INST OUT1;VOLT {voltage}')  # 设置输出电压

    def get_output_voltage(self):
        return float(self.device.query('MEAS:VOLT?'))  # 读取电源输出电压
# CANReader 类
class CANReader:

    def __init__(self, channel="PCAN_USBBUS1", bitrate=500000, filtered_addresses=None):
        self.channel = channel
        self.bitrate = bitrate

        if filtered_addresses is None:
            self.filtered_addresses = []
        else:
            self.filtered_addresses = filtered_addresses
        print(self.channel,'bitrate',self.bitrate)
        self.bus = can.interface.Bus(channel=self.channel, bustype='pcan', bitrate=self.bitrate)
        #self.message_reader = self.bus.connect()

    def read_messages(self):
        messages = []
        while len(messages) < len(self.filtered_addresses):
            message = self.bus.recv()

            if message.arbitration_id in self.filtered_addresses:
                messages.append(message)

        return messages

# DBCProcessor 类
class DBCProcessor:
    def __init__(self, dbc_file):
        self.db = cantools.database.load_file(dbc_file)
        print(dbc_file)
    def parse_messages_using_dbc(self, messages):
        result = {}
        for message in messages:
            parsed_data = self.db.decode_message(message.arbitration_id, message.data)
            result[message.arbitration_id] = parsed_data

        return result
    def get_signals_by_can_id(self, can_id):
       signals = []
       
       for message in self.db.messages:
           if message.frame_id == can_id:
               signals.extend([signal.name for signal in message.signals])
              
       return signals

    def get_signal_position_by_name(self, can_id, signal_name):
       for message in self.db.messages:
           if message.frame_id == can_id:
               for signal in message.signals:
                   if signal.name == signal_name:
                       return signal.start_bit
# GUI 类
class GUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("电源控制以及CAN数据monitor")
        self.window.geometry("950x500")
        self.window.configure(bg="lightgray")

        self.create_connection_setting_area()
        self.create_voltage_setting_area()
        self.create_voltage_cycles_area()
        self.create_filter_condition_area()
        self.create_action_buttons()
        
        global stop_requested
        stop_requested= False
   

    def create_connection_setting_area(self):
        connection_setting_frame = ttk.LabelFrame(self.window, text="连接设置")
        connection_setting_frame.grid(row=0, column=0, padx=20, pady=20, sticky='nw')

        ttk.Label(connection_setting_frame, text="DBC文件路径:").grid(row=0, column=0, padx=5, pady=5)
        self.dbc_file_var = tk.StringVar(value='C:\\Users\\leylv\\Downloads\\Lychee_VEH.dbc')
        ttk.Entry(connection_setting_frame, textvariable=self.dbc_file_var, width=30).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(connection_setting_frame, text="Channel:").grid(row=1, column=0, padx=5, pady=5)
        self.channel_var = tk.StringVar(value="PCAN_USBBUS1")
        ttk.Entry(connection_setting_frame, textvariable=self.channel_var, width=30).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(connection_setting_frame, text="Bitrate:").grid(row=2, column=0, padx=5, pady=5)
        self.bitrate_var = tk.IntVar(value=500000)
        ttk.Entry(connection_setting_frame, textvariable=self.bitrate_var, width=30).grid(row=2, column=1, padx=5, pady=5)


    def create_voltage_setting_area(self):
        voltage_setting_frame = ttk.LabelFrame(self.window, text="电压设置")
        voltage_setting_frame.grid(row=0, column=1, padx=20, pady=20, sticky='nw')

        ttk.Label(voltage_setting_frame, text="设置电压(V):").grid(row=0, column=0, padx=5, pady=5)
        self.voltage_var = tk.DoubleVar(value=14)
        ttk.Entry(voltage_setting_frame, textvariable=self.voltage_var, width=10).grid(row=0, column=1, padx=5, pady=5)

    def create_voltage_cycles_area(self):
        voltage_cycles_frame = ttk.LabelFrame(self.window, text="电压周期设置")
        voltage_cycles_frame.grid(row=0, column=2, padx=20, pady=20, sticky='nw')

        ttk.Label(voltage_cycles_frame, text="时间 Off (s):").grid(row=0, column=0, padx=5, pady=5)
        self.duration_1_var = tk.IntVar(value=2)
        ttk.Entry(voltage_cycles_frame, textvariable=self.duration_1_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(voltage_cycles_frame, text="时间 On (s):").grid(row=1, column=0, padx=5, pady=5)
        self.duration_2_var = tk.IntVar(value=10)
        ttk.Entry(voltage_cycles_frame, textvariable=self.duration_2_var, width=10).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(voltage_cycles_frame, text="重复次数:").grid(row=2, column=0, padx=5, pady=5)
        self.repeat_cycles_var = tk.IntVar(value=10)
        ttk.Entry(voltage_cycles_frame, textvariable=self.repeat_cycles_var, width=10).grid(row=2, column=1, padx=5, pady=5)

    def create_filter_condition_area(self):
        filter_condition_frame = ttk.LabelFrame(self.window, text="过滤条件设置")
        filter_condition_frame.grid(row=1, column=0, padx=20, pady=20, columnspan=3, sticky='nw')
        
        self.signal_option_menus=[]
        self.signal_vars  =[]
        self.can_id_vars = []
        self.stop_condition_number_vars = []
        self.stop_condition_operator_vars = []

        ttk.Label(filter_condition_frame, text="CAN ID").grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(filter_condition_frame, text="停止条件符号").grid(row=1, column=0, padx=5, pady=5)
        ttk.Label(filter_condition_frame, text="停止条件值").grid(row=2, column=0, padx=5, pady=5)

        for i in range(10):
            can_id_var = tk.StringVar()
            self.can_id_vars.append(can_id_var)
            signal_var = tk.StringVar()
            self.signal_vars.append(signal_var)
            signal_option_menu =ttk.OptionMenu(filter_condition_frame, signal_var,"")
            signal_option_menu.grid(row=8, column=i+1, padx=5, pady=5)
            stop_condition_number_var = tk.StringVar()
            self.stop_condition_number_vars.append(stop_condition_number_var)
            stop_condition_operator_var = tk.StringVar()
            self.stop_condition_operator_vars.append(stop_condition_operator_var)

            ttk.Entry(filter_condition_frame, textvariable=can_id_var, width=8).grid(row=0, column=i + 1, padx=5, pady=5)

            operator = ttk.OptionMenu(filter_condition_frame, stop_condition_operator_var, '等于', '小于', '大于')
            operator.grid(row=1, column=i + 1, padx=5, pady=5)
            self.signal_option_menus.append(signal_option_menu)
            ttk.Entry(filter_condition_frame, textvariable=stop_condition_number_var, width=8).grid(row=2, column=i + 1, padx=5, pady=5)
        
        self.can_id_vars[0].trace("w",lambda *args,var=can_id_var:self.update_signal_options(var))
        self.stop_relation_var = tk.StringVar()
        ttk.Label(filter_condition_frame, text="停止条件关系").grid(row=3, column=0, padx=5, pady=5)
        relation = ttk.OptionMenu(filter_condition_frame, self.stop_relation_var, 'And', 'Or')
        relation.grid(row=3, column=1, padx=5, pady=5)


    def update_signal_options(self, event):
        
        # 获取有效的CAN ID

        can_ids = [can_id_var.get() for can_id_var in self.can_id_vars if can_id_var.get()]
        dbc_processor=DBCProcessor(dbc_file=self.dbc_file_var.get())
        
        if can_ids:

            # 清空原有选项

            for signal_var, signal_option_menu in zip(self.signal_vars, self.signal_option_menus):

                signal_var.set("")

                signal_option_menu['menu'].delete(0, 'end')


            # 更新信号选项

            for can_id in can_ids:

                # 根据CAN ID获取对应的信号列表
                
                signals = dbc_processor.get_signals_by_can_id(can_id)
                print(signals,can_id)
                # 添加信号选项

                for signal in signals:

                    self.signal_option_menus[can_ids.index(can_id)]['menu'].add_command(

                        label=signal, command=lambda value=signal: self.signal_vars[can_ids.index(can_id)].set(value))


    def create_action_buttons(self):
        action_frame = ttk.Frame(self.window)
        action_frame.grid(row=2, column=1, padx=20, pady=20, sticky='nw')

        ttk.Button(action_frame, text="启动", command=self.start_power_cycle_thread).grid(row=0, column=0, padx=10, pady=10)
        ttk.Button(action_frame, text="停止", command=self.stop_and_save_data_thread).grid(row=0, column=1, padx=10, pady=10)
    
   
    
    def start_power_cycle(self):
        global stop_requested
       
        selected_signals =[signal_var.get() for signal_var in self.signal_vars]
       
       
        # 获取用户输入的值
        stop_requested = False
        dbc_file = self.dbc_file_var.get()
        channel = self.channel_var.get()
        bitrate = self.bitrate_var.get()
       
        psc = PowerSupplyController ( address='ASRL4::INSTR')
        self.stop_power_cycle()
        duration_1 = self.duration_1_var.get()
        duration_2 = self.duration_2_var.get()
        repeat_cycles = self.repeat_cycles_var.get()

        filtered_addresses = [int(can_id.get(), 16) for can_id in self.can_id_vars if can_id.get()]
        can_reader = CANReader(channel=channel, bitrate=bitrate, filtered_addresses=filtered_addresses)
        dbc_processor = DBCProcessor(dbc_file=self.dbc_file_var.get())

        # 在此添加时间戳
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_data_file = f"raw_data_{timestamp}.txt"
        decoded_data_file = f"decoded_data_{timestamp}.txt"
        
        # 如果文件不存在，则创建文件
        if not os.path.exists(raw_data_file):
            with open(raw_data_file, "w") as f:
                pass
            
        if not os.path.exists(decoded_data_file):
            with open(decoded_data_file, "w") as f:
                pass
            

        # 新增：打开文件以记录原始信号和解码后的信号
        with open(raw_data_file, "w") as raw_data_file, open(decoded_data_file, "w") as decoded_data_file:

            stop_conditions = []
            for can_id_var, operator_var, value_var,signal_var in zip(self.can_id_vars, self.stop_condition_operator_vars,
                                            self.stop_condition_number_vars),self.signal_vars:
                if can_id_var.get() and signal_var.get():
                    can_id = int(can_id_var.get(), 16)
                    operator= operator_var.get()
                    value= int(value_var.get(),16)
                    signal_name=signal_var.get()
                    signal_position =dbc_processor.get_signal_position_by_name(can_id, signal_name)
                    if signal_position is not None:
                        stop_conditions.append((can_id, operator_var.get(), int(value_var.get(), 16)))

            for _ in range(repeat_cycles):
                
                psc.set_output_voltage(0)
                self.window.after(1000 * duration_1, psc.set_output_voltage(self.voltage_var.get()))

                start_time = time.time()
                while (time.time() - start_time) < duration_2:
                    can_data = can_reader.read_messages()
                    parsed_data = dbc_processor.parse_messages_using_dbc(can_data)

                    # 新增：记录原始信号和解码后的信号到文件
                    raw_data_file.write(f"{can_data}\n")
                    decoded_data_file.write(f"{parsed_data}\n")
                    print(stop_requested)
                    if stop_requested==True:
                        tkinter.messagebox.showinfo("终止" ,"手动停止")
                        return
                    satisfied_conditions = 0
                    for can_id, operator, value in stop_conditions:
                        if can_id in parsed_data:
                            match = False
                            if operator == "等于":
                                match = parsed_data[can_id] == value
                            elif operator == "小于":
                                match = parsed_data[can_id] < value
                            elif operator == "大于":
                                match = parsed_data[can_id] > value

                            if match:
                                satisfied_conditions += 1
                                if self.stop_relation_var.get() == "Or":
                                    psc.set_output_voltage(0)
                                    tkinter.messagebox.showinfo("终止", f"停止条件已被触发。CAN ID: {can_id}")
                                    return
                            
                    if self.stop_relation_var.get() == "And" and satisfied_conditions == len(stop_conditions):
                        psc.set_output_voltage(0)
                        tkinter.messagebox.showinfo("终止", f"所有停止条件已被触发。")
                        return

                    time.sleep(0.1)

                psc.set_output_voltage(0)
                time.sleep(duration_1)
    
    def start_power_cycle_thread(self):
        t=threading.Thread(target=self.start_power_cycle)
        t.start()
    
    def stop_power_cycle(self):
        psc = PowerSupplyController(address="ASRL4::INSTR")  # 修改
        psc.set_output_voltage(0)

    def stop_and_save_data_thread(self):
        t=threading.Thread(target=self.stop_and_save_data)
        t.start()
    
    def stop_and_save_data(self):
        global stop_requested
        stop_requested=True
        self.stop_power_cycle()
        
        
if __name__ == '__main__':
    app = GUI()
    app.window.mainloop() 


