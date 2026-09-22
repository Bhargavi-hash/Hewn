from __future__ import annotations
import argparse, json
from pathlib import Path

SYSTEM = """You are Hewn's action model. Return exactly one JSON object and no prose.
Allowed actions are read_file, search_text, replace_text, run_check, and final.
Never invent tool results."""

def tool(name: str, **arguments: str) -> str:
    return json.dumps({"type":"tool","name":name,"arguments":arguments}, separators=(",",":"))

def final(text: str) -> str:
    return json.dumps({"type":"final","text":text}, separators=(",",":"))

def rows(family: str, n: int):
    out=[]
    for i in range(n):
        p=f"src/sample_{i}.py"; s=f"normalize_{i}"
        old=f"def {s}(value: str) -> str:\\n    return value.strip()"
        new=f"def {s}(value: str) -> str:\\n    return value.strip().lower()"
        if family=="read_before_edit":
            q=f"Change `{s}` in {p}. No source has been read yet."; a=tool("read_file",path=p)
        elif family=="missing_target_recovery":
            q=f"A replace_text on {p} failed because its target was absent. Reacquire evidence."; a=tool("read_file",path=p)
        elif family=="grounded_edit":
            q=f"Normalize names to lowercase. Current source in {p}:\\n{old}\\nMake the grounded edit."; a=tool("replace_text",path=p,old=old,new=new)
        elif family=="verify_after_edit":
            q=f"An effective mutation changed {p}. No verification has run after it."; a=tool("run_check",check="tests")
        elif family=="search_after_rejection":
            q=f"The expected path for `{s}` was wrong and replacement failed. Select the next evidence action."; a=tool("search_text",query=s)
        elif family=="completion_after_verification":
            q=f"The requested mutation to {p} was effective and required tests passed afterward."; a=final("Implemented the requested change and verified the tests.")
        else: raise ValueError(family)
        out.append({"family":family,"system":SYSTEM,"prompt":q,"target":a})
    return out

def write(path: Path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in data),encoding="utf-8")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",type=Path,default=Path("research/014-tool-using-model/data"))
    a=ap.parse_args()
    train_f=("read_before_edit","missing_target_recovery","grounded_edit","verify_after_edit")
    eval_f=("search_after_rejection","completion_after_verification")
    train=sum((rows(f,24) for f in train_f),[]); ev=sum((rows(f,12) for f in eval_f),[])
    write(a.out/"train.jsonl",train); write(a.out/"eval.jsonl",ev)
    (a.out/"manifest.json").write_text(json.dumps({"train_families":train_f,"eval_families":eval_f,"train_rows":len(train),"eval_rows":len(ev),"isolation":"template-family"},indent=2)+"\n")
    print(f"train={len(train)} eval={len(ev)}")
if __name__=="__main__": main()
