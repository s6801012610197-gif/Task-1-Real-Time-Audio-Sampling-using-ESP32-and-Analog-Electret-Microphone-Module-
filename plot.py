import serial
import struct
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import sys

# ==========================================
# การตั้งค่าพารามิเตอร์
# ==========================================
SERIAL_PORT = 'COM4'      # <<< ตรวจสอบพอร์ตอีกครั้ง
BAUD_RATE = 1000000       
BLOCK_SIZE = 1024     
SAMPLE_RATE = 10000       
PACKET_SIZE = 4 + (BLOCK_SIZE * 2) # Header(2) + N(2) + Data(2048) = 2052 bytes

# ==========================================
# การเชื่อมต่อ Serial
# ==========================================
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
    ser.reset_input_buffer() 
    print(f"เชื่อมต่อกับ {SERIAL_PORT} สำเร็จ")
except Exception as e:
    print(f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")
    sys.exit(1)

# ==========================================
# การเตรียมกราฟ (Matplotlib)
# ==========================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))
fig.canvas.manager.set_window_title('Real-Time Audio DSP')

# 1. กราฟ Time Domain
x_time = np.linspace(0, BLOCK_SIZE / SAMPLE_RATE, BLOCK_SIZE)
line_time, = ax1.plot(x_time, np.zeros(BLOCK_SIZE), lw=1, color='blue')
ax1.set_title("Time-Domain Waveform")
ax1.set_xlabel("Time [s]")
ax1.set_ylabel("ADC Value (0-4095)")
ax1.set_ylim(0, 4096)
ax1.grid(True)

# 2. กราฟ Frequency Domain (FFT)
x_freq = np.fft.rfftfreq(BLOCK_SIZE, d=1.0/SAMPLE_RATE)
line_fft, = ax2.plot(x_freq, np.zeros(len(x_freq)), lw=1, color='red')
ax2.set_title("Frequency-Domain Spectrum (FFT with Hann Window)")
ax2.set_xlabel("Frequency [Hz]")
ax2.set_xlim(0, 3000)
ax2.set_ylabel("Magnitude")
ax2.set_ylim(0, 100) # ปรับลดสเกลเพื่อให้มองเห็นคลื่นความถี่ชัดเจนขึ้น
ax2.grid(True)

plt.tight_layout()

hann_window = np.hanning(BLOCK_SIZE)
byte_buffer = bytearray()

# ==========================================
# ฟังก์ชันอัปเดตกราฟ
# ==========================================
def update_plot(frame):
    global byte_buffer
    
    # 1. ดูดข้อมูลที่เข้ามาใหม่ทั้งหมดไปต่อท้ายบัฟเฟอร์
    if ser.in_waiting > 0:
        byte_buffer.extend(ser.read(ser.in_waiting))
        
    # 2. ป้องกันบัฟเฟอร์ล้น
    if len(byte_buffer) > PACKET_SIZE * 3:
        del byte_buffer[:-PACKET_SIZE*2]
        
    # 3. ค้นหา Header (0xAA 0x55)
    idx = byte_buffer.find(b'\xaa\x55')
    
    if idx != -1:
        # 4. ตรวจสอบว่ามีข้อมูลต่อท้ายครบ 1 บล็อก
        if len(byte_buffer) >= idx + PACKET_SIZE:
            
            n_bytes = byte_buffer[idx+2 : idx+4]
            N = struct.unpack('<H', n_bytes)[0]
            
            if N == BLOCK_SIZE:
                data_bytes = byte_buffer[idx+4 : idx+4+(N*2)]
                
                adc_data = np.frombuffer(data_bytes, dtype=np.uint16).copy()
                del byte_buffer[:idx+PACKET_SIZE]
                
                # --- อัปเดต Time Domain ---
                line_time.set_ydata(adc_data)
                
                # --- อัปเดต Frequency Domain (FFT) ---
                adc_ac = adc_data - np.mean(adc_data) 
                adc_windowed = adc_ac * hann_window 
                fft_result = np.fft.rfft(adc_windowed)
                fft_mag = np.abs(fft_result) / (BLOCK_SIZE / 2)
                
                line_fft.set_ydata(fft_mag)
                
                # เสริม: ปรับสเกลแกน Y อัตโนมัติเผื่อเสียงดังเกินพิกัดที่ตั้งไว้
                ax2.relim()
                ax2.autoscale_view(scalex=False, scaley=True)
                
    return line_time, line_fft

# ==========================================
# สั่งรัน Animation
# ==========================================
ani = animation.FuncAnimation(fig, update_plot, interval=30, blit=True, cache_frame_data=False)

try:
    plt.show()
except KeyboardInterrupt:
    pass
finally:
    ser.close()
    print("ปิดพอร์ต Serial สำเร็จ")