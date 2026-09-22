from __future__ import annotations
import argparse,json
from pathlib import Path
def main():
    ap=argparse.ArgumentParser()
    for x in ("base","m14","m15"): ap.add_argument(f"--{x}",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    rows=[]
    for label,path in (("BASE",a.base),("M14",a.m14),("M15",a.m15)):
        d=json.loads(path.read_text()); rows.append({"condition":label,"valid_json_rate":d["valid_json_rate"],"action_correct_rate":d["action_correct_rate"],"exact_action_rate":d["exact_action_rate"],"wall_seconds":d["wall_seconds"]})
    result={"primary_metric":"exact_action_rate","comparison":rows,"nonclaim":"This does not measure repository-level coding capability."}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2))
if __name__=="__main__": main()
