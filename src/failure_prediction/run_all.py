"""실행: python -m src.failure_prediction.run_all"""
import subprocess, sys, time

STEPS = [("data_pipeline", "step0_check"), ("data_pipeline", "step1_clean"),
         ("data_pipeline", "step2_features"), ("data_pipeline", "step3_labels"),
         ("failure_prediction", "step4_train_ml"),
         ("failure_prediction", "step5_train_dl"),
         ("failure_prediction", "step6_predict")]

for pkg, s in STEPS:
    print(f"\n{'='*66}\n▶ {s}\n{'='*66}")
    t = time.time()
    r = subprocess.run([sys.executable, "-m", f"src.{pkg}.{s}"])
    if r.returncode != 0:
        if s == "step5_train_dl":
            print("⚠️ 딥러닝 실패 → 머신러닝만으로 계속"); continue
        print(f"❌ {s} 실패"); sys.exit(1)
    print(f"✔ {s} ({time.time()-t:.0f}초)")
print("\n🎉 완료 → data/processed/predictions.csv")
