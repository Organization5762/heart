use std::fs;
use std::os::unix::fs::MetadataExt;
use std::path::Path;

pub(crate) fn describe_device_permissions(path: &Path) -> String {
    match fs::metadata(path) {
        Ok(metadata) => format!(
            "Current ownership is uid={} gid={} mode={:#o}.",
            metadata.uid(),
            metadata.gid(),
            metadata.mode() & 0o7777
        ),
        Err(_) => format!("Unable to query permissions for {}.", path.display()),
    }
}
