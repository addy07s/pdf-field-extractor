# Build, push, and roll out the FastAPI + React image to AWS ECS (us-east-1).
# Prerequisites: Docker Desktop running, AWS CLI configured.

$ErrorActionPreference = "Stop"

$Region = "us-east-1"
$AccountId = "712789090051"
$Repository = "pdf-field-extractor"
$ImageUri = "$AccountId.dkr.ecr.$Region.amazonaws.com/$Repository"
$Cluster = "pdf-extractor-cluster-2"
$Service = "pdf-extractor-task-service-unsxhlzw"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Building Docker image..."
docker build -t "${Repository}:latest" .

Write-Host "Logging in to ECR..."
aws ecr get-login-password --region $Region |
    docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"

Write-Host "Pushing image tags..."
docker tag "${Repository}:latest" "${ImageUri}:latest"
docker push "${ImageUri}:latest"

Write-Host "Forcing ECS rolling deployment..."
aws ecs update-service `
    --cluster $Cluster `
    --service $Service `
    --force-new-deployment `
    --region $Region `
    --output table

Write-Host "Done. Monitor rollout:"
Write-Host "  aws ecs describe-services --cluster $Cluster --services $Service --region $Region"
