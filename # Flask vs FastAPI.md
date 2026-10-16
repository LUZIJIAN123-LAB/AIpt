# Flask vs FastAPI

Flask 和 FastAPI 都是 Python 生态的主流 Web 框架，但定位不同。

## Flask

- 微框架，极简核心
- 灵活自由，社区插件丰富
- 适合小型项目或快速原型
- 同步框架，原生不支持 async

## FastAPI

- 现代高性能异步框架
- 自动生成 OpenAPI 文档和交互式 Swagger UI
- 基于 Pydantic 做类型校验
- 原生 async/await + type hints
- 性能接近 Node.js / Go

## 选型建议

- 小项目/脚本 → Flask
- 中大型 API 服务 → FastAPI
- 机器学习推理服务 → FastAPI（异步高并发）