import numpy as np
import time
from config import Config
from sta_lta import STALTADetector
from polarization import PolarizationAnalyzer
from magnitude import MagnitudeEstimator
from advanced_processing import cluster_and_classify_events, deduplicate_detections


class OnlineProcessingResult:
    def __init__(self):
        self.all_times = []
        self.all_data = []
        self.all_sta = []
        self.all_lta = []
        self.all_sta_lta_ratio = []
        self.all_rectilinearity = []
        self.all_incidence = []
        self.all_azimuth = []
        self.detections = []
        self.processing_times = []
        self.raw_detections = []

    def add_chunk(self, times, data, sta_lta_result, pol_result, mag_results, processing_time):
        self.all_times.extend(times.tolist())
        self.all_data.extend(data.tolist())
        self.all_sta.extend(sta_lta_result['sta'].tolist())
        self.all_lta.extend(sta_lta_result['lta'].tolist())
        self.all_sta_lta_ratio.extend(sta_lta_result['sta_lta_ratio'].tolist())
        self.all_rectilinearity.extend(pol_result['rectilinearity'].tolist())
        self.all_incidence.extend(pol_result['incidence_angle'].tolist())
        self.all_azimuth.extend(pol_result['azimuth'].tolist())
        self.processing_times.append(processing_time)

        for i, detection in enumerate(sta_lta_result['detections']):
            combined_result = detection.copy()
            if i < len(pol_result['verifications']):
                combined_result.update(pol_result['verifications'][i])
            if i < len(mag_results):
                combined_result.update(mag_results[i])

            combined_result['alert_level'] = Config.get_alert_level(
                combined_result['sta_lta_ratio'],
                combined_result.get('magnitude', np.nan)
            )

            combined_result['detection_delay'] = times[-1] - combined_result['arrival_time']
            combined_result['chunk_end_time'] = times[-1]

            overall_confidence = combined_result['confidence']
            if 'confidence' in combined_result:
                pol_conf = combined_result.get('confidence', 0.5)
                overall_confidence = 0.4 * overall_confidence + 0.4 * pol_conf + 0.2

            combined_result['overall_confidence'] = min(1.0, overall_confidence)
            self.raw_detections.append(combined_result)
            self.detections.append(combined_result)

    def finalize(self):
        self.all_times = np.array(self.all_times)
        self.all_data = np.array(self.all_data)
        self.all_sta = np.array(self.all_sta)
        self.all_lta = np.array(self.all_lta)
        self.all_sta_lta_ratio = np.array(self.all_sta_lta_ratio)
        self.all_rectilinearity = np.array(self.all_rectilinearity)
        self.all_incidence = np.array(self.all_incidence)
        self.all_azimuth = np.array(self.all_azimuth)
        self.avg_processing_time = np.mean(self.processing_times) if self.processing_times else 0
        self.max_processing_time = np.max(self.processing_times) if self.processing_times else 0

        if Config.aftershock_detection_enabled and len(self.raw_detections) > 0:
            self.detections = deduplicate_detections(self.raw_detections, time_tolerance=1.0)
            self.detections = cluster_and_classify_events(self.detections)
            self.num_clusters = len(set(d.get('cluster_id') for d in self.detections if d.get('cluster_id') is not None))
        else:
            self.detections = self.raw_detections
            self.num_clusters = 0


class OnlineProcessor:
    def __init__(self, sampling_rate):
        self.sampling_rate = sampling_rate
        self.sta_lta_detector = STALTADetector(sampling_rate)
        self.polarization_analyzer = PolarizationAnalyzer(sampling_rate)
        self.magnitude_estimator = MagnitudeEstimator(sampling_rate)
        self.result = OnlineProcessingResult()

    def process_stream(self, stream_simulator, verbose=True):
        self.reset()

        chunk_count = 0
        while stream_simulator.has_next():
            chunk = stream_simulator.next_chunk()
            if chunk is None:
                break

            start_time = time.time()

            sta_lta_result = self.sta_lta_detector.process_chunk(chunk.data, chunk.times)
            arrival_indices = [d['arrival_idx'] for d in sta_lta_result['detections']]

            pol_result = self.polarization_analyzer.process_chunk(chunk.data, arrival_indices)
            mag_results = self.magnitude_estimator.process_chunk(chunk.data, arrival_indices)

            processing_time = (time.time() - start_time) * 1000

            self.result.add_chunk(
                chunk.times,
                chunk.data,
                sta_lta_result,
                pol_result,
                mag_results,
                processing_time
            )

            if verbose and sta_lta_result['detections']:
                for det in sta_lta_result['detections']:
                    delay = chunk.times[-1] - det['arrival_time']
                    print(f"[Chunk {chunk_count}] P波检测: "
                          f"到时={det['arrival_time']:.2f}s, "
                          f"STA/LTA={det['sta_lta_ratio']:.2f}, "
                          f"检测延迟={delay:.2f}s")

            chunk_count += 1

        self.result.finalize()
        return self.result

    def reset(self):
        self.sta_lta_detector.reset()
        self.polarization_analyzer.reset()
        self.magnitude_estimator.reset()
        self.result = OnlineProcessingResult()


class SlidingWindowProcessor:
    def __init__(self, waveform_data, window_size=None, overlap=None):
        if window_size is None:
            window_size = Config.online_window_size
        if overlap is None:
            overlap = Config.online_overlap

        self.waveform = waveform_data
        self.window_size = window_size
        self.overlap = overlap
        self.dt = 1.0 / waveform_data.sampling_rate
        self.window_npts = int(window_size / self.dt)
        self.step_npts = int((window_size - overlap) / self.dt)

    def process_offline(self, true_p_arrival=None, verbose=True, site_class=None):
        from sta_lta import compute_sta_lta, detect_p_arrival
        from polarization import compute_polarization_parameters, verify_p_wave
        from magnitude import estimate_magnitude
        from advanced_processing import cluster_and_classify_events, deduplicate_detections

        results = {
            'windows': [],
            'detections': [],
            'detection_delays': [],
            'all_detections': []
        }

        npts = self.waveform.npts
        start_idx = 0

        while start_idx + self.window_npts <= npts:
            end_idx = start_idx + self.window_npts
            window_data = self.waveform.slice(start_idx, end_idx)

            combined_amp = np.sqrt(np.sum(window_data.data ** 2, axis=1))
            sta, lta, sta_lta_ratio = compute_sta_lta(combined_amp, self.waveform.sampling_rate)
            detections = detect_p_arrival(sta_lta_ratio, window_data.times)

            window_result = {
                'start_time': window_data.times[0],
                'end_time': window_data.times[-1],
                'start_idx': start_idx,
                'end_idx': end_idx,
                'sta': sta,
                'lta': lta,
                'sta_lta_ratio': sta_lta_ratio,
                'times': window_data.times,
                'data': window_data.data,
                'detections_raw': detections
            }

            if detections:
                pol_params = compute_polarization_parameters(window_data.data, self.waveform.sampling_rate)

                for det in detections:
                    global_idx = start_idx + det['arrival_idx']
                    det['global_arrival_idx'] = global_idx
                    det['global_arrival_time'] = self.waveform.times[global_idx]

                    if true_p_arrival is not None:
                        det['detection_delay'] = window_data.times[-1] - true_p_arrival
                        results['detection_delays'].append(det['detection_delay'])

                    pol_verif = verify_p_wave(pol_params, det['arrival_idx'])
                    det.update(pol_verif)

                    mag_result = estimate_magnitude(
                        window_data.data, self.dt, det['arrival_idx'],
                        method='combined',
                        polarization_params=pol_params,
                        site_class=site_class
                    )
                    det.update(mag_result)

                    det['alert_level'] = Config.get_alert_level(
                        det['sta_lta_ratio'],
                        det.get('magnitude', np.nan)
                    )

                    det['overall_confidence'] = min(1.0,
                        0.4 * det['confidence'] + 0.4 * det.get('confidence', 0.5) + 0.2
                    )

                    results['all_detections'].append(det)

                    if verbose:
                        delay_str = f", 延迟={det['detection_delay']:.2f}s" if 'detection_delay' in det else ""
                        mag_str = f", 震级={det['magnitude']:.1f}" if 'magnitude' in det and not np.isnan(det['magnitude']) else ""
                        event_type = f", 类型={det.get('event_type', 'N/A')}" if 'event_type' in det else ""
                        print(f"[窗口 {window_data.times[0]:.1f}-{window_data.times[-1]:.1f}s] "
                              f"P波检测: 到时={det['arrival_time']:.2f}s"
                              f"{mag_str}"
                              f"{delay_str}"
                              f"{event_type}")

            results['windows'].append(window_result)
            start_idx += self.step_npts

        if Config.aftershock_detection_enabled and len(results['all_detections']) > 0:
            results['detections'] = deduplicate_detections(results['all_detections'], time_tolerance=1.0)
            results['detections'] = cluster_and_classify_events(results['detections'])
            results['num_clusters'] = len(set(d.get('cluster_id') for d in results['detections'] if d.get('cluster_id') is not None))
        else:
            results['detections'] = results['all_detections']
            results['num_clusters'] = 0

        if results['detection_delays']:
            results['avg_delay'] = np.mean(results['detection_delays'])
            results['min_delay'] = np.min(results['detection_delays'])
            results['max_delay'] = np.max(results['detection_delays'])
        else:
            results['avg_delay'] = None
            results['min_delay'] = None
            results['max_delay'] = None

        return results
