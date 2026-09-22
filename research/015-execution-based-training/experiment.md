# Experiment 015

Create recovery states from mechanically known outcomes:
- missing target -> read current source;
- accepted no-op -> read current source;
- effective unverified mutation -> run tests;
- failed verification -> reacquire changed source.

Train M15 on Module 14 data plus these recovery states.

Evaluate BASE, M14, and M15 on the same held-out recovery instances. Primary metric: exact structured-action correctness.

## Training environment decision

Module 14 established that the initial 0.5B LoRA training configuration was
not operationally practical on the target CPU-only laptop.

Module 15 will therefore not attempt local CPU training before its primary
experiment.

If Module 14 produces sufficient evidence to justify proceeding with
execution-derived training, Module 15 training will use the same GPU-backed
training environment used for Module 14 where practical.

This is an execution-environment decision only.

The frozen Module 15 dataset construction, recovery targets, held-out
evaluation data, behavioral metrics, and BASE/M14/M15 comparison remain
unchanged.

Training hardware and deployment hardware will be reported separately.
