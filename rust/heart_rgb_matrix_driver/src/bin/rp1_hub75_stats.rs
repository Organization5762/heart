use std::env;

use heart_rgb_matrix_driver::{
    rp1_hub75_read_pack_stats_from, rp1_hub75_read_present_stats_from,
    rp1_hub75_read_worker_status_from,
};

const DEFAULT_DEVICE_PATH: &str = "/dev/rp1-hub75";

fn main() {
    let device_path = env::args()
        .nth(1)
        .unwrap_or_else(|| DEFAULT_DEVICE_PATH.to_string());
    match rp1_hub75_read_pack_stats_from(&device_path) {
        Ok(stats) => {
            println!("device={device_path}");
            println!("frames_packed={}", stats.frames_packed);
            println!("bytes_packed={}", stats.bytes_packed);
            println!("last_error={}", stats.last_error);
            println!("words_per_frame={}", stats.words_per_frame);
        }
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
    match rp1_hub75_read_present_stats_from(&device_path) {
        Ok(stats) => {
            println!("frames_queued={}", stats.frames_queued);
            println!("frames_presented={}", stats.frames_presented);
            println!("frames_dropped={}", stats.frames_dropped);
            println!("vsync_count={}", stats.vsync_count);
            println!("queued_seq={}", stats.queued_seq);
            println!("presented_seq={}", stats.presented_seq);
            println!("displayed_slot={}", stats.displayed_slot);
            println!("pending_slot={}", stats.pending_slot);
        }
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
    match rp1_hub75_read_worker_status_from(&device_path) {
        Ok(status) => {
            println!("worker_state={}", status.state);
            println!("worker_flags={}", status.flags);
            println!("worker_status_timeout_ms={}", status.status_timeout_ms);
            println!("worker_seq={}", status.worker_seq);
            println!("worker_vsync_count={}", status.vsync_count);
            println!("worker_queued_seq={}", status.queued_seq);
            println!("worker_presented_seq={}", status.presented_seq);
            println!("worker_displayed_slot={}", status.displayed_slot);
            println!("worker_pending_slot={}", status.pending_slot);
            println!("worker_frames_queued={}", status.frames_queued);
            println!("worker_frames_presented={}", status.frames_presented);
            println!("worker_frames_dropped={}", status.frames_dropped);
            println!("worker_last_error={}", status.last_error);
            println!("worker_last_vsync_ns={}", status.last_vsync_ns);
        }
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
}
