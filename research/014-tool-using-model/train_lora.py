from __future__ import annotations
import argparse, json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model",default="Qwen/Qwen2.5-Coder-0.5B-Instruct")
    ap.add_argument("--train",type=Path,required=True); ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--epochs",type=float,default=1.0); a=ap.parse_args()
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig,get_peft_model
        from transformers import AutoModelForCausalLM,AutoTokenizer,Trainer,TrainingArguments
    except ImportError as e:
        raise SystemExit("Install: uv pip install torch transformers datasets peft accelerate") from e
    rows=[json.loads(x) for x in a.train.read_text().splitlines() if x.strip()]
    tok=AutoTokenizer.from_pretrained(a.model); tok.pad_token=tok.pad_token or tok.eos_token
    texts=[]
    for r in rows:
        msgs=[{"role":"system","content":r["system"]},{"role":"user","content":r["prompt"]},{"role":"assistant","content":r["target"]}]
        texts.append(tok.apply_chat_template(msgs,tokenize=False,add_generation_prompt=False))
    ds=Dataset.from_dict({"text":texts})
    def enc(batch):
        z=tok(batch["text"],truncation=True,max_length=384,padding="max_length")
        z["labels"]=[[t if m else -100 for t,m in zip(ids,mask)] for ids,mask in zip(z["input_ids"],z["attention_mask"])]
        return z
    ds=ds.map(enc,batched=True,remove_columns=["text"])
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        a.model,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
    )
    model.config.use_cache=False
    model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=.05,bias="none",task_type="CAUSAL_LM",target_modules=["q_proj","k_proj","v_proj","o_proj"]))
    a.out.mkdir(parents=True,exist_ok=True)
    ta = TrainingArguments(
        output_dir=str(a.out),
        num_train_epochs=a.epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        logging_steps=2,
        save_strategy="epoch",
        report_to=[],
        use_cpu=not torch.cuda.is_available(),
        fp16=torch.cuda.is_available(),
        dataloader_num_workers=0,
    )

    trainer = Trainer(
        model=model,
        args=ta,
        train_dataset=ds,
    )
    result = trainer.train()

    model.save_pretrained(a.out)
    tok.save_pretrained(a.out)

    (a.out / "training_result.json").write_text(
        json.dumps(
            {
                "base_model": a.model,
                "rows": len(rows),
                "epochs": a.epochs,
                "loss": result.training_loss,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()