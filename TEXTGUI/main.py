import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext, Toplevel
import serial
import serial.tools.list_ports
import threading
import time

BAUD_RATE = 115200
SERIAL_TIMEOUT = 0.1
TEENSY_VIDPID = "16C0:0483"  #Serial connection port for the teensy 4.0
DARK_GRAY = "#2e2e2e"


class NRF24ChatApp:
    def __init__(self, master):
        self.master = master
        master.title("NRF24 ENCRYPTED Chat GUI")
        master.configure(bg=DARK_GRAY)
        self.serial_conn = None
        self.running = True
        self.popup_open = False
        self.PLACEHOLDER = "Type your message here..."
        # Chat log label
        self.chat_log_label = tk.Label(master, text="Chat Log", font=("Arial", 12, "bold"),bg= DARK_GRAY,fg="white")
        self.chat_log_label.pack(pady=(10, 0))

        # Chat display
        self.chat_display = scrolledtext.ScrolledText(master, width=70, height=30, state='normal',bg="lightgray")
        self.chat_display.pack(padx=10, pady=(0, 10))

        # Message entry
        self.message_entry = tk.Entry(master, width=60, fg='grey')
        self.message_entry.pack(side=tk.LEFT, padx=(10, 5), pady=(0, 10))
        self.message_entry.insert(0, self.PLACEHOLDER)
        self.message_entry.bind("<FocusIn>", self.clear_placeholder)
        self.message_entry.bind("<FocusOut>", self.add_placeholder)
        self.message_entry.bind("<Return>", self.send_message_event)

        # Send button
        self.send_button = tk.Button(master, text="Send", command=self.send_message_thread)
        self.send_button.pack(side=tk.LEFT, padx=(0, 10), pady=(0, 10))

        self.status_label = tk.Label(master, text="Status: Not connected", fg="red")
        self.status_label.pack(pady=5)

        self.auto_connect_serial()

        self.monitor_thread = threading.Thread(target=self.monitor_connection, daemon=True)
        self.monitor_thread.start()

    def get_serial_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]

    def auto_connect_serial(self):
        for port in serial.tools.list_ports.comports():
            if TEENSY_VIDPID in port.hwid.upper():
                try:
                    self.serial_conn = serial.Serial(port.device, BAUD_RATE, timeout=SERIAL_TIMEOUT)
                    self.status_label.config(text=f"Connected to {port.device}", fg="green",bg = DARK_GRAY)
                    self.reader_thread = threading.Thread(target=self.read_serial, daemon=True)
                    self.reader_thread.start()
                    self.chat_display.insert(tk.END, f"***Connected to device. You will see messages appear in this box***")
                    return
                except Exception as e:
                    messagebox.showerror("Auto-Connect Error", f"Failed to connect to {port.device}: {e}")
                    return
        self.status_label.config(text="Auto-connect failed", fg="orange",bg = DARK_GRAY)
        self.show_manual_connect_popup()

    def show_manual_connect_popup(self):
        if self.popup_open:
            return
        self.popup_open = True

        popup = Toplevel(self.master)
        popup.title("Device Not Found")
        popup.geometry("300x150")
        popup.resizable(False, False)

        label = tk.Label(popup, text="Teensy device not found.\nReconnect and select manually:", justify=tk.LEFT)
        label.pack(pady=10)

        ports = self.get_serial_ports()
        combo = ttk.Combobox(popup, values=ports, width=30)
        combo.pack(pady=5)

        def connect_manual():
            selected_port = combo.get()
            if not selected_port:
                messagebox.showwarning("No Port Selected", "Please select a serial port.")
                return
            try:
                self.serial_conn = serial.Serial(selected_port, BAUD_RATE, timeout=SERIAL_TIMEOUT)
                self.status_label.config(text=f"Connected to {selected_port}", fg="green")
                self.reader_thread = threading.Thread(target=self.read_serial, daemon=True)
                self.reader_thread.start()
                self.popup_open = False
                popup.destroy()
            except Exception as e:
                messagebox.showerror("Connection Error", f"Failed to connect: {e}")

        connect_button = tk.Button(popup, text="Connect", command=connect_manual)
        connect_button.pack(pady=10)

        popup.protocol("WM_DELETE_WINDOW", lambda: (popup.destroy(), self.set_popup_closed()))

    def set_popup_closed(self):
        self.popup_open = False

    def send_message_event(self, event):
        self.send_message_thread()

    def send_message_thread(self):
        threading.Thread(target=self.send_message, daemon=True).start()

    def clear_placeholder(self, event):
        if self.message_entry.get() == self.PLACEHOLDER:
            self.message_entry.delete(0, tk.END)
            self.message_entry.config(fg='black')

    def add_placeholder(self, event):
        if not self.message_entry.get():
            self.message_entry.insert(0, self.PLACEHOLDER)
            self.message_entry.config(fg='grey')


    def send_message(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            messagebox.showerror("Connection Error", "Serial connection not available.")
            return
        chunk_size = 31
        msg = self.message_entry.get().strip()
        if not msg:
            messagebox.showwarning("Empty Input", "Please enter some text to send.")
            return

        try:
            for i in range(0, len(msg), chunk_size):
                if i > 0:
                    chunk = msg[i:i + chunk_size]
                    self.serial_conn.write(('`' + chunk + '\n').encode('utf-8'))
                else:
                    chunk = msg[i:i + chunk_size]
                    self.serial_conn.write((chunk + '\n').encode('utf-8'))
                #self.serial_conn.write((chunk + '\n').encode('utf-8'))
                time.sleep(0.05)  # small delay to allow NRF24 to process
            #self.serial_conn.write(('\n').encode('utf-8'))
            #self.chat_display.insert(tk.END, f"\nYOU: {msg}")
            self.chat_display.see(tk.END)
            self.message_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Send Error", f"Failed to send: {e}")
            self.status_label.config(text="Send failed", fg="red")

    def read_serial(self):
        while self.running:
            try:
                if self.serial_conn and self.serial_conn.in_waiting:
                    line = self.serial_conn.readline().decode('utf-8').strip()
                    if line:
                        if line[0] == '`':
                            self.chat_display.insert(tk.END,f"{line[1:len(line)]}")
                            self.chat_display.see(tk.END)
                        else:
                            self.chat_display.insert(tk.END, f"\nFRIEND: {line}")
                            self.chat_display.see(tk.END)
                            self.flash_chat_display()
            except Exception:
                pass
            time.sleep(0.1)

    def add_chat_bubble(self, sender, message, side='left', color="#4a4a4a"):
        bubble_frame = tk.Frame(self.chat_frame, bg=DARK_GRAY)
        bubble_label = tk.Label(
            bubble_frame,
            text=message,
            wraplength=300,
            bg=color,
            fg="white",
            justify=tk.LEFT if side == 'left' else tk.RIGHT,
            padx=10,
            pady=5
        )
        bubble_label.pack(anchor=side, padx=10, pady=2)
        bubble_frame.pack(anchor=side, fill=tk.X)

        # Auto-scroll to bottom
        self.master.after(100, lambda: self.canvas.yview_moveto(1.0))

    def flash_chat_display(self):
        original_color = self.chat_display.cget("background")
        self.chat_display.config(background="#3cc911")  # green
        self.master.after(300, lambda: self.chat_display.config(background=original_color))

    def monitor_connection(self):
        while self.running:
            if self.serial_conn and not self.serial_conn.is_open:
                self.serial_conn = None
                self.status_label.config(text="Status: Disconnected", fg="red")
                self.show_manual_connect_popup()
            time.sleep(2)

    def close(self):
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = NRF24ChatApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.close(), root.destroy()))
    root.mainloop()
