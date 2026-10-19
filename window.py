import serial
import struct
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import sys

# =========================
# SETTINGS
# =========================
SERIAL_PORT = 'COM4'
BAUD_RATE = 1000000

BLOCK_SIZE = 1024
SAMPLE_RATE = 10000

PACKET_SIZE = 4 + (BLOCK_SIZE * 2)

# =========================
# SERIAL CONNECTION
# =========================
try:
    ser = serial.Serial(
        SERIAL_PORT,
        BAUD_RATE,
        timeout=0.01
    )

    ser.reset_input_buffer()

    print(f"เชื่อมต่อกับ {SERIAL_PORT} สำเร็จ")

except Exception as e:
    print(f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")
    sys.exit(1)


# =========================
# FIGURE
# =========================
fig, (ax1, ax2) = plt.subplots(
    2, 1,
    figsize=(10, 8)
)

fig.canvas.manager.set_window_title(
    'Spectral Leakage - Without Window vs Hann Window'
)


# =========================
# TIME DOMAIN
# =========================
x_time = np.arange(BLOCK_SIZE) / SAMPLE_RATE

line_time, = ax1.plot(
    x_time,
    np.zeros(BLOCK_SIZE),
    lw=1
)

ax1.set_title("Time-Domain Waveform")
ax1.set_xlabel("Time [s]")
ax1.set_ylabel("ADC Value")
ax1.set_ylim(0, 4096)
ax1.grid(True)


# =========================
# FREQUENCY AXIS
# =========================
x_freq = np.fft.rfftfreq(
    BLOCK_SIZE,
    d=1.0 / SAMPLE_RATE
)


# =========================
# FFT COMPARISON
# =========================
line_no_window, = ax2.plot(
    x_freq,
    np.zeros(len(x_freq)),
    lw=1.5,
    label="Without Window"
)

line_hann, = ax2.plot(
    x_freq,
    np.zeros(len(x_freq)),
    lw=1.5,
    label="Hann Window"
)

ax2.set_title(
    "FFT Comparison - Spectral Leakage"
)

ax2.set_xlabel("Frequency [Hz]")
ax2.set_ylabel("Magnitude")

# ขยายช่วงเพื่อให้เห็น leakage ชัดขึ้น
ax2.set_xlim(0, 3000)

ax2.grid(True)
ax2.legend()


plt.tight_layout()


# =========================
# HANN WINDOW
# =========================
hann_window = np.hanning(BLOCK_SIZE)


# =========================
# SERIAL BUFFER
# =========================
byte_buffer = bytearray()


# =========================
# UPDATE FUNCTION
# =========================
def update_plot(frame):

    global byte_buffer

    # -------------------------
    # Read serial data
    # -------------------------
    if ser.in_waiting > 0:

        byte_buffer.extend(
            ser.read(ser.in_waiting)
        )


    # Prevent buffer from growing too large
    if len(byte_buffer) > PACKET_SIZE * 3:

        del byte_buffer[:-PACKET_SIZE * 2]


    # -------------------------
    # Find packet header
    # -------------------------
    idx = byte_buffer.find(
        b'\xaa\x55'
    )


    if idx != -1:

        # Check if full packet has arrived
        if len(byte_buffer) >= idx + PACKET_SIZE:

            # -------------------------
            # Read N
            # -------------------------
            n_bytes = byte_buffer[
                idx + 2:idx + 4
            ]

            N = struct.unpack(
                '<H',
                n_bytes
            )[0]


            # -------------------------
            # Check block size
            # -------------------------
            if N == BLOCK_SIZE:

                data_bytes = byte_buffer[
                    idx + 4:
                    idx + 4 + (N * 2)
                ]

                adc_data = np.frombuffer(
                    data_bytes,
                    dtype=np.uint16
                ).copy()


                # Remove processed packet
                del byte_buffer[
                    :idx + PACKET_SIZE
                ]


                # =========================
                # TIME DOMAIN
                # =========================
                line_time.set_ydata(
                    adc_data
                )


                # =========================
                # REMOVE DC OFFSET
                # =========================
                adc_ac = (
                    adc_data.astype(float)
                    - np.mean(adc_data)
                )


                # =========================
                # FFT WITHOUT WINDOW
                # =========================
                fft_no_window = np.fft.rfft(
                    adc_ac
                )

                fft_mag_no_window = (
                    np.abs(fft_no_window)
                    / (BLOCK_SIZE / 2)
                )


                # =========================
                # FFT WITH HANN WINDOW
                # =========================
                adc_hann = (
                    adc_ac
                    * hann_window
                )

                fft_hann = np.fft.rfft(
                    adc_hann
                )

                fft_mag_hann = (
                    np.abs(fft_hann)
                    / (BLOCK_SIZE / 2)
                )


                # =========================
                # UPDATE BOTH FFT
                # =========================
                line_no_window.set_ydata(
                    fft_mag_no_window
                )

                line_hann.set_ydata(
                    fft_mag_hann
                )


                # =========================
                # AUTO SCALE
                # =========================
                ax2.relim()

                ax2.autoscale_view(
                    scalex=False,
                    scaley=True
                )


    return (
        line_time,
        line_no_window,
        line_hann
    )


# =========================
# ANIMATION
# =========================
ani = animation.FuncAnimation(
    fig,
    update_plot,
    interval=30,
    blit=True,
    cache_frame_data=False
)


# =========================
# SHOW
# =========================
try:

    plt.show()

except KeyboardInterrupt:

    pass

finally:

    ser.close()

    print("ปิดพอร์ต Serial สำเร็จ")

