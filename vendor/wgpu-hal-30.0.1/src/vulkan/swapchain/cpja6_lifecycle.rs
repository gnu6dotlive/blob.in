//! GNU6 CP-JA6: one-shot per-generation Vulkan present ID authority.
//! A failed/uncertain presentation permanently poisons this swapchain.
#[cfg(feature = "gnu6-cpja7d-multi-inflight")]
use alloc::collections::VecDeque;
use core::sync::atomic::{AtomicU64, Ordering};

static NEXT_GENERATION: AtomicU64 = AtomicU64::new(1);

#[derive(Debug)]
pub(crate) struct PresentLifecycle {
    generation: u64,
    next_id: u64,
    #[cfg(not(feature = "gnu6-cpja7d-multi-inflight"))]
    outstanding: Option<u64>,
    #[cfg(feature = "gnu6-cpja7d-multi-inflight")]
    outstanding: VecDeque<u64>,
    poisoned: bool,
}
impl PresentLifecycle {
    pub(crate) fn new() -> Result<Self, &'static str> {
        let generation = NEXT_GENERATION.fetch_add(1, Ordering::Relaxed);
        if generation == 0 || generation == u64::MAX {
            return Err("CPJA6_GENERATION_ID_EXHAUSTED");
        }
        Ok(Self {
            generation,
            next_id: 1,
            #[cfg(not(feature = "gnu6-cpja7d-multi-inflight"))]
            outstanding: None,
            #[cfg(feature = "gnu6-cpja7d-multi-inflight")]
            outstanding: VecDeque::new(),
            poisoned: false,
        })
    }
    pub(crate) fn generation(&self) -> u64 {
        self.generation
    }
    pub(crate) fn begin(&mut self) -> Result<u64, &'static str> {
        if self.poisoned {
            return Err("CPJA6_SWAPCHAIN_POISONED");
        }
        #[cfg(not(feature = "gnu6-cpja7d-multi-inflight"))]
        if self.outstanding.is_some() {
            return Err("CPJA6_PRESENT_STILL_OUTSTANDING");
        }
        let id = self.next_id;
        if id == 0 {
            self.poisoned = true;
            return Err("CPJA6_PRESENT_ID_OVERFLOW");
        }
        self.next_id = self.next_id.checked_add(1).unwrap_or(0);
        #[cfg(not(feature = "gnu6-cpja7d-multi-inflight"))]
        {
            self.outstanding = Some(id);
        }
        #[cfg(feature = "gnu6-cpja7d-multi-inflight")]
        {
            if self.outstanding.len() >= 2 {
                self.poison();
                return Err("CPJA7D_INFLIGHT_CAP_EXCEEDED");
            }
            self.outstanding.push_back(id);
        }
        Ok(id)
    }
    pub(crate) fn acknowledge(&mut self, id: u64) -> Result<(), &'static str> {
        if self.poisoned {
            return Err("CPJA6_SWAPCHAIN_POISONED");
        }
        #[cfg(not(feature = "gnu6-cpja7d-multi-inflight"))]
        if self.outstanding != Some(id) {
            self.poisoned = true;
            return Err("CPJA6_PRESENT_ACK_WRONG_GENERATION_OR_ID");
        }
        #[cfg(not(feature = "gnu6-cpja7d-multi-inflight"))]
        {
            self.outstanding = None;
        }
        #[cfg(all(
            feature = "gnu6-cpja7d-multi-inflight",
            not(feature = "gnu6-cpja7db-async-retire")
        ))]
        {
            if self.outstanding.pop_front() != Some(id) {
                self.poison();
                return Err("CPJA7D_ACK_OUT_OF_ORDER");
            }
        }
        #[cfg(feature = "gnu6-cpja7db-async-retire")]
        {
            if let Some(position) = self.outstanding.iter().position(|&pending| pending == id) {
                self.outstanding.remove(position);
            } else {
                self.poison();
                return Err("CPJA7DB_ACK_UNKNOWN_OR_DUPLICATE");
            }
        }
        Ok(())
    }
    #[cfg(feature = "gnu6-cpja7db-async-retire")]
    pub(crate) fn acknowledge_from_worker(
        &mut self,
        generation: u64,
        id: u64,
    ) -> Result<(), &'static str> {
        if generation != self.generation {
            self.poison();
            return Err("CPJA7DB_CROSS_GENERATION_ACK");
        }
        self.acknowledge(id)
    }
    #[cfg(all(feature = "gnu6-cpja7db-async-retire",test))]
    pub(crate) fn contains(&self, id: u64) -> bool {
        self.outstanding.contains(&id)
    }
    pub(crate) fn poison(&mut self) {
        self.poisoned = true;
        #[cfg(not(feature = "gnu6-cpja7d-multi-inflight"))]
        {
            self.outstanding = None;
        }
        #[cfg(feature = "gnu6-cpja7d-multi-inflight")]
        {
            self.outstanding.clear();
        }
    }
    #[cfg(feature = "gnu6-cpja7d-multi-inflight")]
    pub(crate) fn oldest(&self) -> Option<u64> {
        self.outstanding.front().copied()
    }
    #[cfg(feature = "gnu6-cpja7d-multi-inflight")]
    pub(crate) fn pending(&self) -> usize {
        self.outstanding.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn sequential_ack_monotone() {
        let mut s = PresentLifecycle::new().unwrap();
        for id in 1..=120 {
            assert_eq!(s.begin(), Ok(id));
            assert_eq!(s.acknowledge(id), Ok(()));
        }
        assert_eq!(s.begin(), Ok(121));
    }
    #[cfg(not(feature = "gnu6-cpja7d-multi-inflight"))]
    #[test]
    fn reject_duplicate_submission_before_ack() {
        let mut s = PresentLifecycle::new().unwrap();
        assert_eq!(s.begin(), Ok(1));
        assert_eq!(s.begin(), Err("CPJA6_PRESENT_STILL_OUTSTANDING"));
    }
    #[test]
    fn wrong_ack_poisoned() {
        let mut s = PresentLifecycle::new().unwrap();
        assert_eq!(s.begin(), Ok(1));
        #[cfg(not(feature = "gnu6-cpja7d-multi-inflight"))]
        assert_eq!(
            s.acknowledge(2),
            Err("CPJA6_PRESENT_ACK_WRONG_GENERATION_OR_ID")
        );
        #[cfg(all(
            feature = "gnu6-cpja7d-multi-inflight",
            not(feature = "gnu6-cpja7db-async-retire")
        ))]
        assert_eq!(s.acknowledge(2), Err("CPJA7D_ACK_OUT_OF_ORDER"));
        #[cfg(feature = "gnu6-cpja7db-async-retire")]
        assert_eq!(s.acknowledge(2), Err("CPJA7DB_ACK_UNKNOWN_OR_DUPLICATE"));
        assert_eq!(s.begin(), Err("CPJA6_SWAPCHAIN_POISONED"));
    }
    #[test]
    fn timeout_poisoned_and_no_id_reuse() {
        let mut s = PresentLifecycle::new().unwrap();
        assert_eq!(s.begin(), Ok(1));
        s.poison();
        assert_eq!(s.begin(), Err("CPJA6_SWAPCHAIN_POISONED"));
        assert_eq!(s.acknowledge(1), Err("CPJA6_SWAPCHAIN_POISONED"));
    }
    #[test]
    fn new_generation_discards_older_authority() {
        let mut old = PresentLifecycle::new().unwrap();
        assert_eq!(old.begin(), Ok(1));
        old.poison();
        let mut new = PresentLifecycle::new().unwrap();
        assert!(new.generation() > old.generation());
        assert_eq!(new.begin(), Ok(1));
        assert_eq!(old.begin(), Err("CPJA6_SWAPCHAIN_POISONED"));
    }
    #[cfg(feature = "gnu6-cpja7d-multi-inflight")]
    #[test]
    fn two_outstanding_and_fifo_retirement() {
        let mut s = PresentLifecycle::new().unwrap();
        assert_eq!(s.begin(), Ok(1));
        assert_eq!(s.begin(), Ok(2));
        assert_eq!(s.pending(), 2);
        assert_eq!(s.oldest(), Some(1));
        assert_eq!(s.acknowledge(1), Ok(()));
        assert_eq!(s.begin(), Ok(3));
        assert_eq!(s.acknowledge(2), Ok(()));
        assert_eq!(s.acknowledge(3), Ok(()));
        assert_eq!(s.pending(), 0);
    }
    #[cfg(feature = "gnu6-cpja7d-multi-inflight")]
    #[test]
    fn loss_invalidates_multiple_unacked_ids() {
        let mut s = PresentLifecycle::new().unwrap();
        assert_eq!(s.begin(), Ok(1));
        assert_eq!(s.begin(), Ok(2));
        s.poison();
        assert_eq!(s.pending(), 0);
        assert_eq!(s.begin(), Err("CPJA6_SWAPCHAIN_POISONED"));
        assert_eq!(s.acknowledge(1), Err("CPJA6_SWAPCHAIN_POISONED"));
    }
    #[cfg(feature = "gnu6-cpja7db-async-retire")]
    #[test]
    fn out_of_order_completion_and_generation_bound() {
        let mut s = PresentLifecycle::new().unwrap();
        let g = s.generation();
        assert_eq!(s.begin(), Ok(1));
        assert_eq!(s.begin(), Ok(2));
        assert_eq!(s.acknowledge_from_worker(g, 2), Ok(()));
        assert!(s.contains(1));
        assert!(!s.contains(2));
        assert_eq!(s.begin(), Ok(3));
        assert_eq!(s.acknowledge_from_worker(g, 1), Ok(()));
        assert_eq!(s.acknowledge_from_worker(g, 3), Ok(()));
        assert_eq!(s.pending(), 0);
        assert_eq!(
            s.acknowledge_from_worker(g, 2),
            Err("CPJA7DB_ACK_UNKNOWN_OR_DUPLICATE")
        );
        assert_eq!(s.begin(), Err("CPJA6_SWAPCHAIN_POISONED"));
    }
    #[cfg(feature = "gnu6-cpja7db-async-retire")]
    #[test]
    fn wrong_generation_revokes_old_pending() {
        let mut s = PresentLifecycle::new().unwrap();
        let g = s.generation();
        assert_eq!(s.begin(), Ok(1));
        assert_eq!(
            s.acknowledge_from_worker(g + 1, 1),
            Err("CPJA7DB_CROSS_GENERATION_ACK")
        );
        assert_eq!(s.pending(), 0);
        assert_eq!(s.begin(), Err("CPJA6_SWAPCHAIN_POISONED"));
    }
    #[cfg(feature = "gnu6-cpja7d-multi-inflight")]
    #[test]
    fn refuse_third_while_window_full() {
        let mut s = PresentLifecycle::new().unwrap();
        assert_eq!(s.begin(), Ok(1));
        assert_eq!(s.begin(), Ok(2));
        assert_eq!(s.begin(), Err("CPJA7D_INFLIGHT_CAP_EXCEEDED"));
        assert_eq!(s.pending(), 0);
    }
    #[test]
    fn checked_overflow_denies_issue() {
        let mut s = PresentLifecycle::new().unwrap();
        s.next_id = u64::MAX;
        assert_eq!(s.begin(), Ok(u64::MAX));
        assert_eq!(s.acknowledge(u64::MAX), Ok(()));
        assert_eq!(s.begin(), Err("CPJA6_PRESENT_ID_OVERFLOW"));
    }
}
