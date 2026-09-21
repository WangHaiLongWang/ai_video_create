# Doubao Seedream / Seedance 2.5 UAT 报告

> 日期：2026-09-21
> 代码基线：工作区（基于 `b01e63e`，包含未提交 Doubao Provider 变更）
> 环境：Windows / Python 3.12.3 / 火山方舟北京地域

## 结论

状态：**External Blocked**。

API Key 认证和模型目录访问成功，Provider 离线契约通过；真实媒体生成被账号模型激活状态阻断。

## 验证记录

| 操作 | 结果 |
|---|---|
| Provider health/catalog | 成功 |
| 模型目录查询 | 成功 |
| Seedream 生图 | HTTP 404：账号未激活模型服务 |
| Seedance 2.5 文生视频 | HTTP 404：账号未激活模型服务 |
| Seedance 图生视频 | 未执行；上游图像和视频权限均阻断 |

确认的模型 ID：

```text
doubao-seedream-5-0-pro-260628
doubao-seedance-2-5-260628
```

早期默认短名称已校准为当前目录中的正式版本 ID。

## 自动测试

```text
Doubao Provider + Config API: 16 passed
All provider tests:           43 passed
Frontend typecheck:           passed
Frontend production build:    passed
Python compileall:             passed
```

## 资产与费用

- 未生成图片；
- 未创建成功视频任务；
- 未保存媒体文件；
- 没有可确认的成功生成费用。

报告不记录 API Key、账号编号、请求 ID或签名 URL。

## 下一步

在方舟控制台激活模型服务或创建推理 Endpoint，更新 `.env`，然后按 [`DOUBAO-SEEDANCE-PLAN.md`](../plans/active/DOUBAO-SEEDANCE-PLAN.md) 重新执行 UAT-002 至 UAT-004。
