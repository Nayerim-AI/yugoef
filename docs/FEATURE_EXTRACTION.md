# Yugoef CSI Feature Extraction

**Status:** deterministic cloud feature extraction for synthetic binary CSI fixtures.  
**Hardware status:** not verified using ESP32 CSI captures.

## Data Notice

```text
SYNTHETIC TEST DATA
NOT CAPTURED FROM A REAL PERSON
NOT HARDWARE-VALIDATED
```

## Input

Feature extraction consumes output from `yugoef.signal_processing.pipeline`:

```text
Raw CSI packet
→ protocol parser
→ signal-processing window
→ CsiFeatureExtractor
→ CsiFeatureVector
```

It does not decode raw packets again.

## Output

`CsiFeatureVector` fields include:

- node/room/boot/window identifiers
- window timestamps from device uptime
- sample count and effective sample rate
- packet loss rate
- RSSI, noise floor, SNR
- amplitude mean/std/variance
- phase variance
- phase derivative energy
- motion energy
- presence score
- subcarrier coherence
- active subcarrier count
- signal quality score
- deterministic evidence
- extractor version `yugoef-feature-v1`

## Formulas

### SNR

```text
snr_db = rssi_dbm - noise_floor_dbm
```

### Amplitude statistics

Computed from all amplitudes in the processed bounded window.

```text
amplitude_mean = mean(amplitudes)
amplitude_variance = population_variance(amplitudes)
amplitude_std = population_stddev(amplitudes)
```

### Phase statistics

```text
phase_variance = population_variance(unwrapped_phase_values)
```

Phase derivative energy uses active subcarriers:

```text
phase_derivative_energy = mean((phase[t] - phase[t-1])²)
```

### Motion energy

Motion is deterministic and based on temporal differences in active subcarriers:

```text
amplitude_energy = mean(abs(amplitude[t] - amplitude[t-1])) / CSI_MOTION_ENERGY_SCALE
phase_energy = mean(abs(phase[t] - phase[t-1])) / CSI_MOTION_ENERGY_SCALE
motion_energy = clamp01(
    CSI_MOTION_AMPLITUDE_WEIGHT * clamp01(amplitude_energy)
  + CSI_MOTION_PHASE_WEIGHT * clamp01(phase_energy)
)
```

### Presence score

Presence is a room-activity heuristic, not validated human classification:

```text
presence_score = clamp01(
    CSI_PRESENCE_MOTION_WEIGHT * motion_energy
  + CSI_PRESENCE_PHASE_WEIGHT * normalized_phase_variance
  + CSI_PRESENCE_AMPLITUDE_WEIGHT * normalized_amplitude_variance
  + CSI_PRESENCE_ACTIVE_SUBCARRIER_WEIGHT * active_subcarrier_ratio
)
```

### Signal quality score

Signal quality is deterministic and uses metadata plus processing quality:

```text
signal_quality_score = clamp01(
    0.25 * rssi_quality
  + 0.25 * snr_quality
  + 0.20 * packet_loss_quality
  + 0.15 * sample_rate_quality
  + 0.10 * subcarrier_coherence
  + 0.05 * sample_completeness
)
```

Quality sub-scores are linear between configured bad/good thresholds.

## Evidence

Evidence is condition-based. Examples:

- `motion energy elevated from temporal CSI changes`
- `motion energy elevated from temporal phase changes`
- `phase variance above configured activity scale`
- `packet loss reduced signal quality`
- `RSSI below preferred operating range`
- `SNR below preferred operating range`
- `active subcarriers indicate coherent environmental change`
- `signal quality score is low`

No evidence sentence is always added.

## Configuration

Environment variables:

```text
CSI_FEATURE_EXTRACTOR_VERSION=yugoef-feature-v1
CSI_MOTION_AMPLITUDE_WEIGHT=0.5
CSI_MOTION_PHASE_WEIGHT=0.5
CSI_MOTION_ENERGY_SCALE=1.0
CSI_PRESENCE_MOTION_WEIGHT=0.40
CSI_PRESENCE_PHASE_WEIGHT=0.25
CSI_PRESENCE_AMPLITUDE_WEIGHT=0.20
CSI_PRESENCE_ACTIVE_SUBCARRIER_WEIGHT=0.15
CSI_PRESENCE_ENTER_THRESHOLD=0.60
CSI_PRESENCE_EXIT_THRESHOLD=0.40
CSI_QUALITY_MIN_RSSI_DBM=-85
CSI_QUALITY_GOOD_RSSI_DBM=-50
CSI_QUALITY_MIN_SNR_DB=5
CSI_QUALITY_GOOD_SNR_DB=30
CSI_QUALITY_MAX_PACKET_LOSS=0.30
CSI_QUALITY_TARGET_SAMPLE_RATE_HZ=20
```

Motion and presence weights are validated to sum to `1.0`.

## Deferred Features

Breathing, heart rate, fall detection, and person counting are deferred until real CSI captures, room calibration, and ground-truth evaluation are available.

No medical, distress, safety-critical, or person-counting inference is implemented in this stage.
