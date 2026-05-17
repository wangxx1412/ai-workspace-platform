# ECR repository URL.
# Use this to tag and push the backend Docker image.
output "backend_ecr_repository_url" {
  description = "ECR repository URL for backend image"
  value       = aws_ecr_repository.backend.repository_url
}

# ALB DNS name.
# This is the backend public URL.
output "alb_dns_name" {
  description = "Application Load Balancer DNS name"
  value       = aws_lb.app.dns_name
}

# Backend base URL.
# Use this as BACKEND_API_URL in Vercel.
output "backend_api_url" {
  description = "Backend API URL through ALB"
  value       = "http://${aws_lb.app.dns_name}"
}

# RDS endpoint.
# Useful for debugging but do not expose publicly.
output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.address
}

# CloudWatch log group name.
# Use this to tail ECS backend logs.
output "backend_log_group_name" {
  description = "CloudWatch log group for backend"
  value       = aws_cloudwatch_log_group.backend.name
}

# S3 bucket for future RAG document storage.
output "documents_bucket_name" {
  description = "S3 bucket for RAG document storage"
  value       = aws_s3_bucket.documents.bucket
}

# ECS cluster name.
output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

# ECS service name.
output "ecs_service_name" {
  description = "ECS backend service name"
  value       = aws_ecs_service.backend.name
}