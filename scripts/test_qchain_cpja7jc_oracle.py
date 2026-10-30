import shutil,tempfile
from pathlib import Path
from qchain_cpja7jc_compute_oracle import verify
R=Path("/mnt/workbench/evidence/runs/qchain-cpja7jc-20261012-01/runs/f4-sixpass-1200")
def reject(name,mut):
    with tempfile.TemporaryDirectory(prefix="cpja7jc-attack-") as d:
        q=Path(d);(q/"engine-ledger").mkdir()
        shutil.copy2(R/"f4-compute-query.bin",q/"f4-compute-query.bin")
        shutil.copy2(R/"engine-ledger/engine.stderr",q/"engine-ledger/engine.stderr")
        mut(q)
        try:verify(q)
        except (AssertionError,ValueError,RuntimeError,FileNotFoundError) as err:
            print("CPJA7JC_ADVERSARY_REJECTED",name,str(err)[:70],flush=True)
            return
        raise AssertionError("FALSE_ACCEPT_"+name)
def edit(q,old,new):
    p=q/"engine-ledger/engine.stderr";s=p.read_text()
    assert old in s
    p.write_text(s.replace(old,new,1))
def main():
    assert verify(R)["frames"]==1200
    reject("missing_raw",lambda q:(q/"f4-compute-query.bin").unlink())
    reject("truncated_raw",lambda q:(q/"f4-compute-query.bin").write_bytes((q/"f4-compute-query.bin").read_bytes()[:-8]))
    reject("zero_ticks",lambda q:(q/"f4-compute-query.bin").write_bytes(bytes(16)+(q/"f4-compute-query.bin").read_bytes()[16:]))
    reject("missing_kernel",lambda q:edit(q,"CPJA7JC_F4_KERNEL_TIMING seq=0","CPJA7JC_BAD_KERNEL seq=0"))
    reject("fake_period",lambda q:edit(q,"seq=0 period_ns=1","seq=0 period_ns=2"))
    reject("fake_duration",lambda q:edit(q,"f2_ns=","f2_ns=999999 bogus="))
    reject("wrong_device",lambda q:edit(q,"frames=1200 device=1","frames=1200 device=2"))
    reject("missing_completion",lambda q:edit(q,"CPJA7JC_F4_QUERY_STREAM_COMPLETE","CPJA7JC_NOT_COMPLETE"))
    print("CPJA7JC_ADVERSARIAL_8_OF_8_PASS",flush=True)
if __name__=="__main__":main()
