#!/usr/bin/env bash

set -euo pipefail

log() {
  printf 'totem-performance: %s\n' "$*"
}

set_cpu_governor() {
  local governor_file

  for governor_file in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    if [ -w "$governor_file" ] && grep -qw performance "$(dirname "$governor_file")/scaling_available_governors"; then
      if printf '%s\n' performance > "$governor_file"; then
        log "set $governor_file=performance"
      else
        log "unable to set $governor_file=performance"
      fi
    fi
  done
}

set_pcie_aspm_policy() {
  local policy_file="/sys/module/pcie_aspm/parameters/policy"

  if [ -w "$policy_file" ] && grep -qw performance "$policy_file"; then
    if printf '%s\n' performance > "$policy_file"; then
      log "set $policy_file=performance"
    else
      log "unable to set $policy_file=performance"
    fi
  fi
}

set_scheduler_tuning() {
  local cfs_slice="/proc/sys/kernel/sched_cfs_bandwidth_slice_us"
  local rt_runtime="/proc/sys/kernel/sched_rt_runtime_us"

  if [ -w "$cfs_slice" ]; then
    if printf '%s\n' 1000000 > "$cfs_slice"; then
      log "set kernel.sched_cfs_bandwidth_slice_us=1000000"
    else
      log "unable to set kernel.sched_cfs_bandwidth_slice_us=1000000"
    fi
  fi

  if [ -w "$rt_runtime" ]; then
    if printf '%s\n' -1 > "$rt_runtime"; then
      log "disabled RT runtime throttling"
    else
      log "unable to disable RT runtime throttling"
    fi
  fi
}

set_cgroup_cpu_period() {
  local cpu_max

  if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
    while IFS= read -r cpu_max; do
      if [ -w "$cpu_max" ]; then
        read -r quota period < "$cpu_max" || true
        if [ "${quota:-}" = "max" ] && [ "${period:-}" != "1000000" ]; then
          if printf 'max 1000000\n' > "$cpu_max"; then
            log "set $cpu_max=max 1000000"
          else
            log "unable to set $cpu_max=max 1000000"
          fi
        fi
      fi
    done < <(find /sys/fs/cgroup -name cpu.max -print 2>/dev/null)
  else
    while IFS= read -r cpu_max; do
      if [ -w "$cpu_max" ]; then
        if printf '%s\n' 1000000 > "$cpu_max"; then
          log "set $cpu_max=1000000"
        else
          log "unable to set $cpu_max=1000000"
        fi
      fi
    done < <(find /sys/fs/cgroup -name cpu.cfs_period_us -print 2>/dev/null)
  fi
}

report_throttling() {
  if command -v vcgencmd >/dev/null 2>&1; then
    log "$(vcgencmd get_throttled || true)"
  fi
}

set_cpu_governor
set_pcie_aspm_policy
set_scheduler_tuning
set_cgroup_cpu_period
report_throttling
