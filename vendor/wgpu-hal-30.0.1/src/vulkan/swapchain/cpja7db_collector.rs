//! CP-JA7D-B: private per-swapchain async Vulkan present-wait observer.
//! A completion is authoritative only when the actual vkWaitForPresentKHR returns SUCCESS.
use super::super::DeviceShared;
use alloc::sync::Arc;
use ash::{khr, vk};
use parking_lot::Mutex;
use std::{
    sync::mpsc::{self, Receiver, RecvTimeoutError, Sender, TryRecvError},
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

#[derive(Clone, Copy, Debug)]
pub(crate) enum Outcome {
    Ready {
        generation: u64,
        id: u64,
    },
    Fault {
        generation: u64,
        id: u64,
        error: vk::Result,
    },
}
enum Command {
    Submit(u64),
    Flush,
    Stop,
}

pub(crate) struct Collector {
    tx: Sender<Command>,
    results: Mutex<Receiver<Outcome>>,
    thread: Mutex<Option<JoinHandle<()>>>,
}
impl Collector {
    pub(crate) fn spawn(
        generation: u64,
        raw: vk::SwapchainKHR,
        shared: Arc<DeviceShared>,
    ) -> Result<Self, &'static str> {
        let (tx, commands) = mpsc::channel();
        let (result_tx, results) = mpsc::channel();
        let thread=thread::Builder::new()
             .name(format!("cpja7db-wsi-{generation}"))
             .spawn(move || {
                 // Keep the raw device and Vulkan loader owned by the worker until joined.
                 let wait=khr::present_wait::Device::new(&shared.instance.raw,&shared.raw);
                 let mut pending=alloc::vec::Vec::<u64>::new();
                 let mut ready=alloc::vec::Vec::<u64>::new();
                 let mut sequence=0_u64;
                 let mut delivery=0_u64;
                 let mut flushing=false;
                 #[cfg(feature="gnu6-cpja7e-adaptive-scheduler")]
                 let profile=super::cpja7e_policy::Profile::from_env();
                 #[cfg(feature="gnu6-cpja7e-adaptive-scheduler")]
                 let begun=Instant::now();
                 #[cfg(feature="gnu6-cpja7e-adaptive-scheduler")]
                 let cpu_before=super::cpja7e_policy::thread_cpu_us();
                 #[cfg(feature="gnu6-cpja7e-adaptive-scheduler")]
                 let (mut wait_calls,mut timeouts,mut polls,mut idle_wakes,mut idle_us,mut active_us)=(0_u64,0_u64,0_u64,0_u64,0_u64,0_u64);
                 #[cfg(feature="gnu6-cpja7e-adaptive-scheduler")]
                 let mut staged:Option<Command>=None;
                 'worker: loop {
                     loop {
                         #[cfg(feature="gnu6-cpja7e-adaptive-scheduler")]
                         let msg=staged.take().map(Ok).unwrap_or_else(||commands.try_recv());
                         #[cfg(not(feature="gnu6-cpja7e-adaptive-scheduler"))]
                         let msg=commands.try_recv();
                         match msg {
                             Ok(Command::Submit(id)) => {
                                 pending.push(id);
                                 log::info!("CPJA7DB_WORKER_REGISTER generation={generation} present_id={id}");
                             }
                             Ok(Command::Flush)=>flushing=true,
                             Ok(Command::Stop)|Err(TryRecvError::Disconnected)=>break 'worker,
                             Err(TryRecvError::Empty)=>break,
                         }
                     }
                     if pending.len()+ready.len()<2 && !flushing {
                         #[cfg(feature="gnu6-cpja7e-adaptive-scheduler")]
                         {
                             let t=Instant::now();
                             let result=commands.recv();
                             idle_us+=t.elapsed().as_micros() as u64;
                             idle_wakes+=1;
                             match result {
                                 Ok(command)=>staged=Some(command),
                                 Err(_)=>break 'worker,
                             }
                             continue;
                         }
                         #[cfg(not(feature="gnu6-cpja7e-adaptive-scheduler"))]
                         {
                             thread::sleep(Duration::from_micros(250));
                             continue;
                         }
                     }
                    // Newest-first is intentional: when two real Vulkan waits
                     // become ready, completion *observations* can be out of order.
                     // No synthetic ACKs, timers-as-success, or result fabrication.
                     let mut index=pending.len();
                     while index>0 {
                         index-=1;
                         let id=pending[index];
                         #[cfg(feature="gnu6-cpja7e-adaptive-scheduler")]
                         {wait_calls+=1;}
                         let result=unsafe {wait.wait_for_present(raw,id,0)};
                         match result {
                             Ok(())=>{
                                 pending.remove(index);
                                 sequence+=1;
                                 log::info!("CPJA7DB_WORKER_WAIT_SUCCESS generation={generation} present_id={id} observation={sequence}");
                                 ready.push(id);
                             }
                             Err(vk::Result::TIMEOUT)=>{
                                 #[cfg(feature="gnu6-cpja7e-adaptive-scheduler")]
                                 {timeouts+=1;}
                             }
                             Err(error)=>{
                                 log::error!("CPJA7DB_WORKER_WAIT_FAILED generation={generation} present_id={id} error={error:?}");
                                 let _=result_tx.send(Outcome::Fault{generation,id,error});
                                 break 'worker;
                             }
                         }
                     }
                     if ready.len()==2 || (flushing && pending.is_empty() && !ready.is_empty()){
                         ready.sort_unstable();
                         let ordered=ready.clone();
                         if ordered.len()==2 {
                             log::info!("CPJA7DB_DELIVERY_REORDERED generation={generation} old={} new={} proof=two_real_vk_wait_success",
                                 ordered[0],ordered[1]);
                         }
                         for id in ready.drain(..).rev(){
                             delivery+=1;
                             log::info!("CPJA7DB_WORKER_DELIVER generation={generation} present_id={id} arrival={delivery}");
                             if result_tx.send(Outcome::Ready{generation,id}).is_err(){break 'worker;}
                         }
                     }
                     #[cfg(feature="gnu6-cpja7e-adaptive-scheduler")]
                     {
                         polls+=1;
                         let t=Instant::now();
                         match commands.recv_timeout(Duration::from_micros(profile.cadence_us())) {
                             Ok(command)=>staged=Some(command),
                             Err(RecvTimeoutError::Timeout)=>{},
                             Err(RecvTimeoutError::Disconnected)=>break 'worker,
                         }
                         active_us+=t.elapsed().as_micros() as u64;
                     }
                     #[cfg(not(feature="gnu6-cpja7e-adaptive-scheduler"))]
                     thread::sleep(Duration::from_micros(250));
                 }
                 #[cfg(feature="gnu6-cpja7e-adaptive-scheduler")]
                 log::info!("CPJA7E_WORKER_METRICS generation={generation} profile={} cadence_us={} wait_calls={wait_calls} timeouts={timeouts} polls={polls} idle_wakes={idle_wakes} idle_block_us={idle_us} active_wait_us={active_us} successes={sequence} delivered={delivery} wall_us={} cpu_us={} pending_abandoned={} ready_abandoned={}",
                     profile.name(),profile.cadence_us(),begun.elapsed().as_micros(),
                     super::cpja7e_policy::thread_cpu_us().saturating_sub(cpu_before),
                     pending.len(),ready.len());
                 #[cfg(all(target_os="linux",feature="gnu6-cpja7eb-benchmark"))]
                 if let Some((voluntary,nonvoluntary))=super::cpja7e_policy::thread_context_switches(){
                     log::info!("CPJA7EB_WORKER_CTX generation={generation} voluntary={voluntary} nonvoluntary={nonvoluntary}");
                 }
                 log::info!("CPJA7DB_WORKER_STOP generation={generation} pending_discarded={} ready_unclaimed={}",
                     pending.len(),ready.len());
             })
             .map_err(|_|"CPJA7DB_WORKER_SPAWN_FAILED")?;
        Ok(Self {
            tx,
            results: Mutex::new(results),
            thread: Mutex::new(Some(thread)),
        })
    }
    pub(crate) fn submit(&self, id: u64) -> Result<(), &'static str> {
        self.tx
            .send(Command::Submit(id))
            .map_err(|_| "CPJA7DB_COLLECTOR_DISCONNECTED")
    }
    pub(crate) fn flush(&self) -> Result<(), &'static str> {
        self.tx
            .send(Command::Flush)
            .map_err(|_| "CPJA7DB_COLLECTOR_DISCONNECTED")
    }
    pub(crate) fn poll(&self) -> Option<Outcome> {
        self.results.lock().try_recv().ok()
    }
    pub(crate) fn receive(&self, timeout: Duration) -> Result<Outcome, &'static str> {
        self.results
            .lock()
            .recv_timeout(timeout)
            .map_err(|e| match e {
                RecvTimeoutError::Timeout => "CPJA7DB_COLLECTOR_TIMEOUT",
                RecvTimeoutError::Disconnected => "CPJA7DB_COLLECTOR_DISCONNECTED",
            })
    }
    pub(crate) fn stop(&self) {
        let _ = self.tx.send(Command::Stop);
        if let Some(join) = self.thread.lock().take() {
            if join.join().is_err() {
                log::error!("CPJA7DB_WORKER_PANIC_ON_JOIN");
            }
        }
    }
}
impl Drop for Collector {
    fn drop(&mut self) {
        self.stop();
    }
}
