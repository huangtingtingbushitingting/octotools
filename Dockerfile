FROM python:3.10-slim

WORKDIR /workspace/octotools

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md requirements.txt ./
COPY octotools ./octotools

RUN grep -vE '^(vllm|#|$)' requirements.txt > /tmp/requirements-docker.txt \
    && pip install --upgrade pip \
    && pip install -r /tmp/requirements-docker.txt \
    && pip install --no-deps -e . \
    && pip install jupyterlab ipykernel

EXPOSE 8888

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--NotebookApp.token=octotools"]