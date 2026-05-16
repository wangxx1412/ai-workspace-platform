# AWS Deployment Notes

This document summarizes the manual AWS deployment for AI Workspace Platform.

The goal was to deploy the FastAPI backend as a containerized service on AWS and connect it to a managed PostgreSQL database, while keeping the frontend on Vercel.

---

## Final Deployment Architecture

```text
Vercel Frontend
 ↓
Vercel Rewrite Proxy
 ↓
AWS Application Load Balancer
 ↓
ECS Fargate Backend Service
 ↓
RDS PostgreSQL
 ↓
OpenAI API

ECR stores the backend Docker image.
CloudWatch collects backend logs.
SSM Parameter Store injects OPENAI_API_KEY.
```

---

## AWS Services Used

| Service             | Purpose                             |
| ------------------- | ----------------------------------- |
| ECR                 | Store backend Docker image          |
| ECS Fargate         | Run FastAPI backend container       |
| ALB                 | Public HTTP entry point for backend |
| Target Group        | Route ALB traffic to ECS tasks      |
| RDS PostgreSQL      | Managed PostgreSQL database         |
| CloudWatch Logs     | Collect backend logs                |
| SSM Parameter Store | Store OpenAI API key                |
| IAM                 | ECS task execution permissions      |
| Security Groups     | Network access control              |

---

## Deployment Steps

## 1. Set Variables

```bash
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

export APP_NAME=ai-workspace
export ECR_REPO=ai-workspace-backend

export IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:latest"
```

---

## 2. Build and Push Backend Image to ECR

Create ECR repository:

```bash
aws ecr create-repository \
  --region $AWS_REGION \
  --repository-name $ECR_REPO
```

Login to ECR:

```bash
aws ecr get-login-password --region $AWS_REGION | \
docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
```

Build for ECS-compatible platform:

```bash
docker buildx build \
  --platform linux/amd64 \
  -t $IMAGE_URI \
  ./backend \
  --push
```

Important note:

If building from Apple Silicon Mac, always specify:

```bash
--platform linux/amd64
```

Otherwise ECS Fargate may fail with:

```text
image Manifest does not contain descriptor matching platform 'linux/amd64'
```

---

## 3. Get VPC and Public Subnets

Use the default VPC for the learning deployment.

```bash
export VPC_ID=$(aws ec2 describe-vpcs \
  --region $AWS_REGION \
  --filters "Name=is-default,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text)
```

Get two public subnets:

```bash
export PUBLIC_SUBNET_1=$(aws ec2 describe-subnets \
  --region $AWS_REGION \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=map-public-ip-on-launch,Values=true" \
  --query "Subnets[0].SubnetId" \
  --output text)

export PUBLIC_SUBNET_2=$(aws ec2 describe-subnets \
  --region $AWS_REGION \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=map-public-ip-on-launch,Values=true" \
  --query "Subnets[1].SubnetId" \
  --output text)
```

Check:

```bash
echo $VPC_ID
echo $PUBLIC_SUBNET_1
echo $PUBLIC_SUBNET_2
```

---

## 4. Create RDS PostgreSQL

Create RDS security group:

```bash
aws ec2 create-security-group \
  --region $AWS_REGION \
  --group-name ${APP_NAME}-rds-sg \
  --description "Security group for ${APP_NAME} RDS" \
  --vpc-id $VPC_ID
```

Get security group ID:

```bash
export RDS_SG_ID=$(aws ec2 describe-security-groups \
  --region $AWS_REGION \
  --filters "Name=group-name,Values=${APP_NAME}-rds-sg" "Name=vpc-id,Values=$VPC_ID" \
  --query "SecurityGroups[0].GroupId" \
  --output text)
```

Create DB subnet group:

```bash
aws rds create-db-subnet-group \
  --region $AWS_REGION \
  --db-subnet-group-name ${APP_NAME}-db-subnet-group \
  --db-subnet-group-description "DB subnet group for ${APP_NAME}" \
  --subnet-ids $PUBLIC_SUBNET_1 $PUBLIC_SUBNET_2
```

Create RDS instance:

```bash
export DB_USERNAME=postgres
export DB_PASSWORD='ChangeThisPassword123'
export DB_NAME=ai_workspace

aws rds create-db-instance \
  --region $AWS_REGION \
  --db-instance-identifier ${APP_NAME}-postgres \
  --db-instance-class db.t4g.micro \
  --engine postgres \
  --allocated-storage 20 \
  --storage-type gp3 \
  --db-name $DB_NAME \
  --master-username $DB_USERNAME \
  --master-user-password "$DB_PASSWORD" \
  --vpc-security-group-ids $RDS_SG_ID \
  --db-subnet-group-name ${APP_NAME}-db-subnet-group \
  --backup-retention-period 1 \
  --no-publicly-accessible
```

If `db.t4g.micro` is unavailable, use:

```bash
--db-instance-class db.t3.micro
```

Wait until available:

```bash
aws rds wait db-instance-available \
  --region $AWS_REGION \
  --db-instance-identifier ${APP_NAME}-postgres
```

Get endpoint:

```bash
export RDS_ENDPOINT=$(aws rds describe-db-instances \
  --region $AWS_REGION \
  --db-instance-identifier ${APP_NAME}-postgres \
  --query "DBInstances[0].Endpoint.Address" \
  --output text)
```

Build database URL:

```bash
export DATABASE_URL="postgresql://${DB_USERNAME}:${DB_PASSWORD}@${RDS_ENDPOINT}:5432/${DB_NAME}"
```

---

## 5. Create CloudWatch Log Group

```bash
aws logs create-log-group \
  --region $AWS_REGION \
  --log-group-name /ecs/${APP_NAME}-backend
```

Set retention:

```bash
aws logs put-retention-policy \
  --region $AWS_REGION \
  --log-group-name /ecs/${APP_NAME}-backend \
  --retention-in-days 7
```

---

## 6. Create ECS Cluster

```bash
aws ecs create-cluster \
  --region $AWS_REGION \
  --cluster-name ${APP_NAME}-cluster
```

---

## 7. Create ECS Task Execution Role

Create trust policy:

```bash
cat > ecs-task-execution-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
```

Create role:

```bash
aws iam create-role \
  --role-name ${APP_NAME}-ecs-task-execution-role \
  --assume-role-policy-document file://ecs-task-execution-trust-policy.json
```

Attach ECS execution policy:

```bash
aws iam attach-role-policy \
  --role-name ${APP_NAME}-ecs-task-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

Get role ARN:

```bash
export ECS_EXECUTION_ROLE_ARN=$(aws iam get-role \
  --role-name ${APP_NAME}-ecs-task-execution-role \
  --query "Role.Arn" \
  --output text)
```

---

## 8. Store OpenAI API Key in SSM

```bash
aws ssm put-parameter \
  --region $AWS_REGION \
  --name "/${APP_NAME}/OPENAI_API_KEY" \
  --type "SecureString" \
  --value "your_openai_api_key_here" \
  --overwrite
```

Get parameter ARN:

```bash
export OPENAI_PARAM_ARN=$(aws ssm get-parameter \
  --region $AWS_REGION \
  --name "/${APP_NAME}/OPENAI_API_KEY" \
  --query "Parameter.ARN" \
  --output text)
```

Allow ECS execution role to read it:

```bash
cat > ssm-read-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters"
      ],
      "Resource": "${OPENAI_PARAM_ARN}"
    }
  ]
}
EOF
```

```bash
aws iam put-role-policy \
  --role-name ${APP_NAME}-ecs-task-execution-role \
  --policy-name ${APP_NAME}-ssm-read-policy \
  --policy-document file://ssm-read-policy.json
```

---

## 9. Create Security Groups

Create backend security group:

```bash
aws ec2 create-security-group \
  --region $AWS_REGION \
  --group-name ${APP_NAME}-backend-sg \
  --description "Security group for ECS backend" \
  --vpc-id $VPC_ID
```

```bash
export BACKEND_SG_ID=$(aws ec2 describe-security-groups \
  --region $AWS_REGION \
  --filters "Name=group-name,Values=${APP_NAME}-backend-sg" "Name=vpc-id,Values=$VPC_ID" \
  --query "SecurityGroups[0].GroupId" \
  --output text)
```

Allow backend to access RDS:

```bash
aws ec2 authorize-security-group-ingress \
  --region $AWS_REGION \
  --group-id $RDS_SG_ID \
  --protocol tcp \
  --port 5432 \
  --source-group $BACKEND_SG_ID
```

Create ALB security group:

```bash
aws ec2 create-security-group \
  --region $AWS_REGION \
  --group-name ${APP_NAME}-alb-sg \
  --description "Security group for ALB" \
  --vpc-id $VPC_ID
```

```bash
export ALB_SG_ID=$(aws ec2 describe-security-groups \
  --region $AWS_REGION \
  --filters "Name=group-name,Values=${APP_NAME}-alb-sg" "Name=vpc-id,Values=$VPC_ID" \
  --query "SecurityGroups[0].GroupId" \
  --output text)
```

Allow public HTTP to ALB:

```bash
aws ec2 authorize-security-group-ingress \
  --region $AWS_REGION \
  --group-id $ALB_SG_ID \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0
```

Allow ALB to backend:

```bash
aws ec2 authorize-security-group-ingress \
  --region $AWS_REGION \
  --group-id $BACKEND_SG_ID \
  --protocol tcp \
  --port 8000 \
  --source-group $ALB_SG_ID
```

---

## 10. Create ALB, Target Group, and Listener

Create ALB:

```bash
aws elbv2 create-load-balancer \
  --region $AWS_REGION \
  --name ${APP_NAME}-alb \
  --subnets $PUBLIC_SUBNET_1 $PUBLIC_SUBNET_2 \
  --security-groups $ALB_SG_ID \
  --scheme internet-facing \
  --type application \
  --ip-address-type ipv4
```

Get ALB ARN and DNS:

```bash
export ALB_ARN=$(aws elbv2 describe-load-balancers \
  --region $AWS_REGION \
  --names ${APP_NAME}-alb \
  --query "LoadBalancers[0].LoadBalancerArn" \
  --output text)

export ALB_DNS=$(aws elbv2 describe-load-balancers \
  --region $AWS_REGION \
  --names ${APP_NAME}-alb \
  --query "LoadBalancers[0].DNSName" \
  --output text)
```

Create target group:

```bash
aws elbv2 create-target-group \
  --region $AWS_REGION \
  --name ${APP_NAME}-backend-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /health \
  --health-check-protocol HTTP \
  --health-check-port traffic-port
```

```bash
export TARGET_GROUP_ARN=$(aws elbv2 describe-target-groups \
  --region $AWS_REGION \
  --names ${APP_NAME}-backend-tg \
  --query "TargetGroups[0].TargetGroupArn" \
  --output text)
```

Create listener:

```bash
aws elbv2 create-listener \
  --region $AWS_REGION \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TARGET_GROUP_ARN
```

---

## 11. Register ECS Task Definition

Create task definition JSON:

```bash
cat > ecs-task-definition.json << EOF
{
  "family": "${APP_NAME}-backend-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "${ECS_EXECUTION_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "${APP_NAME}-backend",
      "image": "${IMAGE_URI}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "OPENAI_MODEL",
          "value": "gpt-4.1-mini"
        },
        {
          "name": "DATABASE_URL",
          "value": "${DATABASE_URL}"
        },
        {
          "name": "FRONTEND_URL",
          "value": "https://your-vercel-domain.vercel.app"
        }
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "${OPENAI_PARAM_ARN}"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${APP_NAME}-backend",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF
```

Register it:

```bash
aws ecs register-task-definition \
  --region $AWS_REGION \
  --cli-input-json file://ecs-task-definition.json
```

Get latest task definition ARN:

```bash
export TASK_DEFINITION_ARN=$(aws ecs describe-task-definition \
  --region $AWS_REGION \
  --task-definition ${APP_NAME}-backend-task \
  --query "taskDefinition.taskDefinitionArn" \
  --output text)
```

---

## 12. Create ECS Fargate Service

```bash
aws ecs create-service \
  --region $AWS_REGION \
  --cluster ${APP_NAME}-cluster \
  --service-name ${APP_NAME}-backend-service \
  --task-definition $TASK_DEFINITION_ARN \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$PUBLIC_SUBNET_1,$PUBLIC_SUBNET_2],securityGroups=[$BACKEND_SG_ID],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=$TARGET_GROUP_ARN,containerName=${APP_NAME}-backend,containerPort=8000"
```

Check service:

```bash
aws ecs describe-services \
  --region $AWS_REGION \
  --cluster ${APP_NAME}-cluster \
  --services ${APP_NAME}-backend-service \
  --query "services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}"
```

Expected:

```json
{
  "desired": 1,
  "running": 1,
  "pending": 0
}
```

---

## 13. Test Backend

```bash
curl http://$ALB_DNS/health
```

Expected:

```json
{
  "status": "ok",
  "database": "ok",
  "service": "ai-workspace-api"
}
```

View logs:

```bash
aws logs tail /ecs/${APP_NAME}-backend \
  --region $AWS_REGION \
  --since 30m
```

---

## 14. Configure Vercel Frontend

Set Vercel environment variables:

```env
NEXT_PUBLIC_API_BASE_URL=/backend
BACKEND_API_URL=http://your-alb-dns-name
```

Use Next.js rewrites in `frontend/next.config.ts`:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${process.env.BACKEND_API_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
```

This avoids browser mixed-content issues by making browser requests go to:

```text
https://vercel-app.vercel.app/backend/*
```

Vercel then proxies the request to:

```text
http://aws-alb-dns/*
```

---

## Issues Encountered and Fixes

### 1. RDS PostgreSQL Version Not Found

Error:

```text
Cannot find version 16.3 for postgres
```

Fix:

Do not hardcode the engine version, or query supported versions first.

```bash
aws rds describe-db-engine-versions \
  --region $AWS_REGION \
  --engine postgres \
  --query "DBEngineVersions[*].EngineVersion" \
  --output text
```

---

### 2. ECS Image Platform Mismatch

Error:

```text
image Manifest does not contain descriptor matching platform 'linux/amd64'
```

Cause:

Docker image was built on Apple Silicon as ARM64.

Fix:

```bash
docker buildx build \
  --platform linux/amd64 \
  -t $IMAGE_URI \
  ./backend \
  --push
```

---

### 3. OpenAI API Key Not Injected

Cause:

ECS task definition did not correctly inject `OPENAI_API_KEY` from SSM.

Fix:

Use full SSM parameter ARN in task definition:

```json
"secrets": [
  {
    "name": "OPENAI_API_KEY",
    "valueFrom": "arn:aws:ssm:REGION:ACCOUNT_ID:parameter/ai-workspace/OPENAI_API_KEY"
  }
]
```

Ensure ECS execution role has:

```text
ssm:GetParameter
ssm:GetParameters
```

---

### 4. Vercel Mixed Content

Problem:

Vercel frontend uses HTTPS, but ALB backend was HTTP.

Fix:

Use Vercel rewrite proxy:

```text
NEXT_PUBLIC_API_BASE_URL=/backend
BACKEND_API_URL=http://ALB-DNS
```

---

## Important Notes

Do not commit generated AWS JSON files containing real values:

```text
ecs-task-definition.json
ssm-read-policy.json
ecs-task-execution-trust-policy.json
```

Add them to `.gitignore`.

Safe future direction:

```text
infra/terraform/
```

Use Terraform templates instead of committing temporary manual deployment JSON files.

---

## Cleanup

To avoid AWS charges, clean up resources when no longer needed.

Scale ECS service to zero:

```bash
aws ecs update-service \
  --region $AWS_REGION \
  --cluster ${APP_NAME}-cluster \
  --service ${APP_NAME}-backend-service \
  --desired-count 0
```

Delete ECS service:

```bash
aws ecs delete-service \
  --region $AWS_REGION \
  --cluster ${APP_NAME}-cluster \
  --service ${APP_NAME}-backend-service \
  --force
```

Delete RDS instance:

```bash
aws rds delete-db-instance \
  --region $AWS_REGION \
  --db-instance-identifier ${APP_NAME}-postgres \
  --skip-final-snapshot \
  --delete-automated-backups
```

Delete ALB and target group through AWS Console or CLI after removing listener.

---

## Summary

This deployment proves the project can run as a cloud-hosted AI application:

```text
Vercel Frontend
→ AWS ALB
→ ECS Fargate Backend
→ RDS PostgreSQL
→ SSM Secrets
→ CloudWatch Logs
→ OpenAI API
```
