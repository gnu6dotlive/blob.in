//! CP-JA7E: bounded, opt-in adaptive polling intervals. No arbitrary durations.
//! Idle worker threads must wait on a command, never wake on a periodic timer.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Profile {
    Latency,
    Balanced,
    Eco,
}
impl Profile {
    pub(crate) fn from_env() -> Self {
        match std::env::var("CPJA7E_POLL_PROFILE").ok().as_deref() {
            Some("latency") => Self::Latency,
            Some("eco") => Self::Eco,
            Some("balanced") | None => Self::Balanced,
            Some(other) => {
                log::warn!("CPJA7E_PROFILE_INVALID requested={other:?} fallback=balanced");
                Self::Balanced
            }
        }
    }
    pub(crate) const fn cadence_us(self) -> u64 {
        match self {
            Self::Latency => 250,
            Self::Balanced => 1000,
            Self::Eco => 4000,
        }
    }
    pub(crate) const fn name(self) -> &'static str {
        match self {
            Self::Latency => "latency",
            Self::Balanced => "balanced",
            Self::Eco => "eco",
        }
    }
}
#[cfg(target_os = "linux")]
pub(crate) fn thread_cpu_us() -> u64 {
    let mut usage: libc::rusage = unsafe { core::mem::zeroed() };
    if unsafe { libc::getrusage(libc::RUSAGE_THREAD, &mut usage) } != 0 {
        return 0;
    }
    let a = usage.ru_utime;
    let b = usage.ru_stime;
    ((a.tv_sec + b.tv_sec) as u64) * 1_000_000 + (a.tv_usec + b.tv_usec) as u64
}
#[cfg(not(target_os = "linux"))]
pub(crate) fn thread_cpu_us() -> u64 {
    0
}
#[cfg(all(target_os = "linux", feature = "gnu6-cpja7eb-benchmark"))]
pub(crate) fn thread_context_switches() -> Option<(u64, u64)> {
    let status = std::fs::read_to_string("/proc/thread-self/status").ok()?;
    let read = |prefix: &str| {
        status
            .lines()
            .find(|line| line.starts_with(prefix))
            .and_then(|line| line.split_whitespace().last())
            .and_then(|value| value.parse::<u64>().ok())
    };
    Some((
        read("voluntary_ctxt_switches:")?,
        read("nonvoluntary_ctxt_switches:")?,
    ))
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bounded_positive_cadence() {
        for p in [Profile::Latency, Profile::Balanced, Profile::Eco] {
            assert!(p.cadence_us() >= 250 && p.cadence_us() <= 4000);
        }
    }
    #[test]
    fn unique_profiles() {
        assert_eq!(Profile::Latency.name(), "latency");
        assert_eq!(Profile::Balanced.name(), "balanced");
        assert_eq!(Profile::Eco.name(), "eco");
        assert!(Profile::Latency.cadence_us() < Profile::Balanced.cadence_us());
        assert!(Profile::Balanced.cadence_us() < Profile::Eco.cadence_us());
    }
}
