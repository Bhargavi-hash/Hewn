from __future__ import annotations
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PY=sys.executable
M14=ROOT/"research/014-tool-using-model"; M15=ROOT/"research/015-execution-based-training"
MODEL="Qwen/Qwen2.5-Coder-0.5B-Instruct"
def run(*x): print("+",PY,*x,flush=True); subprocess.run([PY,*x],cwd=ROOT,check=True)
def prepare():
    run(str(M14/"build_dataset.py")); run(str(M15/"build_data.py"))
def train():
    run(str(M14/"train_lora.py"),"--model",MODEL,"--train",str(M14/"data/train.jsonl"),"--out",str(M14/"checkpoints/m14-lora"))
    run(str(M14/"train_lora.py"),"--model",MODEL,"--train",str(M15/"data/train.jsonl"),"--out",str(M15/"checkpoints/m15-lora"))
def ev(script,data,out,adapter=None):
    x=[str(script),"--model",MODEL,"--eval",str(data),"--out",str(out)]
    if adapter: x += ["--adapter",str(adapter)]
    run(*x)
def evaluate():
    e=M14/"evaluate.py"; d=M14/"data/eval.jsonl"
    ev(e,d,M14/"results/base.json"); ev(e,d,M14/"results/m14.json",M14/"checkpoints/m14-lora")
    d=M15/"data/eval.jsonl"
    ev(e,d,M15/"results/base.json"); ev(e,d,M15/"results/m14.json",M14/"checkpoints/m14-lora"); ev(e,d,M15/"results/m15.json",M15/"checkpoints/m15-lora")
    run(str(M15/"compare.py"),"--base",str(M15/"results/base.json"),"--m14",str(M15/"results/m14.json"),"--m15",str(M15/"results/m15.json"),"--out",str(M15/"results/comparison.json"))
def validate():
    prepare()
    for p in (M14/"build_dataset.py",M14/"train_lora.py",M14/"evaluate.py",M15/"build_data.py",M15/"compare.py",Path(__file__).resolve()): run("-m","py_compile",str(p))
    print("Modules 14/15 validation passed.")
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--stage",choices=("validate","prepare","train","evaluate","all"),required=True); s=ap.parse_args().stage
    if s=="validate": validate()
    elif s=="prepare": prepare()
    elif s=="train": train()
    elif s=="evaluate": evaluate()
    else: validate(); train(); evaluate()
if __name__=="__main__": main()
