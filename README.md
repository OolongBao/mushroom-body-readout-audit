# Mushroom-body readout audit

**对既有蘑菇体模型的权重—响应传递与测量盲区审计**

This is a portable, standard-library-only **saved-data reanalysis**, not a new fly brain model or a native simulation runner. 本仓库公开一个既有 IncentiveCircuit 模型实验的完整终点表、统计复核代码和简洁技术报告，保留负结果与适用边界。

## Quick start / 快速复核

需要 Python 3.11 或更新版本；已实测 3.11.9，无第三方依赖。下载或克隆后，在仓库根目录运行：

```text
python -B audit_saved.py
python -B -m unittest discover -s . -p test_audit_saved.py -v
```

第一条命令只读 `data/`，在标准输出给出 JSON；成功退出 0，损坏/缺失/不一致则非零退出。脚本按自身位置定位数据，可从其他工作目录调用。它不联网、不导入作者模型、不生成新种子、不训练，也不写结果文件。

## What is included / 内容

- `audit_saved.py`、`test_audit_saved.py`：独立复算误差、完整网格、逐格统计和拒绝路径。
- `data/`：原样保存的 measurements、predictions、statistics 和 cold_evidence 四份 JSON，共 1,099,939 bytes。
- [REPORT.md](REPORT.md)：方法、主辅结果、负结果与限制。
- [PROVENANCE.json](PROVENANCE.json)、[manifest.json](manifest.json)：来源、原字节摘要及核对范围。
- [verification.json](verification.json)：本发布版本实际验收记录。
- [RIGHTS.md](RIGHTS.md)：权利和第三方来源说明。

数据含 16 个共同种子块 × 4 个固定映射＝64 任务，主、辅终点各 32 格，每格 n=16，总共 1024 行。重复条件不能当作额外独立样本。[C1：data/measurements.json、data/predictions.json]

主要结果：R1 的主终点全网格平均绝对误差约 0.0174，简单稳态基线约 0.000917；本批不支持 R1 的整体优势。弱探针也并非普遍改善分辨能力。[C2/C3：data/statistics.json；详见 REPORT]

## Scope / 不包含什么

本包仅复现**保存测量和预测到汇总统计**，不是重新运行原实验、重新生成预测、原生轨迹逐点复现或论文全部曲线复现。predictions 中的 frozen 路径/摘要为历史来源标识；对应状态与完整轨迹未随包分发。不能从这些引用恢复原模拟。

不包含早期连接组工程、旧 Git 历史、运行环境、实验启动授权或所有历史实验。不存在对生物记忆新机制、旧痕迹恢复、全脑模型或跨模型泛化的证明。`scientific_pass=false`、`human_verification=PENDING`、`submission_ready=false`；技术复核不代替人类科学审核。This is a technical resource, not a peer-reviewed paper.

## Source and assistance

Underlying model: Gkanias, E., McCurdy, L. Y., Nitabach, M. N., & Webb, B. (2022). *An incentive circuit for memory dynamics in the mushroom body of Drosophila melanogaster*. eLife 11:e75611. [DOI](https://doi.org/10.7554/eLife.75611). [Author repository at the recorded commit](https://github.com/InsectRobotics/IncentiveCircuit/tree/1610c80072fe8bb59bd397e7a61f716393a509b9). The author model is not bundled here.

AI tools assisted code preparation, checks and documentation; these checks do not constitute human authorship approval or biological validation. Scientific-writing procedures helped separate evidence, interpretation and unresolved claims. Procedural reference (not fly evidence): Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. [DOI](https://doi.org/10.48550/arXiv.2609.00065). Official metadata checked 2026-10-23 (current revision v2).
