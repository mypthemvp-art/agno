#!/usr/bin/env bash
set -euo pipefail

ENV="${1:-staging}"
AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER="strategyiq-${ENV}"

echo "Deploying StrategyIQ ${ENV} to ECS..."

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/strategyiq"

aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker build -f infra/Dockerfile -t "${ECR}:backend-${ENV}" .
docker push "${ECR}:backend-${ENV}"

docker build -f frontend/Dockerfile -t "${ECR}:frontend-${ENV}" frontend/
docker push "${ECR}:frontend-${ENV}"

for svc in strategyiq-backend strategyiq-frontend strategyiq-celery; do
  aws ecs update-service --cluster "$CLUSTER" --service "${svc}-${ENV}" --force-new-deployment --region "$AWS_REGION" || true
done

echo "Deployment triggered for ${ENV}."
