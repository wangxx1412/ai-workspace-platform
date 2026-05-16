# AWS Deployment Plan

## Goal

Deploy AI Workspace Platform as a production-style cloud application using AWS container and managed database services.

## Target Architecture

```text
User
 ↓
Vercel Frontend
 ↓
AWS Application Load Balancer
 ↓
ECS Fargate Backend Service
 ↓
RDS PostgreSQL
 ↓
OpenAI API

CloudWatch collects backend logs.
SSM or Secrets Manager stores secrets.
S3 stores uploaded documents for future RAG.
```
