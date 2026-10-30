//! Optional machine-readable event trace (JSON lines), flushed per event so an
//! external harness can follow a live session. Disabled unless `--trace` is given.

use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::Path;
use std::time::Instant;

use serde_json::{Map, Value};

pub struct Trace {
    out: Option<BufWriter<File>>,
    t0: Instant,
}

impl Trace {
    pub fn open(path: Option<&Path>) -> io::Result<Self> {
        let out = match path {
            Some(p) => Some(BufWriter::new(File::create(p)?)),
            None => None,
        };
        Ok(Self { out, t0: Instant::now() })
    }

    pub fn emit(&mut self, event: &str, fields: Value) {
        let Some(out) = self.out.as_mut() else { return };
        let mut m = Map::new();
        m.insert("t_ms".into(), Value::from(self.t0.elapsed().as_secs_f64() * 1e3));
        m.insert("event".into(), Value::from(event));
        if let Value::Object(f) = fields {
            m.extend(f);
        }
        let ok = serde_json::to_writer(&mut *out, &Value::Object(m)).is_ok()
            && out.write_all(b"\n").is_ok()
            && out.flush().is_ok();
        if !ok {
            log::warn!("trace write failed; disabling trace");
            self.out = None;
        }
    }
}
