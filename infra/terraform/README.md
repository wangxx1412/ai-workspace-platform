# Terraform Infrastructure

This folder contains Terraform infrastructure for AI Workspace Platform.

## What This Provisions

This Terraform configuration provisions:

- ECR repository for backend Docker images
- CloudWatch log group for ECS logs
- S3 bucket for future RAG document storage
- ECS cluster
- ECS task execution role
- IAM permissions for SSM secret access
- Security groups
- Application Load Balancer
- Target group
- HTTP listener
- RDS PostgreSQL
- ECS task definition
- ECS Fargate backend service

## Architecture

```text
Vercel Frontend
 ↓
Vercel Rewrite Proxy
 ↓
AWS Application Load Balancer
 ↓
ECS Fargate Backend
 ↓
RDS PostgreSQL
 ↓
OpenAI API

CloudWatch collects logs.
SSM Parameter Store injects secrets.
```
