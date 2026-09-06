# 在 GPU 服务器复现 OctoTools + APC

本项目采用两个容器：`octotools` 负责规划、工具执行、APC 和 Jupyter；
`vllm` 独占 GPU，并通过 OpenAI 兼容接口提供模型服务。Jupyter 使用 8888
端口，vLLM 使用 8000 端口，二者不会冲突。

## 1. 验证服务器前置条件

服务器需要 Linux、NVIDIA 驱动、Docker Engine、Docker Compose v2 和
NVIDIA Container Toolkit。执行：

```bash
nvidia-smi
docker compose version
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

原因：宿主机能看到 GPU 不代表 Docker 已获得 GPU 权限；第三条命令同时验证
驱动和容器运行时。

## 2. 克隆论文实验分支

```bash
git clone --branch feature/apc-plan-cache \
  https://github.com/huangtingtingbushitingting/octotools.git
cd octotools
```

原因：该分支包含 APC 集成、证据门控、多尝试控制器、实验日志和 GPU 部署文件。

## 3. 创建私有配置

```bash
cp .env.template .env
cp .env.gpu.example .env.gpu
chmod 600 .env .env.gpu
```

编辑 `.env.gpu`：

- `VLLM_MODEL` 是 Hugging Face 模型名或服务器上的模型目录。
- `VLLM_SERVED_MODEL_NAME` 是 OctoTools 请求时使用的名字，通常与模型名一致。
- 多张 GPU 时，把 `VLLM_TENSOR_PARALLEL_SIZE` 改为实际使用的 GPU 数。
- 私有或受限模型才需要 `HF_TOKEN`。
- 必须修改 `JUPYTER_TOKEN`。

原因：`.env` 和 `.env.gpu` 已被 Git 忽略，密钥与服务器差异不会进入论文代码仓库。

## 4. 启动 GPU 服务

```bash
docker compose --env-file .env.gpu \
  -f compose.yaml -f compose.gpu.yaml up --build -d
```

检查状态：

```bash
docker compose --env-file .env.gpu \
  -f compose.yaml -f compose.gpu.yaml ps
docker logs -f octotools-vllm
curl http://localhost:8000/v1/models
```

原因：Compose 会先等待 vLLM 健康，再启动依赖它的 OctoTools，避免模型仍在加载时
实验立即失败。首次启动会下载模型，耗时取决于模型大小和网络速度。

## 5. 验证代码和模型连接

```bash
docker exec octotools python -m pytest tests -q
docker exec octotools python -c \
  "import os; from openai import OpenAI; c=OpenAI(base_url=os.environ['VLLM_BASE_URL'], api_key=os.environ['VLLM_API_KEY']); print([m.id for m in c.models.list().data])"
```

原因：第一条验证算法模块没有回归；第二条单独验证容器网络、服务地址和模型名，
能把部署问题与 OctoTools 规划问题分开定位。

## 6. 运行一条可复现实验

```bash
docker exec octotools python -m octotools.research.experiment \
  --group C1 \
  --model "vllm-Qwen/Qwen2.5-7B-Instruct" \
  --tools generalist_solution_generator \
  --query "What is 12 plus 12?" \
  --expected-answer "24" \
  --total-steps 12 \
  --steps-per-attempt 4 \
  --output experiment_runs/smoke.jsonl
```

原因：`C1` 同时开启跨尝试证据和失败记忆、APC Assist 和证据门控；JSONL 会保存
配置、全部轨迹、缓存状态、总预算和按组件划分的模型调用统计。token 数当前标记为
`estimated_from_text`，只能作为统一估计，不能冒充服务商精确计费数据。

## 7. 按实验组运行消融

保持 query、模型、工具、总步骤和时间完全一致，只修改 `--group`：

```bash
for group in B0 B1 M1 M2 P0 P1 C1; do
  docker exec octotools python -m octotools.research.experiment \
    --group "$group" \
    --model "vllm-Qwen/Qwen2.5-7B-Instruct" \
    --tools generalist_solution_generator \
    --query "What is 12 plus 12?" \
    --expected-answer "24" \
    --total-steps 12 \
    --steps-per-attempt 4 \
    --output experiment_runs/ablation.jsonl
done
```

原因：固定总预算后，改进才可归因于记忆或计划门控，而不是某一组获得了更多
工具步骤。正式实验还应使用固定数据集、随机种子、重复运行和置信区间。

## 8. 连接服务器上已有的 vLLM（可选）

如果管理员已经提供 OpenAI 兼容地址，不启动 `compose.gpu.yaml`。在 `.env` 中设置：

```dotenv
VLLM_BASE_URL=http://model-server:8000/v1
VLLM_API_KEY=dummy-token
OCTOTOOLS_MODEL=vllm-server-model-id
```

然后只启动应用：

```bash
docker compose up --build -d octotools
```

原因：这种模式不会重复占用 GPU，也适合学校共享集群。若网关不支持 `/v1/models`，
可显式设置 `VLLM_SKIP_MODEL_CHECK=1`，但仍应先用一次真实 completion 验证地址。

## 9. 常见问题

- CUDA out of memory：换更小模型、降低 `VLLM_GPU_MEMORY_UTILIZATION`，或增加张量并行 GPU 数。
- 模型名不匹配：以 `curl http://localhost:8000/v1/models` 返回的 `id` 为准。
- Hugging Face 下载失败：配置服务器代理或预先把模型放到本地目录，再修改 `VLLM_MODEL`。
- Jupyter 无法访问：确认防火墙开放 `JUPYTER_PORT`；公网服务器建议使用 SSH 隧道。
- APC 本地源码联调：额外叠加 `-f compose.apc.yaml` 并设置 `APC_SOURCE_DIR`。正常复现不需要该挂载，因为依赖已固定到 APC commit。
