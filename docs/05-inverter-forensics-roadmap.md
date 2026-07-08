# Inverter Event Forensics Roadmap

## Vision

Build software for high-frequency inverter diagnostics.

This is not the first project. It becomes powerful after DSP knowledge, power electronics basics, lab access, inverter data, waveform data, and professor collaboration.

## Market Pain

Utilities and plant operators need to know:

- Why an inverter tripped
- Whether harmonics are increasing
- Whether grid resonance exists
- Whether protection misoperated
- Whether commissioning issues are present
- Whether power quality is damaging equipment

## Core Technical Stack

- Python DSP
- FFT
- THD calculation
- Harmonic detection
- Voltage sag/swell detection
- Frequency deviation
- Sequence-of-events reconstruction
- Isolation Forest anomaly detection
- Later: 1D CNN if labeled data is available

## Product Output

Inverter Event Forensics Platform.

Use during:

- Commissioning
- Troubleshooting
- O&M
- Grid compliance
- Power quality analysis

## Prototype Milestones

### M1: Synthetic Waveform Lab

Generate sine waves with sag, swell, harmonics, frequency deviation, and interruption events.

### M2: Event Detector

Detect event type, start time, duration, and severity.

### M3: THD and Harmonic Report

Compute FFT, harmonic amplitudes, and THD.

### M4: Forensics Report

Produce a concise explanation:

- What happened
- When it happened
- Why it may have happened
- What to inspect next

