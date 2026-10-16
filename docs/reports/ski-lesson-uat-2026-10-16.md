# 冬季滑雪教学真实工作流 UAT（2026-10-16）

> 实现基线：`78a99ac`，其后补充隔离脚本与 FFmpeg 假成功修复
> Provider：Qwen Image 3.0 / Wan3.0 Video Prime / imageio-ffmpeg 7.1
> 数据目录：`data/uat/20261016-100634-ski-lesson/`（媒体与 UAT DB 不入库）

## 技术链路

隔离命令：

```powershell
python scripts/run_ski_lesson.py
```

编译得到 8 个任务，真实执行结果：2 张 1280×720 PNG、2 段 3 秒/480P MP4，以及用 FFmpeg 对已有片段重试生成的 6.06 秒合成 MP4。两次付费视频调用均成功，external job ID 已保存在隔离 UAT DB 中。

| 产物 | 字节数 | SHA-256 |
|---|---:|---|
| `images/img-8638f570.png` | 1,135,322 | `C15983073ACDC89CA8848C9D85916A6A6826136ACBE10BD371DABC31AFF1A00A` |
| `images/img-2793e7e0.png` | 1,290,286 | `9D9CF5297B83745ACE6713F708B0C61E42B88D917E5E7B59C1A2A071CE0339AA` |
| `videos/vid-f7a9e500.mp4` | 2,575,573 | `D277457751CF59727CFFC4B2D35672F89B0384E892E592FEBA5DF351318FBE4B` |
| `videos/vid-9a3f391f.mp4` | 3,432,244 | `C03290F627A0E7F259B0350B2227054CF7203E80632A3675179669CFBA924C1D` |
| `final/final-4ca89bd1.mp4` | 6,004,312 | `5B928AB657AC044D7B7D9139C387189C4B63B508E3B3C3C88786A29F119FD39A` |

合成片经 FFmpeg 全帧解码通过：H.264、854×480、约 29.91 fps、时长 6.06 秒。

## 发现并关闭的工程缺陷

首次执行时，环境缺 FFmpeg，`RealVideoConcatHandler` 却登记 0 字节资产并返回成功。此次已完成：

- 将 `imageio-ffmpeg==0.6.0` 纳入 constraints；
- 真实 concat 缺输入、缺 FFmpeg、FFmpeg 错误均返回失败，不再生成 synthetic asset；
- `run_ski_lesson.py` 使用隔离 UAT DB/资产目录，不再删除默认开发数据库；
- 新增 `--images-only` 人工内容门禁，不合格图片不会继续产生视频费用。

## 内容硬约束人工验收

三批共 6 张候选图均检查了：人物数量、左右位置、教练手势、单板数量、学员前/后脚固定关系、背景人物和写实质量。

| 条目 | 结果 |
|---|---|
| 仅两人、教练左/学员右、晴天雪场、写实 | 通过 |
| 教练半蹲并指向学员固定器 | 多数候选通过 |
| 每人恰好一块单板 | 后两批通过，首批存在板关系含混 |
| 学员仅前脚固定、后脚明确踩雪、空后固定器可见 | **未通过**；模型持续把两脚放在板上或无法清晰显示踩雪后脚 |
| 背景无其他人 | 通过（缆车载客不作为雪道背景人物，但严格产品规则可继续收紧） |

结论：**技术工作流通过，内容 UAT 不通过**。这是 Qwen Image 对精细装备/肢体空间关系的随机遵循问题；系统已在视频调用前提供 images-only 人工门禁，避免把不合格首帧继续送往付费视频。若必须关闭内容验收，需要人工选片、局部重绘/ControlNet，或更换在固定器姿态上可验证的模型，不得把当前候选伪标为合格。

按系统单位成本估算：完整技术批次 2 image + 2 video 约 USD 0.48；随后两个 images-only 候选批次共 4 image 约 USD 0.16。实际账单以供应商控制台为准。
