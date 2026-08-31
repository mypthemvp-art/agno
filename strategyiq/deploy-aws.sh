#!/usr/bin/env bash
set -euo pipefail

# StrategyIQ AWS ECS deployment script
# Usage: ./deploy-aws.sh [staging|production]

ENV="${1:-staging}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPO="strategyiq"
CLUSTER="strategyiq-${ENV}"
SERVICE_BACKEND="strategyiq-backend-${ENV}"
SERVICE_FRONTEND="strategyiq-frontend-${ENV}"

echo "Deploying StrategyIQ to ${ENV} in ${AWS_REGION}..."

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "Building backend image..."
docker build -t "${ECR_URI}:backend-${ENV}-latest" ./backend
docker push "${ECR_URI}:backend-${ENV}-latest"

echo "Building frontend image..."
docker build -t "${ECR_URI}:frontend-${ENV}-latest" ./frontend \
  --build-arg NEXT_PUBLIC_API_URL="https://api-${ENV}.strategyiq.io"
docker push "${ECR_URI}:frontend-${ENV}-latest"

echo "Forcing ECS service redeployment..."
aws ecs update-service \
  --cluster "${CLUSTER}" \
  --service "${SERVICE_BACKEND}" \
  --force-new-deployment \
  --region "${AWS_REGION}"

aws ecs update-service \
  --cluster "${CLUSTER}" \
  --service "${SERVICE_FRONTEND}" \
  --force-new-deployment \
  --region "${AWS_REGION}"

echo "Waiting for services to stabilize..."
aws ecs wait services-stable \
  --cluster "${CLUSTER}" \
  --services "${SERVICE_BACKEND}" "${SERVICE_FRONTEND}" \
  --region "${AWS_REGION}"

echo "Deployment to ${ENV} complete."
