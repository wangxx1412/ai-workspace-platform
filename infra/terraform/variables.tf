# AWS region where resources will be created.
# Example: us-west-2
variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-west-2"
}

# Application name used for naming AWS resources.
# Example resources: ai-workspace-tfdev-alb, ai-workspace-tfdev-cluster
variable "app_name" {
  description = "Application name used for resource naming"
  type        = string
  default     = "ai-workspace"
}

# Environment name.
# Use tfdev to avoid conflicts with manually created resources.
variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "tfdev"
}

# Name of the SSM Parameter Store entry that already stores the OpenAI API key.
# This parameter should be created manually before terraform apply.
variable "openai_api_key_parameter_name" {
  description = "SSM Parameter Store name for OpenAI API key"
  type        = string
  default     = "/ai-workspace/OPENAI_API_KEY"
}

# PostgreSQL database name.
variable "database_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "ai_workspace"
}

# PostgreSQL master username.
variable "database_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "postgres"
}

# PostgreSQL master password.
# This is required for RDS creation.
# Do not commit terraform.tfvars because this value is sensitive.
variable "database_password" {
  description = "PostgreSQL master password"
  type        = string
  sensitive   = true
}

# RDS instance class.
# db.t4g.micro is usually cost-effective, but some regions/accounts may require db.t3.micro.
variable "database_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

# Optional PostgreSQL engine version.
# Leave empty to let AWS choose the default supported version for the region.
variable "database_engine_version" {
  description = "PostgreSQL engine version. Leave empty to use AWS default."
  type        = string
  default     = ""
}

# Backend container port.
# FastAPI runs on port 8000.
variable "backend_container_port" {
  description = "Backend container port"
  type        = number
  default     = 8000
}

# Docker image tag for backend.
# Usually latest for learning projects.
variable "backend_image_tag" {
  description = "Backend Docker image tag"
  type        = string
  default     = "latest"
}

# ECS task CPU.
# 512 = 0.5 vCPU.
variable "ecs_cpu" {
  description = "ECS task CPU units"
  type        = string
  default     = "512"
}

# ECS task memory.
# 1024 = 1GB.
variable "ecs_memory" {
  description = "ECS task memory"
  type        = string
  default     = "1024"
}

# Number of backend tasks ECS should keep running.
variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

# Frontend URL used by FastAPI CORS.
# Example: https://your-vercel-app.vercel.app
variable "frontend_url" {
  description = "Frontend URL allowed by backend CORS"
  type        = string
}

# OpenAI model used by the backend.
variable "openai_model" {
  description = "OpenAI model name"
  type        = string
  default     = "gpt-4.1-mini"
}