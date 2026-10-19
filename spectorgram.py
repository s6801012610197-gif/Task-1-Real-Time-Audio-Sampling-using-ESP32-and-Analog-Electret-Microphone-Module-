import serial
import struct
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import stft

# ============================================================
# SETTINGS
# ============================================================

SERIAL_PORT = 'COM4'
BAUD_RATE = 1000000

SAMPLE_RATE = 10000      # ESP32 sampling rate: 10 kHz
BLOCK_SIZE = 1024        # ESP32 sends 1024 samples per block

# STFT settings
WINDOW_SIZE = 256
OVERLAP = 128

# ============================================================
# SERIAL
# ============================================================

ser = serial.Serial(
    SERIAL_PORT,
    BAUD_RATE,
    timeout=1
)

print("Connected to", SERIAL_PORT)

# ============================================================
# FIGURE
# ============================================================

plt.ion()

fig, ax = plt.subplots(figsize=(10, 5))

# Store spectrogram data from previous blocks
spectrogram_history = []

MAX_HISTORY = 30


# ============================================================
# READ ONE BLOCK FROM ESP32
# ============================================================

def read_block():

    # Find packet header AA 55
    while True:

        byte = ser.read(1)

        if not byte:
            return None

        if byte == b'\xAA':

            byte2 = ser.read(1)

            if byte2 == b'\x55':
                break

    # Read number of samples
    n_bytes = ser.read(2)

    if len(n_bytes) != 2:
        return None

    N = struct.unpack('<H', n_bytes)[0]

    # Check block size
    if N != BLOCK_SIZE:
        print("Unexpected block size:", N)
        return None

    # Read samples
    data = ser.read(N * 2)

    if len(data) != N * 2:
        return None

    # Convert bytes -> uint16 samples
    samples = np.frombuffer(
        data,
        dtype='<u2'
    )

    return samples


# ============================================================
# REAL-TIME STFT
# ============================================================

try:

    while plt.fignum_exists(fig.number):

        # ----------------------------------------------------
        # Receive one block from ESP32
        # ----------------------------------------------------

        samples = read_block()

        if samples is None:
            continue

        # Convert ADC data to float
        samples = samples.astype(np.float32)

        # Remove DC component
        samples = samples - np.mean(samples)

        # ----------------------------------------------------
        # STFT
        # ----------------------------------------------------

        f, t, Zxx = stft(
            samples,
            fs=SAMPLE_RATE,
            window='hann',
            nperseg=WINDOW_SIZE,
            noverlap=OVERLAP,
            boundary=None
        )

        # Magnitude spectrum
        magnitude = np.abs(Zxx)

        # Convert to dB
        magnitude_dB = 20 * np.log10(
            magnitude + 1e-6
        )

        # ----------------------------------------------------
        # Save spectrogram history
        # ----------------------------------------------------

        spectrogram_history.append(magnitude_dB)

        if len(spectrogram_history) > MAX_HISTORY:
            spectrogram_history.pop(0)

        # Combine previous blocks
        S = np.concatenate(
            spectrogram_history,
            axis=1
        )

        # ----------------------------------------------------
        # Display
        # ----------------------------------------------------

        ax.clear()

        ax.imshow(
            S,
            aspect='auto',
            origin='lower',
            extent=[
                0,
                S.shape[1] * (t[1] - t[0]),
                f[0],
                f[-1]
            ],
            cmap='viridis'
        )

        ax.set_title(
            'Real-Time Audio Spectrogram using STFT'
        )

        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Frequency (Hz)')

        # Nyquist frequency = 10,000 / 2 = 5,000 Hz
        ax.set_ylim(0, SAMPLE_RATE / 2)

        plt.tight_layout()

        # Update figure
        plt.pause(0.001)


except KeyboardInterrupt:

    print("\nStopped by user.")


finally:

    ser.close()
    plt.close()

    print("Serial connection closed.")