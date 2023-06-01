import tkinter as tk
import tkinter.messagebox
import pyvisa
import sys
import atexit
import can
from can.interfaces.pcan.pcan import PcanCanOperationError
import cantools
import time
from   tkinter import ttk,StringVar,filedialog
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
class TextRedirector:
   def __init__(self, widget):
       self.widget = widget

   def write(self, text):
       self.widget.insert(tk.END, text)
       self.widget.see(tk.END)

   def flush(self):
       pass

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
        self.window.title("Power supply control and CAN data monitor")
        self.window.geometry("1650x1000")
        self.window.configure(bg="lightgray")
        
        
        self.dbc_file_path=None
        self.filter_condition_frame=None
        self.unit_labels = []
        self.range_labels = []
        self.create_connection_setting_area()
        self.create_voltage_setting_area()
        self.create_voltage_cycles_area()
        self.create_filter_condition_area()
        self.create_action_buttons()
        self.create_output_area()
        self.dbc=None
       
        global stop_requested
        stop_requested= False
        self.selected_signals_names = []
        print("Please load a DBC FILE") 
    
    #加载dbc文件  后续可拓展加载多个DBC    
    def load_dbc(self):
       
        self.dbc_file_path = filedialog.askopenfilename(filetypes=[("DBC 文件", "*.dbc")])
        if self.dbc_file_path:
            self.dbc = cantools.database.load_file(self.dbc_file_path)
            self.signals = []
        print("DBC File Successfully Loaded")   
    #新建线程运行 load dbc防止卡顿    
    def start_load_dbc_thread(self):
        t=threading.Thread(target=self.load_dbc)
        t.start()  
    
    #电源以及CAN连接的UI配置    
    def create_connection_setting_area(self):
       connection_setting_frame = ttk.LabelFrame(self.window, text="CONNECTION SETTING")
       connection_setting_frame.grid(row=0, column=0, padx=20, pady=20, sticky='nw')

       ttk.Label(connection_setting_frame, text="LOAD DBC FILE:").grid(row=0, column=0, padx=5, pady=5)
       ttk.Button(connection_setting_frame, text="LOAD DBC", command=self.start_load_dbc_thread).grid(row=0, column=0, columnspan=2, padx=5, pady=5)

       ttk.Label(connection_setting_frame, text="Channel:").grid(row=2, column=0, padx=5, pady=5)
       self.channel_var = tk.StringVar(value="PCAN_USBBUS1")
       ttk.Entry(connection_setting_frame, textvariable=self.channel_var, width=30).grid(row=2, column=1, padx=5, pady=5)

       ttk.Label(connection_setting_frame, text="Bitrate:").grid(row=3, column=0, padx=5, pady=5)
       self.bitrate_var = tk.IntVar(value=500000)
       ttk.Entry(connection_setting_frame, textvariable=self.bitrate_var, width=30).grid(row=3, column=1, padx=5, pady=5)
       
       ttk.Label(connection_setting_frame,text="power_address:").grid(row=4,column=0, padx=5, pady=5) 
       self.power_addr = tk.StringVar(value="ASRL4::INSTR")
       ttk.Entry(connection_setting_frame, textvariable=self.power_addr, width=30).grid(row=4, column=1, padx=5, pady=5)
    
    #电压配置的UI    
    def create_voltage_setting_area(self):
        voltage_setting_frame = ttk.LabelFrame(self.window, text="VOLTAGE setting")
        voltage_setting_frame.grid(row=0, column=1, padx=20, pady=20, sticky='nw')

        ttk.Label(voltage_setting_frame, text="SET OUTPUT VOLTAGE(V):").grid(row=0, column=0, padx=5, pady=5)
        self.voltage_var = tk.DoubleVar(value=14)
        ttk.Entry(voltage_setting_frame, textvariable=self.voltage_var, width=10).grid(row=0, column=1, padx=5, pady=5)
    #循环次数的UI
    def create_voltage_cycles_area(self):
        voltage_cycles_frame = ttk.LabelFrame(self.window, text="POWER SUPPLY CYCLE SETITNG")
        voltage_cycles_frame.grid(row=0, column=2, padx=20, pady=20, sticky='nw')

        ttk.Label(voltage_cycles_frame, text="TIME Off (s):").grid(row=0, column=0, padx=5, pady=5)
        self.duration_1_var = tk.IntVar(value=2)
        ttk.Entry(voltage_cycles_frame, textvariable=self.duration_1_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(voltage_cycles_frame, text="TIME On (s):").grid(row=1, column=0, padx=5, pady=5)
        self.duration_2_var = tk.IntVar(value=10)
        ttk.Entry(voltage_cycles_frame, textvariable=self.duration_2_var, width=10).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(voltage_cycles_frame, text="Repeat cycle:").grid(row=2, column=0, padx=5, pady=5)
        self.repeat_cycles_var = tk.IntVar(value=10)
        ttk.Entry(voltage_cycles_frame, textvariable=self.repeat_cycles_var, width=10).grid(row=2, column=1, padx=5, pady=5)
    #过滤条件（触发条件）的UI
    def create_filter_condition_area(self):
        self.filter_condition_frame = ttk.LabelFrame(self.window, text="Stop conditions config")
        self.filter_condition_frame.grid(row=1, column=0, padx=20, pady=20, columnspan=3, sticky='nw')
        
        self.signal_option_menus=[]
        
        self.can_id_vars = []
        self.stop_condition_number_vars = []
        self.stop_condition_operator_vars = []
        ttk.Label(self.filter_condition_frame, text="CAN ID").grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(self.filter_condition_frame, text="stop condition symbol").grid(row=1, column=0, padx=5, pady=5)
        ttk.Label(self.filter_condition_frame, text="stop condition relation").grid(row=2, column=0, padx=5, pady=5)
        ttk.Label(self.filter_condition_frame, text="signal selection").grid(row=3, column=0, padx=5, pady=5)
        ttk.Label(self.filter_condition_frame, text="stop condition unit/range").grid(row=4, column=0, padx=5, pady=5)
        ttk.Label(self.filter_condition_frame, text="stop condition value").grid(row=6, column=0, padx=5, pady=5)
        for i in range(10):
            can_id_var = tk.StringVar()
            self.can_id_vars.append(can_id_var)
            
           
            stop_condition_number_var = tk.StringVar()
            self.stop_condition_number_vars.append(stop_condition_number_var)
            stop_condition_operator_var = tk.StringVar()
            self.stop_condition_operator_vars.append(stop_condition_operator_var)

            ttk.Entry(self.filter_condition_frame, textvariable=can_id_var, width=8).grid(row=0, column=i + 1, padx=15, pady=15)

            operator = ttk.OptionMenu(self.filter_condition_frame, stop_condition_operator_var, '=', '=', '<', '>')
            operator.grid(row=1, column=i + 1, padx=15, pady=15)

            ttk.Entry(self.filter_condition_frame, textvariable=stop_condition_number_var, width=8).grid(row=6, column=i + 1, padx=15, pady=15)
          
            can_id_var.trace("w",lambda *args,index=i:self.update_signal_options(index))
            
            unit_label = ttk.Label(self.filter_condition_frame, text="Unit")
            unit_label.grid(row=4, column=i + 1, padx=5, pady=5)
            range_label = ttk.Label(self.filter_condition_frame, text="Range")
            range_label.grid(row=5, column=i + 1, padx=5, pady=5)
            self.unit_labels.append(unit_label)
            self.range_labels.append(range_label)
            
        self.stop_relation_var = tk.StringVar()
        
        relation = ttk.OptionMenu(self.filter_condition_frame, self.stop_relation_var, 'And','And', 'Or')
        relation.grid(row=2, column=1, padx=5, pady=5)

    #根据 CAN ID 以及DBC更新信号下拉列表
    def update_signal_options(self, index, *args):
        if self.dbc is None:
            print("Please load DBC File")
            return
        
        self.signal_combo = ttk.Combobox(self.filter_condition_frame, width=15)  # 设置下拉列表宽度
        self.signal_combo.grid(row=3 , column=index+1, padx=10, pady=10)

        # 创建横向滚动条
        scrollbar = tk.Scrollbar(self.filter_condition_frame, orient=tk.HORIZONTAL,width=15)
        scrollbar.grid(row=7, column=index+1, padx=5, pady=(0,5), sticky="ew")
       
        self.signal_combo.config(xscrollcommand=scrollbar.set)
        scrollbar.config(command=self.signal_combo.xview)

        self.signal_combo.config(xscrollcommand = scrollbar.set) # combobox绑定滚动条设置
        scrollbar.config(command =self.signal_combo.xview) # 滚动条绑定combobox滚动设置

        can_ids = [can_id_var.get() for can_id_var in self.can_id_vars if can_id_var.get()]
        for can_id in can_ids:
            message = self.dbc.get_message_by_frame_id(int(can_id, 16))
            print("Detected valid CAN_ID",can_id)
            if message:
                self.signals = message.signals
                signal_names = [signal.name for signal in self.signals]
                self.signal_combo["values"]= sorted(signal_names)
                self.signal_combo.bind("<<ComboboxSelected>>", lambda event: self.on_signal_selected(index))
            else:
                print("Please input a valid CAN_ID")
                self.signals = []
                self.signal_combo.set("")
                self.signal_combo["values"] = []
    
    #得到所选信号的范围以及单位并显示
    def on_signal_selected(self, index):
        selected_signal_name = self.signal_combo.get()
        selected_signal = next((signal for signal in self.signals if signal.name == selected_signal_name), None)
        self.selected_signals_names.append(selected_signal_name)
        if selected_signal:
            self.unit_labels[index]["text"] = f"Unit: {selected_signal.unit}"
            print("Please set stop conditions accroding to unit and range shown above")
            self.range_labels[index]["text"] = f"Range: {selected_signal.minimum}-{selected_signal.maximum}"
        else:
            self.unit_labels[index]["text"] = ""
            self.range_labels[index]["text"] = ""

    #开始与停止 UI
    def create_action_buttons(self):
        action_frame = ttk.Frame(self.window)
        action_frame.grid(row=2, column=1, padx=20, pady=20, sticky='nw')

        ttk.Button(action_frame, text="START", command=self.start_power_cycle_thread).grid(row=0, column=0, padx=10, pady=10)
        ttk.Button(action_frame, text="STOP", command=self.stop_and_save_data_thread).grid(row=0, column=1, padx=10, pady=10)
    
    #power cycle
    def start_power_cycle(self):
        global stop_requested   
        # 获取用户输入的值
        stop_requested = False
        channel = self.channel_var.get()
        bitrate = self.bitrate_var.get()
       
        psc = PowerSupplyController ( address=self.power_addr.get())
        self.stop_power_cycle()
        duration_1 = self.duration_1_var.get()
        duration_2 = self.duration_2_var.get()
        repeat_cycles = self.repeat_cycles_var.get()

        filtered_addresses = [int(can_id.get(), 16) for can_id in self.can_id_vars if can_id.get()]
        can_reader = CANReader(channel=channel, bitrate=bitrate, filtered_addresses=filtered_addresses)
        dbc_processor = DBCProcessor(dbc_file=self.dbc_file_path)

        # 在此添加时间戳到文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_data_file = f"raw_data_{timestamp}.txt"
        decoded_data_file = f"decoded_data_{timestamp}.txt"
        
        # 如果文件不存在，则创建文件
        if not os.path.exists(raw_data_file):
            print(f'Creating file at {os.path.abspath(raw_data_file)}')   #创建文件时打印文件的绝对路径
            with open(raw_data_file, "w") as f:
                pass
      
        if not os.path.exists(decoded_data_file):
            print(f'Creating file at {os.path.abspath(decoded_data_file)}')
            with open(decoded_data_file, "w") as f:
                pass
        

        # 新增：记录原始信号和解码后的信号
        with open(raw_data_file, "w") as raw_data_file, open(decoded_data_file, "w") as decoded_data_file:

            stop_conditions = []
           
            for can_id_var, operator_var, value_var,signal_name in zip(self.can_id_vars, self.stop_condition_operator_vars,
                                            self.stop_condition_number_vars,self.selected_signals_names):
                if can_id_var.get() :
                    can_id = int(can_id_var.get(), 16)
                    operator= operator_var.get()
                    value= float(value_var.get())  #用户的输入转化为了he'x十六进制float  用户应该输入10进制
                    signal_name=signal_name
                    print("Set stop condition as: ",can_id,operator,signal_name,value_var.get())
                  #  signal_position =dbc_processor.get_signal_position_by_name(can_id, signal_name)           
                    stop_conditions.append((can_id, signal_name, operator, value))
            #power cycle 包含触发条件判断以及数据记录
            for i in range(repeat_cycles):
                print("重复轮次：",i)
                psc.set_output_voltage(0)
                self.window.after(1000 * duration_1, psc.set_output_voltage(self.voltage_var.get()))

                start_time = time.time()
                while (time.time() - start_time) < duration_2:
                    try:
                        can_data = can_reader.read_messages()
                    except PcanCanOperationError as e:
                        print(e)
                        print("can reader 异常")
                        can_reader.bus.shutdown()
                        return
                    parsed_data = dbc_processor.parse_messages_using_dbc(can_data)

                    # 新增：记录原始信号和解码后的信号到文件
                    raw_data_file.write(f"{can_data}\n")
                    decoded_data_file.write(f"{parsed_data}\n")
                    
                    if stop_requested==True:
                        tkinter.messagebox.showinfo("终止" ,"手动停止")
                        can_reader.bus.shutdown()
                        return
                    satisfied_conditions = 0
                    
                    for can_id, signal_name, operator, value in stop_conditions:
                        if can_id in parsed_data and parsed_data[can_id].get(signal_name) is not None:
                            print("CAN ID: ",can_id)
                            print("SIGNAL_NAME",signal_name)
                    
                            signal_value = parsed_data[can_id].get(signal_name)#  11111
                            print("signal_value: ",signal_value)
                            if signal_value is not None and signal_value!="SNA":  #信号值为数字时才可以正常进行 若有除了SNA的别的情况请自行添加
                                match = False
                                if operator == "=":
                                    match = signal_value == value
                                elif operator == "<":
                                    match = signal_value < value
                                elif operator == ">":
                                    match = signal_value > value

                                if match:
                                    satisfied_conditions += 1
                                    if self.stop_relation_var.get() == "Or":
                                        #psc.set_output_voltage(0)  #更改逻辑 条件触发时维持供电
                                        tkinter.messagebox.showinfo("终止", f"Stop condition has been triggered  CAN ID: {can_id}, Signal Name: {signal_name}")
                                        return

                    if self.stop_relation_var.get() == "And" and satisfied_conditions == len(stop_conditions): #AND时判断是否所有条件都触发
                        #psc.set_output_voltage(0) #更改逻辑 条件触发时维持供电
                        tkinter.messagebox.showinfo("终止", f"ALL Stop conditions have been triggered.")
                        can_reader.bus.shutdown()
                        return

                    time.sleep(0.001)#防止CPU过高占用或卡死
               
                psc.set_output_voltage(0)
                time.sleep(duration_1)
            tkinter.messagebox.showinfo("终止", f"循环测试已结束。")
            can_reader.bus.shutdown()
    def start_power_cycle_thread(self):
        t=threading.Thread(target=self.start_power_cycle)
        t.start()
    
    def stop_power_cycle(self):
        psc = PowerSupplyController(address=self.power_addr.get())  # 修改
        psc.set_output_voltage(0)

    def stop_and_save_data_thread(self):
        t=threading.Thread(target=self.stop_and_save_data)
        t.start()
    
    def stop_and_save_data(self):
        global stop_requested
        stop_requested=True
        self.stop_power_cycle()
        
    def create_output_area(self):
       # 在现有布局之后添加输出窗口
       self.output_text = tk.Text(self.window, width=80, height=20, wrap=tk.WORD)
       self.output_text.grid(row=3, column=0, padx=20, pady=10, columnspan=3, sticky='nw')

       # 添加一个滚动条
       scrollbar = tk.Scrollbar(self.window, command=self.output_text.yview)
       scrollbar.grid(row=3, column=1, padx=200, pady=10, sticky='nsw')
       self.output_text['yscrollcommand'] = scrollbar.set

       # 重定向标准输出到Text小部件
       sys.stdout = TextRedirector(self.output_text)
       atexit.register(self.restore_stdout)  # 在程序结束时注册回调函数

       # 重定向标准错误输出到Text小部件
       self.original_stderr = sys.stderr  # 保存原始标准错误输出
       sys.stderr = TextRedirector(self.output_text)

       atexit.register(self.restore_stdout)  # 在程序结束时注册回调函数

   # 在程序结束时恢复原始标准输出和标准错误输出
    def restore_stdout(self):
       sys.stdout = self.original_stdout
       sys.stderr = self.original_stderr
        
        
if __name__ == '__main__':
    app = GUI()
    app.window.mainloop() 


