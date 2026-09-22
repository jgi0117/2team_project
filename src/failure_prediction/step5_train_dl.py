"""
실행: python -m src.failure_prediction.step5_train_dl
torch 없으면 건너뛰어도 됨 (머신러닝만으로 전체 파이프라인 동작).

구조
   30일 센서 흐름 ──GRU──┐
                        ├─→ (부품 × 기간) 전부를 한 번에 답한다
   나이·경과일 등  ──MLP──┘

★ 핵심 트릭 — 확률 대신 '위험률'을 내놓게 한다
   기간별 확률을 따로 내면 42일 확률 < 7일 확률 같은 모순이 생긴다.
   그래서 구간마다 '새로 생기는 위험'(항상 0 이상)을 내놓고 누적시킨다.
   누적값은 절대 줄어들 수 없으므로 계단이 항상 올라간다.
   그 누적 곡선 자체가 '언제쯤 터지나'의 답이다 → 별도 모델이 필요 없다.
"""
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from src.common.paths import WORK, MODELS
from src.common.contract import *

torch.manual_seed(SEED); np.random.seed(SEED)
dev = "cuda" if torch.cuda.is_available() else "cpu"
print(f"장치: {dev}")

z = np.load(WORK / "seq_bundle.npz", allow_pickle=True)
cube, rowm, rowd = z["cube"], z["rowm"], z["rowd"]
static, Y, M = z["static"], z["y"], z["mask"]
asof = pd.to_datetime(z["asof"], unit="D")
nC, nH = len(COMPONENTS), len(HORIZONS)

valid = rowd >= LOOKBACK - 1
tr_all = np.where(valid & (asof <= TRAIN_END - pd.Timedelta(days=max(HORIZONS))))[0]
te_i = np.where(valid & (asof >= TEST_START))[0]
split = int(len(tr_all) * 0.85)
tr_i, va_i = tr_all[:split], tr_all[split:]
print(f"학습 {len(tr_i):,} / 검증 {len(va_i):,} / 시험 {len(te_i):,}")

# 정규화 기준은 학습 구간에서만 (시험 데이터를 엿보면 안 됨)
lim = int(rowd[tr_i].max()) + 1
flat = cube[:, :lim].reshape(-1, cube.shape[2])
mu_s, sd_s = flat.mean(0), flat.std(0) + 1e-6
mu_t, sd_t = static[tr_i].mean(0), static[tr_i].std(0) + 1e-6


class DS(torch.utils.data.Dataset):
    def __init__(self, idx): self.idx = idx
    def __len__(self): return len(self.idx)
    def __getitem__(self, k):
        i = self.idx[k]
        seq = cube[rowm[i], rowd[i] - LOOKBACK + 1: rowd[i] + 1]
        return (torch.from_numpy((seq - mu_s) / sd_s).float(),
                torch.from_numpy((static[i] - mu_t) / sd_t).float(),
                torch.from_numpy(Y[i]), torch.from_numpy(M[i]))


class Net(nn.Module):
    def __init__(self, ns, nt):
        super().__init__()
        self.gru = nn.GRU(ns, 64, batch_first=True)
        self.mlp = nn.Sequential(nn.Linear(nt, 64), nn.ReLU(), nn.Dropout(0.2))
        self.head = nn.Sequential(nn.Linear(128, 128), nn.ReLU(), nn.Dropout(0.2),
                                  nn.Linear(128, nC * nH))

    def forward(self, seq, st):
        h = self.gru(seq)[0][:, -1]
        z = self.head(torch.cat([h, self.mlp(st)], 1)).view(-1, nC, nH)
        haz = nn.functional.softplus(z)          # ★ 위험은 항상 0 이상
        cum = torch.cumsum(haz, dim=2)           # ★ 누적하면 절대 안 내려감
        return (1 - torch.exp(-cum)).clamp(1e-6, 1 - 1e-6).reshape(-1, nC * nH)


net = Net(cube.shape[2], static.shape[1]).to(dev)
opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-4)
# 고장이 드물어 그냥 두면 "전부 안 터진다"고 답한다 → 양성에 가중치
pw = torch.tensor(((M[tr_i].sum(0) - Y[tr_i].sum(0)) / np.maximum(Y[tr_i].sum(0), 1))
                  .clip(1, 20), dtype=torch.float32, device=dev)

ld = lambda i, sh: torch.utils.data.DataLoader(DS(i), batch_size=256, shuffle=sh)
tl, vl = ld(tr_i, True), ld(va_i, False)
best, wait = 1e9, 0

for ep in range(40):
    net.train(); tot = 0.0
    for seq, st, y, m in tl:
        seq, st, y, m = [t.to(dev) for t in (seq, st, y, m)]
        p = net(seq, st)
        loss = (-(pw * y * torch.log(p) + (1 - y) * torch.log(1 - p)) * m).sum() / m.sum()
        opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
        tot += loss.item() * len(y)
    net.eval(); v = 0.0
    with torch.no_grad():
        for seq, st, y, m in vl:
            seq, st, y, m = [t.to(dev) for t in (seq, st, y, m)]
            p = net(seq, st)
            v += ((-(y * torch.log(p) + (1 - y) * torch.log(1 - p)) * m).sum()
                  / m.sum()).item() * len(y)
    v /= max(len(va_i), 1)
    star = "  ★" if v < best - 1e-4 else ""
    print(f"  ep{ep:02d}  train {tot/len(tr_i):.4f}  valid {v:.4f}{star}")
    if v < best - 1e-4:
        best, wait = v, 0
        torch.save({"state": net.state_dict(), "mu_s": mu_s, "sd_s": sd_s,
                    "mu_t": mu_t, "sd_t": sd_t, "version": MODEL_VERSION},
                   MODELS / "dl_multihorizon.pt")
    else:
        wait += 1
        if wait >= 6:
            print("  조기 종료"); break

_ck = torch.load(MODELS / "dl_multihorizon.pt", weights_only=False)
net.load_state_dict(_ck["state"]); net.eval()

out = []
with torch.no_grad():
    for seq, st, _, _ in ld(te_i, False):
        out.append(net(seq.to(dev), st.to(dev)).cpu().numpy())
S = np.vstack(out)

met, preds = [], []
for ci, c in enumerate(COMPONENTS):
    for hi, H in enumerate(HORIZONS):
        k = ci * nH + hi
        sel = M[te_i, k] == 1
        yt, sc = Y[te_i, k][sel], S[sel, k]
        if yt.sum() < 5:
            continue
        auc = roc_auc_score(yt, sc)
        met.append({COL_VER: MODEL_VERSION, COL_COMP: c, COL_H: H, "split": "test",
                    "metric": "auc", "value": round(auc, 4), "source": "dl"})
        preds.append(pd.DataFrame({COL_MACHINE: z["machine"][te_i][sel], COL_COMP: c,
                                   COL_ASOF: asof[te_i][sel], COL_H: H,
                                   COL_P: sc, COL_Y: yt, "source": "dl"}))
        print(f"  {c} {H:>2}일  AUC {auc:.3f}  고장률 {yt.mean():5.1%}")

pd.DataFrame(met).to_csv(WORK / "metrics_dl.csv", index=False)
pd.concat(preds).to_parquet(WORK / "pred_dl.parquet", index=False)
print("✅ 딥러닝 완료")
