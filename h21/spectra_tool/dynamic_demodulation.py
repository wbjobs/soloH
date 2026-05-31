import numpy as np
import os
import time
import threading
import queue
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable, Tuple
from collections import deque

try:
    import serial
    from serial.tools import list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from .data_reader import SpectrumData
from .peak_detection import detect_peaks
from .peak_decomposition import deconvolve_peaks
from .physical_calculations import (
    calculate_wavelength_shift,
    calculate_temperature,
    calculate_strain,
    calculate_uncertainty,
)
from .multichannel_fbg import (
    FBGChannelConfig,
    MultiChannelResult,
    FBGChannelResult,
    demodulate_multichannel,
)


@dataclass
class SerialConfig:
    """Serial port configuration."""
    port: str
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    timeout: float = 1.0
    data_format: str = "ascii"
    delimiter: str = "\n"
    wavelength_column: int = 0
    intensity_column: int = 1


@dataclass
class DemodulationConfig:
    """Configuration for real-time demodulation."""
    method: str = "auto"
    n_peaks: int = 1
    decomposition: bool = False
    line_profile: str = "gaussian"
    reference_wavelength: Optional[float] = None
    calibration_coeffs: Optional[Dict[str, float]] = None
    channel_configs: Optional[List[FBGChannelConfig]] = None
    smoothing_window: int = 5
    remove_outliers: bool = True


@dataclass
class RealTimeResult:
    """Result from a single real-time demodulation cycle."""
    timestamp: float
    spectrum: Optional[SpectrumData]
    peak_wavelengths: List[float]
    wavelength_shifts: List[float]
    temperatures: List[Optional[float]]
    strains: List[Optional[float]]
    uncertainties: List[Optional[float]]
    intensities: List[float]
    multichannel_result: Optional[MultiChannelResult] = None
    raw_data: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DataBuffer:
    """Thread-safe buffer for spectrum data."""
    max_size: int = 100
    buffer: deque = field(default_factory=lambda: deque(maxlen=100))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, data: RealTimeResult) -> None:
        with self._lock:
            self.buffer.append(data)

    def get_all(self) -> List[RealTimeResult]:
        with self._lock:
            return list(self.buffer)

    def get_latest(self, n: int = 1) -> List[RealTimeResult]:
        with self._lock:
            return list(self.buffer)[-n:]

    def clear(self) -> None:
        with self._lock:
            self.buffer.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self.buffer)


class SerialSpectrumReader:
    """
    Read spectrum data from serial port in real-time.

    Parameters:
    -----------
    config : SerialConfig
        Serial port configuration
    """

    def __init__(self, config: SerialConfig):
        if not SERIAL_AVAILABLE:
            raise ImportError("pyserial is not installed. Install with: pip install pyserial")

        self.config = config
        self.serial_port: Optional[serial.Serial] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._data_queue: "queue.Queue[Optional[str]]" = queue.Queue(maxsize=1000)
        self._buffer = ""
        self._lock = threading.Lock()

    @staticmethod
    def list_available_ports() -> List[str]:
        """List available serial ports."""
        if not SERIAL_AVAILABLE:
            return []
        return [port.device for port in list_ports.comports()]

    def connect(self) -> None:
        """Connect to the serial port."""
        with self._lock:
            if self.serial_port is not None and self.serial_port.is_open:
                return

            self.serial_port = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                bytesize=self.config.bytesize,
                parity=self.config.parity,
                stopbits=self.config.stopbits,
                timeout=self.config.timeout,
            )
            self._buffer = ""
            print(f"Connected to {self.config.port} at {self.config.baudrate} baud")

    def disconnect(self) -> None:
        """Disconnect from the serial port."""
        with self._lock:
            self._running = False
            if self.serial_port is not None and self.serial_port.is_open:
                self.serial_port.close()
                self.serial_port = None
                print("Disconnected from serial port")

    def start_reading(self, callback: Optional[Callable[[str], None]] = None) -> None:
        """Start reading data in a background thread."""
        if self._running:
            return

        self.connect()
        self._running = True

        def _read_loop():
            try:
                while self._running and self.serial_port and self.serial_port.is_open:
                    try:
                        raw_data = self.serial_port.readline()
                        if raw_data:
                            decoded = raw_data.decode(self.config.data_format, errors="ignore")
                            self._buffer += decoded

                            while self.config.delimiter in self._buffer:
                                line, self._buffer = self._buffer.split(self.config.delimiter, 1)
                                line = line.strip()
                                if line:
                                    if callback:
                                        callback(line)
                                    if not self._data_queue.full():
                                        self._data_queue.put(line)
                    except Exception as e:
                        print(f"Error reading serial data: {e}")
                        time.sleep(0.01)
            except Exception as e:
                print(f"Serial reading thread error: {e}")
            finally:
                self._data_queue.put(None)

        self._thread = threading.Thread(target=_read_loop, daemon=True)
        self._thread.start()

    def stop_reading(self) -> None:
        """Stop reading data."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.disconnect()

    def read_line(self, timeout: float = 1.0) -> Optional[str]:
        """Read a single line of data with timeout."""
        try:
            return self._data_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def is_connected(self) -> bool:
        """Check if serial port is connected."""
        return self.serial_port is not None and self.serial_port.is_open

    def is_running(self) -> bool:
        """Check if reading thread is running."""
        return self._running


class SpectrumDataParser:
    """
    Parse raw serial data into SpectrumData objects.

    Supports multiple data formats:
    - Two-column ASCII: "wavelength1,intensity1\nwavelength2,intensity2\n..."
    - Single spectrum per line with multiple wavelength-intensity pairs
    - Binary formats (TODO)
    """

    def __init__(
        self,
        delimiter: str = ",",
        wavelength_column: int = 0,
        intensity_column: int = 1,
        expected_points: Optional[int] = None,
    ):
        self.delimiter = delimiter
        self.wavelength_column = wavelength_column
        self.intensity_column = intensity_column
        self.expected_points = expected_points
        self._line_buffer: List[str] = []

    def parse_line(self, line: str) -> Optional[List[Tuple[float, float]]]:
        """
        Parse a single line of data.

        Returns list of (wavelength, intensity) pairs, or None if incomplete.
        """
        line = line.strip()
        if not line:
            return None

        try:
            parts = line.split(self.delimiter)
            if len(parts) >= 2:
                wl = float(parts[self.wavelength_column].strip())
                inten = float(parts[self.intensity_column].strip())
                return [(wl, inten)]
        except (ValueError, IndexError):
            pass

        try:
            pairs = []
            for i in range(0, len(parts) - 1, 2):
                wl = float(parts[i].strip())
                inten = float(parts[i + 1].strip())
                pairs.append((wl, inten))
            if pairs:
                return pairs
        except (ValueError, IndexError):
            pass

        return None

    def parse_lines(self, lines: List[str]) -> Optional[SpectrumData]:
        """Parse multiple lines into a SpectrumData object."""
        all_pairs = []
        for line in lines:
            pairs = self.parse_line(line)
            if pairs:
                all_pairs.extend(pairs)

        if not all_pairs:
            return None

        if self.expected_points and len(all_pairs) < self.expected_points:
            return None

        all_pairs.sort(key=lambda x: x[0])
        wavelengths = np.array([p[0] for p in all_pairs])
        intensities = np.array([p[1] for p in all_pairs])

        return SpectrumData(
            filename=f"serial_{int(time.time() * 1000)}",
            wavelength=wavelengths,
            intensity=intensities,
            metadata={"source": "serial", "timestamp": time.time()},
        )


class RealTimeDemodulator:
    """
    Real-time spectrum demodulation system.

    Integrates serial data reading, parsing, peak detection, and
    physical quantity calculation.

    Parameters:
    -----------
    serial_config : SerialConfig
        Serial port configuration
    demod_config : DemodulationConfig
        Demodulation configuration
    data_buffer_size : int
        Maximum number of results to keep in buffer
    """

    def __init__(
        self,
        serial_config: SerialConfig,
        demod_config: DemodulationConfig,
        data_buffer_size: int = 1000,
    ):
        self.serial_config = serial_config
        self.demod_config = demod_config
        self.reader = SerialSpectrumReader(serial_config)
        self.parser = SpectrumDataParser(
            delimiter=serial_config.delimiter if serial_config.delimiter != "\n" else ",",
            wavelength_column=serial_config.wavelength_column,
            intensity_column=serial_config.intensity_column,
        )
        self.data_buffer = DataBuffer(max_size=data_buffer_size)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[RealTimeResult], None]] = []
        self._line_buffer: List[str] = []
        self._lock = threading.Lock()
        self._smoothing_buffer: Dict[str, deque] = {}

    def add_callback(self, callback: Callable[[RealTimeResult], None]) -> None:
        """Add a callback function to be called on each new result."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[RealTimeResult], None]) -> None:
        """Remove a callback function."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _smooth_value(self, key: str, value: float, window: Optional[int] = None) -> float:
        """Apply moving average smoothing to a value."""
        if window is None:
            window = self.demod_config.smoothing_window

        if key not in self._smoothing_buffer:
            self._smoothing_buffer[key] = deque(maxlen=window)

        self._smoothing_buffer[key].append(value)
        return float(np.mean(self._smoothing_buffer[key]))

    def _remove_outliers(self, values: List[float], threshold: float = 3.0) -> List[float]:
        """Remove outliers using Z-score method."""
        if len(values) < 4:
            return values

        arr = np.array(values)
        median = np.median(arr)
        mad = np.median(np.abs(arr - median))
        if mad == 0:
            return values

        z_scores = 0.6745 * (arr - median) / mad
        return list(arr[np.abs(z_scores) < threshold])

    def _demodulate_spectrum(self, spectrum: SpectrumData) -> RealTimeResult:
        """Demodulate a single spectrum."""
        result = RealTimeResult(
            timestamp=time.time(),
            spectrum=spectrum,
            peak_wavelengths=[],
            wavelength_shifts=[],
            temperatures=[],
            strains=[],
            uncertainties=[],
            intensities=[],
        )

        try:
            if self.demod_config.channel_configs:
                peak_detection_kwargs = {
                    "remove_baseline": True,
                    "min_snr": 1.5,
                    "min_peak_height_ratio": 0.02,
                    "prominence_ratio": 0.02,
                }
                mc_result = demodulate_multichannel(
                    spectrum,
                    self.demod_config.channel_configs,
                    method=self.demod_config.method,
                    decomposition=self.demod_config.decomposition,
                    line_profile=self.demod_config.line_profile,
                    peak_detection_kwargs=peak_detection_kwargs,
                )
                result.multichannel_result = mc_result

                for channel in mc_result.channels:
                    for peak in channel.peak_results:
                        result.peak_wavelengths.append(peak.wavelength)
                        result.intensities.append(peak.intensity)

                    for shift in channel.wavelength_shifts:
                        result.wavelength_shifts.append(shift)
                    for temp in channel.temperatures:
                        result.temperatures.append(temp)
                    for strain in channel.strains:
                        result.strains.append(strain)
                    for unc in channel.uncertainties:
                        result.uncertainties.append(unc)
            else:
                peak_detection_kwargs = {
                    "remove_baseline": True,
                    "min_snr": 1.5,
                    "min_peak_height_ratio": 0.02,
                    "prominence_ratio": 0.02,
                }
                peak_results = detect_peaks(
                    spectrum,
                    method=self.demod_config.method,
                    **peak_detection_kwargs,
                )

                if self.demod_config.decomposition and len(peak_results) > 0:
                    try:
                        deconvolve_peaks(
                            spectrum.wavelength,
                            spectrum.intensity,
                            n_peaks=self.demod_config.n_peaks,
                            line_profile=self.demod_config.line_profile,
                        )
                    except Exception:
                        pass

                ref_wl = self.demod_config.reference_wavelength
                calib = self.demod_config.calibration_coeffs

                for peak in peak_results:
                    result.peak_wavelengths.append(peak.wavelength)
                    result.intensities.append(peak.intensity)

                    if ref_wl is not None:
                        shift = calculate_wavelength_shift(peak.wavelength, ref_wl)
                        result.wavelength_shifts.append(shift)

                        if calib:
                            try:
                                temp = calculate_temperature(
                                    peak.wavelength, ref_wl, calib.get("k_T", 0.01)
                                )
                                result.temperatures.append(temp)
                            except Exception:
                                result.temperatures.append(None)

                            try:
                                if "k_eps" in calib:
                                    strain = calculate_strain(
                                        peak.wavelength,
                                        ref_wl,
                                        calib.get("k_eps", 0.0012),
                                        calib.get("k_T"),
                                        temperature=result.temperatures[-1] if result.temperatures else 25.0,
                                        reference_temperature=25.0,
                                    )
                                    result.strains.append(strain)
                                else:
                                    result.strains.append(None)
                            except Exception:
                                result.strains.append(None)

                            try:
                                unc = calculate_uncertainty(peak, calib, ref_wl)
                                result.uncertainties.append(unc)
                            except Exception:
                                result.uncertainties.append(None)
                        else:
                            result.temperatures.append(None)
                            result.strains.append(None)
                            result.uncertainties.append(None)
                    else:
                        result.wavelength_shifts.append(0.0)
                        result.temperatures.append(None)
                        result.strains.append(None)
                        result.uncertainties.append(None)

            if self.demod_config.smoothing_window > 1:
                for i, wl in enumerate(result.peak_wavelengths):
                    key = f"peak_{i}_wavelength"
                    result.peak_wavelengths[i] = self._smooth_value(key, wl)

                for i, shift in enumerate(result.wavelength_shifts):
                    key = f"peak_{i}_shift"
                    result.wavelength_shifts[i] = self._smooth_value(key, shift)

        except Exception as e:
            result.error = str(e)

        return result

    def _process_line(self, line: str) -> None:
        """Process a single line of data."""
        self._line_buffer.append(line)

        max_lines = self.parser.expected_points or 1000
        if len(self._line_buffer) > max_lines * 2:
            self._line_buffer = self._line_buffer[-max_lines:]

        spectrum = self.parser.parse_lines(self._line_buffer)

        if spectrum is not None:
            self._line_buffer = []
            result = self._demodulate_spectrum(spectrum)
            self.data_buffer.add(result)

            for callback in self._callbacks:
                try:
                    callback(result)
                except Exception as e:
                    print(f"Callback error: {e}")

    def start(self) -> None:
        """Start real-time demodulation."""
        if self._running:
            return

        self._running = True
        self._line_buffer = []

        self.reader.start_reading(callback=self._process_line)

        print("Real-time demodulation started")
        print(f"Serial port: {self.serial_config.port}")
        print(f"Demodulation method: {self.demod_config.method}")
        if self.demod_config.channel_configs:
            print(f"Channels: {len(self.demod_config.channel_configs)}")

    def stop(self) -> None:
        """Stop real-time demodulation."""
        self._running = False
        self.reader.stop_reading()
        print("Real-time demodulation stopped")

    def is_running(self) -> bool:
        """Check if demodulation is running."""
        return self._running and self.reader.is_running()

    def get_latest_result(self) -> Optional[RealTimeResult]:
        """Get the most recent demodulation result."""
        results = self.data_buffer.get_latest(1)
        return results[0] if results else None

    def save_results(self, output_path: str) -> str:
        """
        Save buffered results to CSV file.

        Parameters:
        -----------
        output_path : str
            Output file path

        Returns:
        --------
        str
            Path to saved file
        """
        import pandas as pd

        results = self.data_buffer.get_all()
        if not results:
            raise ValueError("No results to save")

        rows = []
        for result in results:
            base_row = {
                "timestamp": result.timestamp,
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(result.timestamp)),
            }

            if result.multichannel_result:
                for channel in result.multichannel_result.channels:
                    for i, peak in enumerate(channel.peak_results):
                        row = base_row.copy()
                        row["channel_id"] = channel.channel_id
                        row["channel_name"] = channel.name
                        row["peak_index"] = i + 1
                        row["peak_wavelength"] = peak.wavelength
                        row["intensity"] = peak.intensity
                        row["fwhm"] = peak.fwhm
                        row["wavelength_shift"] = channel.wavelength_shifts[i] if i < len(channel.wavelength_shifts) else None
                        row["temperature"] = channel.temperatures[i] if i < len(channel.temperatures) else None
                        row["strain"] = channel.strains[i] if i < len(channel.strains) else None
                        row["uncertainty"] = channel.uncertainties[i] if i < len(channel.uncertainties) else None
                        rows.append(row)
            else:
                for i, (wl, inten, shift, temp, strain, unc) in enumerate(zip(
                    result.peak_wavelengths,
                    result.intensities,
                    result.wavelength_shifts,
                    result.temperatures,
                    result.strains,
                    result.uncertainties,
                )):
                    row = base_row.copy()
                    row["peak_index"] = i + 1
                    row["peak_wavelength"] = wl
                    row["intensity"] = inten
                    row["wavelength_shift"] = shift
                    row["temperature"] = temp
                    row["strain"] = strain
                    row["uncertainty"] = unc
                    rows.append(row)

        df = pd.DataFrame(rows)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path


class SimulatedSpectrumSource:
    """
    Simulated spectrum data source for testing without hardware.

    Generates realistic spectrum data with configurable peak parameters
    and noise characteristics.
    """

    def __init__(
        self,
        wavelength_range: Tuple[float, float] = (1540, 1560),
        n_points: int = 500,
        peak_centers: List[float] = None,
        peak_amplitudes: List[float] = None,
        peak_fwhms: List[float] = None,
        noise_level: float = 0.02,
        update_interval: float = 0.5,
        drift_speed: float = 0.001,
    ):
        self.wavelength_range = wavelength_range
        self.n_points = n_points
        self.wavelengths = np.linspace(wavelength_range[0], wavelength_range[1], n_points)
        self.peak_centers = np.array(peak_centers or [1545.0, 1550.0, 1555.0])
        self.peak_amplitudes = np.array(peak_amplitudes or [1.5, 2.0, 1.2])
        self.peak_fwhms = np.array(peak_fwhms or [0.3, 0.25, 0.35])
        self.noise_level = noise_level
        self.update_interval = update_interval
        self.drift_speed = drift_speed
        self._start_time = time.time()

    def generate_spectrum(self) -> SpectrumData:
        """Generate a simulated spectrum."""
        elapsed = time.time() - self._start_time
        drift = np.sin(elapsed * self.drift_speed * 10) * self.drift_speed * 5

        intensities = np.zeros_like(self.wavelengths)
        for i, (center, amp, fwhm) in enumerate(zip(self.peak_centers, self.peak_amplitudes, self.peak_fwhms)):
            sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
            drifted_center = center + drift * (i + 1) / len(self.peak_centers)
            intensities += amp * np.exp(-((self.wavelengths - drifted_center) ** 2) / (2 * sigma ** 2))

        intensities += np.random.normal(0, self.noise_level, self.n_points)
        intensities += 0.1

        return SpectrumData(
            filename=f"simulated_{int(time.time() * 1000)}",
            wavelength=self.wavelengths.copy(),
            intensity=intensities,
            metadata={
                "source": "simulated",
                "timestamp": time.time(),
                "elapsed": elapsed,
            },
        )

    def generate_serial_lines(self) -> List[str]:
        """Generate serial port style data lines."""
        spectrum = self.generate_spectrum()
        lines = []
        for wl, inten in zip(spectrum.wavelength, spectrum.intensity):
            lines.append(f"{wl:.6f},{inten:.6f}")
        return lines


def run_realtime_demodulation(
    serial_port: str,
    baudrate: int = 115200,
    output_file: Optional[str] = None,
    channel_config: Optional[str] = None,
    duration: Optional[float] = None,
    **kwargs,
) -> DataBuffer:
    """
    Convenience function to run real-time demodulation.

    Parameters:
    -----------
    serial_port : str
        Serial port name or "simulate" for simulated data
    baudrate : int
        Baud rate
    output_file : str, optional
        Output CSV file path
    channel_config : str, optional
        Path to channel configuration JSON file
    duration : float, optional
        Duration in seconds (None for indefinite)
    **kwargs
        Additional arguments for demodulation configuration

    Returns:
    --------
    DataBuffer
        Buffer containing demodulation results
    """
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table

    console = Console()

    demod_kwargs = {
        "method": kwargs.get("method", "auto"),
        "n_peaks": kwargs.get("n_peaks", 1),
        "decomposition": kwargs.get("decomposition", False),
        "line_profile": kwargs.get("line_profile", "gaussian"),
        "reference_wavelength": kwargs.get("reference_wavelength"),
        "calibration_coeffs": kwargs.get("calibration_coeffs"),
    }

    if channel_config:
        from .multichannel_fbg import load_channel_config
        demod_kwargs["channel_configs"] = load_channel_config(channel_config)

    demod_config = DemodulationConfig(**demod_kwargs)

    if serial_port == "simulate":
        source = SimulatedSpectrumSource()
        buffer = DataBuffer(max_size=1000)
        start_time = time.time()

        def generate_result_display(result: RealTimeResult) -> Table:
            table = Table(title="Real-Time Demodulation Results")
            table.add_column("Time", style="cyan")
            table.add_column("Peak λ (nm)", style="green")
            table.add_column("Shift (nm)", style="yellow")
            table.add_column("Temp (°C)", style="red")
            table.add_column("Strain (με)", style="magenta")

            if result.multichannel_result:
                for channel in result.multichannel_result.channels:
                    for i, wl in enumerate(channel.peak_wavelengths):
                        shift = channel.wavelength_shifts[i] if i < len(channel.wavelength_shifts) else 0
                        temp = channel.temperatures[i] if i < len(channel.temperatures) else None
                        strain = channel.strains[i] if i < len(channel.strains) else None

                        table.add_row(
                            f"{channel.name}",
                            f"{wl:.4f}",
                            f"{shift:.4f}",
                            f"{temp:.2f}" if temp is not None else "-",
                            f"{strain:.2f}" if strain is not None else "-",
                        )
            else:
                for i, wl in enumerate(result.peak_wavelengths):
                    shift = result.wavelength_shifts[i] if i < len(result.wavelength_shifts) else 0
                    temp = result.temperatures[i] if i < len(result.temperatures) else None
                    strain = result.strains[i] if i < len(result.strains) else None

                    table.add_row(
                        f"{time.strftime('%H:%M:%S', time.localtime(result.timestamp))}",
                        f"{wl:.4f}",
                        f"{shift:.4f}",
                        f"{temp:.2f}" if temp is not None else "-",
                        f"{strain:.2f}" if strain is not None else "-",
                    )

            return table

        console.print("[cyan]Starting simulated real-time demodulation...[/cyan]")
        console.print("[yellow]Press Ctrl+C to stop[/yellow]")

        try:
            with Live(generate_result_display(RealTimeResult(time.time(), None, [], [], [], [], [])), refresh_per_second=2) as live:
                while True:
                    if duration and (time.time() - start_time) > duration:
                        break

                    spectrum = source.generate_spectrum()

                    fake_reader = object()
                    parser = SpectrumDataParser()

                    result = RealTimeDemodulator(
                        SerialConfig(port="simulate"),
                        demod_config,
                    )._demodulate_spectrum(spectrum)

                    buffer.add(result)
                    live.update(generate_result_display(result))
                    time.sleep(source.update_interval)

        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping...[/yellow]")

        if output_file:
            import pandas as pd
            rows = []
            for result in buffer.get_all():
                for i, wl in enumerate(result.peak_wavelengths):
                    rows.append({
                        "timestamp": result.timestamp,
                        "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(result.timestamp)),
                        "peak_index": i + 1,
                        "peak_wavelength": wl,
                        "intensity": result.intensities[i] if i < len(result.intensities) else None,
                        "wavelength_shift": result.wavelength_shifts[i] if i < len(result.wavelength_shifts) else None,
                        "temperature": result.temperatures[i] if i < len(result.temperatures) else None,
                        "strain": result.strains[i] if i < len(result.strains) else None,
                    })
            df = pd.DataFrame(rows)
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            df.to_csv(output_file, index=False, encoding="utf-8-sig")
            console.print(f"[green]Results saved to: {output_file}[/green]")

        return buffer

    serial_config = SerialConfig(port=serial_port, baudrate=baudrate)
    demodulator = RealTimeDemodulator(serial_config, demod_config)

    def print_result(result: RealTimeResult):
        if result.error:
            console.print(f"[red]Error: {result.error}[/red]")
            return

        timestamp = time.strftime("%H:%M:%S", time.localtime(result.timestamp))
        for i, wl in enumerate(result.peak_wavelengths):
            shift = result.wavelength_shifts[i] if i < len(result.wavelength_shifts) else 0
            temp = result.temperatures[i] if i < len(result.temperatures) else None
            strain = result.strains[i] if i < len(result.strains) else None

            temp_str = f"{temp:.2f}°C" if temp is not None else "-"
            strain_str = f"{strain:.2f} με" if strain is not None else "-"

            console.print(
                f"[{timestamp}] Peak {i+1}: λ={wl:.4f} nm, "
                f"Δλ={shift:.4f} nm, T={temp_str}, ε={strain_str}"
            )

    demodulator.add_callback(print_result)

    console.print(f"[cyan]Connecting to {serial_port} at {baudrate} baud...[/cyan]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]")

    try:
        demodulator.start()

        start_time = time.time()
        while True:
            if duration and (time.time() - start_time) > duration:
                break
            time.sleep(0.1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping...[/yellow]")
    finally:
        demodulator.stop()

        if output_file:
            saved_path = demodulator.save_results(output_file)
            console.print(f"[green]Results saved to: {saved_path}[/green]")

    return demodulator.data_buffer
