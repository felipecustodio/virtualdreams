use clap::Parser;
use hound::{SampleFormat, WavReader, WavSpec, WavWriter};
use rustfft::{num_complex::Complex, FftPlanner};
use std::path::PathBuf;

#[derive(Parser)]
#[command(about = "Detect and extract the chorus from an audio file")]
struct Args {
    input: PathBuf,
    output: PathBuf,
    #[arg(long, default_value = "15")]
    duration: u32,
}

fn main() {
    let args = Args::parse();
    if let Err(e) = run(&args) {
        eprintln!("Error: {e}");
        std::process::exit(1);
    }
}

fn run(args: &Args) -> Result<(), Box<dyn std::error::Error>> {
    let (samples, sample_rate) = read_wav_mono(&args.input)?;

    let duration_samples = args.duration as usize * sample_rate as usize;
    if samples.len() < duration_samples {
        return Err(format!(
            "Audio ({:.1}s) is shorter than requested duration ({}s)",
            samples.len() as f32 / sample_rate as f32,
            args.duration
        )
        .into());
    }

    let start_sample = find_chorus_start(&samples, sample_rate, args.duration);
    let end_sample = (start_sample + duration_samples).min(samples.len());

    write_wav_mono(&args.output, &samples[start_sample..end_sample], sample_rate)?;
    Ok(())
}

// ---------------------------------------------------------------------------
// WAV I/O
// ---------------------------------------------------------------------------

fn read_wav_mono(path: &PathBuf) -> Result<(Vec<f32>, u32), Box<dyn std::error::Error>> {
    let mut reader = WavReader::open(path)?;
    let spec = reader.spec();
    let sample_rate = spec.sample_rate;
    let channels = spec.channels as usize;

    let samples: Vec<f32> = match (spec.sample_format, spec.bits_per_sample) {
        (SampleFormat::Float, 32) => {
            let raw: Vec<f32> = reader.samples::<f32>().collect::<hound::Result<_>>()?;
            if channels == 2 {
                raw.chunks(2).map(|c| (c[0] + c[1]) / 2.0).collect()
            } else {
                raw
            }
        }
        (SampleFormat::Int, 16) => {
            let raw: Vec<i16> = reader.samples::<i16>().collect::<hound::Result<_>>()?;
            let scale = i16::MAX as f32;
            if channels == 2 {
                raw.chunks(2)
                    .map(|c| (c[0] as f32 + c[1] as f32) / (2.0 * scale))
                    .collect()
            } else {
                raw.iter().map(|&s| s as f32 / scale).collect()
            }
        }
        (fmt, bits) => {
            return Err(format!("Unsupported WAV format: {fmt:?} {bits}bit").into())
        }
    };

    Ok((samples, sample_rate))
}

fn write_wav_mono(
    path: &PathBuf,
    samples: &[f32],
    sample_rate: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    let spec = WavSpec {
        channels: 1,
        sample_rate,
        bits_per_sample: 32,
        sample_format: SampleFormat::Float,
    };
    let mut writer = WavWriter::create(path, spec)?;
    for &s in samples {
        writer.write_sample(s)?;
    }
    writer.finalize()?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Chorus detection
// ---------------------------------------------------------------------------

fn find_chorus_start(samples: &[f32], sample_rate: u32, duration_secs: u32) -> usize {
    const FRAME_SIZE: usize = 2048;
    const HOP_SIZE: usize = 512;

    let chroma_frames = compute_chroma(samples, sample_rate, FRAME_SIZE, HOP_SIZE);
    let n_frames = chroma_frames.len();
    let duration_frames = (duration_secs as usize * sample_rate as usize) / HOP_SIZE;

    if n_frames <= duration_frames {
        return 0;
    }

    // The chorus is the most repeated section of a track. Its chroma is
    // closest to the global mean because it contributes to that mean multiple
    // times. Skip the first/last 10% to avoid intro and outro.
    let global_mean = mean_chroma(&chroma_frames);
    let skip = n_frames / 10;
    let end = n_frames.saturating_sub(duration_frames + skip);

    let mut best_score = f32::NEG_INFINITY;
    let mut best_frame = skip;

    for i in skip..=end {
        let window_mean = mean_chroma(&chroma_frames[i..i + duration_frames]);
        let score = cosine_similarity(&window_mean, &global_mean);
        if score > best_score {
            best_score = score;
            best_frame = i;
        }
    }

    best_frame * HOP_SIZE
}

fn compute_chroma(
    samples: &[f32],
    sample_rate: u32,
    frame_size: usize,
    hop_size: usize,
) -> Vec<[f32; 12]> {
    let mut planner = FftPlanner::<f32>::new();
    let fft = planner.plan_fft_forward(frame_size);
    let mut buffer = vec![Complex::new(0.0f32, 0.0f32); frame_size];
    let mut chroma_frames = Vec::new();
    let n_frames = samples.len().saturating_sub(frame_size) / hop_size + 1;

    for i in 0..n_frames {
        let start = i * hop_size;

        for j in 0..frame_size {
            let s = if start + j < samples.len() {
                samples[start + j]
            } else {
                0.0
            };
            // Hann window
            let w = 0.5
                * (1.0
                    - (2.0 * std::f32::consts::PI * j as f32 / (frame_size - 1) as f32).cos());
            buffer[j] = Complex::new(s * w, 0.0);
        }

        fft.process(&mut buffer);

        let mut chroma = [0.0f32; 12];
        let sr = sample_rate as f32;

        for k in 1..(frame_size / 2) {
            let freq = k as f32 * sr / frame_size as f32;
            if freq < 32.7 || freq > 4186.0 {
                continue; // outside piano range C1–C8
            }
            let pitch_class = freq_to_pitch_class(freq);
            chroma[pitch_class] += buffer[k].norm();
        }

        // L2 normalise
        let norm: f32 = chroma.iter().map(|&x| x * x).sum::<f32>().sqrt();
        if norm > 1e-6 {
            for x in chroma.iter_mut() {
                *x /= norm;
            }
        }

        chroma_frames.push(chroma);
    }

    chroma_frames
}

fn freq_to_pitch_class(freq: f32) -> usize {
    let midi = 12.0 * (freq / 440.0).log2() + 69.0;
    (midi.round() as i32).rem_euclid(12) as usize
}

fn mean_chroma(frames: &[[f32; 12]]) -> [f32; 12] {
    let mut mean = [0.0f32; 12];
    let n = frames.len() as f32;
    for frame in frames {
        for i in 0..12 {
            mean[i] += frame[i] / n;
        }
    }
    mean
}

fn cosine_similarity(a: &[f32; 12], b: &[f32; 12]) -> f32 {
    let dot: f32 = a.iter().zip(b.iter()).map(|(&x, &y)| x * y).sum();
    let na: f32 = a.iter().map(|&x| x * x).sum::<f32>().sqrt();
    let nb: f32 = b.iter().map(|&x| x * x).sum::<f32>().sqrt();
    if na < 1e-6 || nb < 1e-6 {
        return 0.0;
    }
    dot / (na * nb)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::f32::consts::PI;

    fn sine_samples(freq: f32, duration_secs: f32, sample_rate: u32) -> Vec<f32> {
        let n = (duration_secs * sample_rate as f32) as usize;
        (0..n)
            .map(|i| (2.0 * PI * freq * i as f32 / sample_rate as f32).sin())
            .collect()
    }

    #[test]
    fn test_find_chorus_returns_valid_offset() {
        let sr = 22050u32;
        let samples = sine_samples(440.0, 60.0, sr);
        let start = find_chorus_start(&samples, sr, 15);
        assert!(start + 15 * sr as usize <= samples.len());
    }

    #[test]
    fn test_find_chorus_short_audio_returns_zero() {
        let sr = 22050u32;
        let samples = sine_samples(440.0, 10.0, sr);
        // 10s audio with 15s duration → falls through to 0
        let start = find_chorus_start(&samples, sr, 15);
        assert_eq!(start, 0);
    }

    #[test]
    fn test_freq_to_pitch_class_a440() {
        assert_eq!(freq_to_pitch_class(440.0), 9); // A
    }

    #[test]
    fn test_freq_to_pitch_class_c4() {
        assert_eq!(freq_to_pitch_class(261.63), 0); // C
    }

    #[test]
    fn test_cosine_similarity_identical() {
        let a = [1.0f32, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];
        assert!((cosine_similarity(&a, &a) - 1.0).abs() < 1e-5);
    }

    #[test]
    fn test_cosine_similarity_orthogonal() {
        let a = [1.0f32, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];
        let b = [0.0f32, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];
        assert!(cosine_similarity(&a, &b).abs() < 1e-5);
    }
}
