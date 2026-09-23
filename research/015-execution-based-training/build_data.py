from __future__ import annotations
import argparse,json,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
m14=runpy.run_path(str(ROOT/"research/014-tool-using-model/build_dataset.py"))
SYSTEM=m14["SYSTEM"]; tool=m14["tool"]

def recovery(n,heldout=False):
    out=[]; prefix="heldout_recovery" if heldout else "recovery"
    for i in range(n):
        p=f"src/{prefix}_{i}.py"; s=f"clean_{i}"
        cases=[
          ("missing_target",f"replace_text on {p} failed because target text was absent. Task concerns `{s}`. Reacquire current source.",tool("read_file",path=p)),
          ("noop_edit",f"replace_text on {p} was accepted but repository bytes did not change. Reacquire current source before another edit.",tool("read_file",path=p)),
          ("unverified_mutation",f"An effective mutation changed {p}. No verification has run afterward.",tool("run_check",check="tests")),
          ("failed_verification",f"Tests failed after changing {p}. Do not complete. Reacquire the changed source before repair.",tool("read_file",path=p))]
        out += [{"family":f,"system":SYSTEM,"prompt":q,"target":a} for f,q,a in cases]
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--m14",type=Path,default=ROOT/"research/014-tool-using-model/data/train.jsonl"); ap.add_argument("--out",type=Path,default=ROOT/"research/015-execution-based-training/data")
    a=ap.parse_args(); base=[json.loads(x) for x in a.m14.read_text().splitlines() if x.strip()]
    train=base+recovery(24); ev=recovery(8,True); a.out.mkdir(parents=True,exist_ok=True)
    for name,data in (("train.jsonl",train),("eval.jsonl",ev)):
        (a.out/name).write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in data))
    (a.out/"manifest.json").write_text(json.dumps({"m14_rows":len(base),"recovery_rows":len(train)-len(base),"eval_rows":len(ev),"label_source":"deterministic mechanical recovery rule"},indent=2)+"\n")
    print(f"train={len(train)} eval={len(ev)}")
if __name__=="__main__": main()
