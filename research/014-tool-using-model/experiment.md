# Experiment 014

Train on four families: read-before-edit, missing-target recovery, grounded replacement, and verify-after-edit.

Evaluate on held-out families: search-after-rejection and completion-after-verification.

Primary metric: exact structured-action correctness.
Diagnostics: JSON validity and action-name correctness.

Default model: `Qwen/Qwen2.5-Coder-0.5B-Instruct`, chosen because the reference machine is CPU-only with about 8 GiB RAM. This is a feasibility model, not the final Hewn model.


## Local training feasibility observation

Before the primary Module 14 training run, the frozen training pipeline was
attempted on the same CPU-only laptop used for Hewn's local inference
experiments.

### Attempted configuration

- model: Qwen2.5-Coder-0.5B-Instruct
- training method: LoRA supervised fine-tuning
- epochs: 1
- training examples: 96
- hardware: Intel Core i5-10210U
- system memory: approximately 7.6 GiB RAM
- accelerator: none
- operating mode: local CPU training

The training command was:

    python research/014-tool-using-model/train_lora.py \
      --model Qwen/Qwen2.5-Coder-0.5B-Instruct \
      --train research/014-tool-using-model/data/train.jsonl \
      --out research/014-tool-using-model/checkpoints/m14-lora \
      --epochs 1

### Observed result

The attempt caused severe workstation-level resource pressure during
training. The interactive editor became unresponsive and terminated.

After recovery:

- no Module 14 training process remained;
- approximately 3.6 GiB of system memory was available;
- approximately 806 MiB of swap remained in use;
- inspected kernel logs did not identify a specific process killed by the
  kernel OOM killer.

The precise termination mechanism was therefore not established.

This observation is classified as an operational training-feasibility
failure on the target laptop. It must not be described as a confirmed
kernel OOM event.

### Experimental decision

Do not repeat the same local training attempt.

The frozen Module 14 dataset, held-out evaluation split, training objective,
and behavioral evaluation protocol remain unchanged.

The training environment will move to GPU-backed hardware. This changes the
training hardware but does not change the research question about whether
tool-use specialization improves the model's behavior.

The resulting adapter/model will subsequently be evaluated using the frozen
Module 14 evaluation set. Local deployment feasibility remains a separate
question from training feasibility.

### Interpretation

Local inference feasibility does not imply local fine-tuning feasibility.

For Hewn, inexpensive local deployment is a product requirement. Training the specialized model on the deployment machine is not.

Training hardware and deployment hardware must therefore be recorded as separate provenance.
