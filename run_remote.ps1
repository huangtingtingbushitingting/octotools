param(
    [string]$ServerIp = "10.21.76.112",
    [int]$Port = 8000,
    [string]$ModelName = "codev-r1"
)

$ErrorActionPreference = "Stop"

Set-Location "D:\octotools"

$env:VLLM_BASE_URL = "http://${ServerIp}:${Port}/v1"
$env:VLLM_API_KEY = "dummy-token"

Write-Host "vLLM address: $env:VLLM_BASE_URL"
Write-Host "Checking vLLM server..."

curl.exe --fail "$env:VLLM_BASE_URL/models"

Write-Host ""
Write-Host "Generating Verilog..."

python -m octotools.verilog.cli generate `
    --model "vllm-$ModelName" `
    --spec-file "problems\mux.txt" `
    --testbench "problems\mux_tb.sv" `
    --attempts 3 `
    --output "build\TopModule.sv" `
    --report "build\report.json"

Write-Host ""
Write-Host "Generation completed."
Write-Host "Verilog: D:\octotools\build\TopModule.sv"
Write-Host "Report:  D:\octotools\build\report.json"