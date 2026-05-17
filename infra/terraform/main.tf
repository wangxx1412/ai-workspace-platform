# Get current AWS account ID.
# This is used to build ARNs such as the SSM parameter ARN.
data "aws_caller_identity" "current" {}

# Use the default VPC for this learning deployment.
# Production systems usually use a custom VPC with public/private subnets.
data "aws_vpc" "default" {
  default = true
}

# Get subnets from the default VPC.
# In a default VPC, default subnets are usually public subnets.
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Generate a random suffix for globally unique names, such as S3 bucket names.
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

locals {
  # Common name prefix for resources.
  # Example: ai-workspace-tfdev
  name_prefix = "${var.app_name}-${var.environment}"

  # Backend container name used in ECS task definition and service.
  backend_container_name = "${var.app_name}-backend"

  # SSM parameter ARN for OpenAI API key.
  # We construct the ARN instead of reading the secret value into Terraform state.
  openai_api_key_parameter_arn = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.openai_api_key_parameter_name}"

  # Database URL that the FastAPI backend expects.
  # This will be stored in SSM as a SecureString and injected into ECS as a secret.
  database_url = "postgresql://${var.database_username}:${var.database_password}@${aws_db_instance.postgres.address}:5432/${var.database_name}"
}

# ------------------------------------------------------------------------------
# ECR
# ------------------------------------------------------------------------------

# ECR repository stores the backend Docker image.
resource "aws_ecr_repository" "backend" {
  name = "${local.name_prefix}-backend"

  # Enable image scanning on push for basic security visibility.
  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# CloudWatch
# ------------------------------------------------------------------------------

# CloudWatch log group receives stdout/stderr logs from ECS tasks.
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${local.name_prefix}-backend"
  retention_in_days = 7

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# S3
# ------------------------------------------------------------------------------

# S3 bucket prepared for future RAG document storage.
# Current app may still use local upload flow, but this bucket shows cloud-ready design.
resource "aws_s3_bucket" "documents" {
  bucket = "${local.name_prefix}-documents-${random_id.bucket_suffix.hex}"

  tags = {
    Project     = var.app_name
    Environment = var.environment
    Purpose     = "rag-document-storage"
  }
}

# Enable versioning for document bucket.
resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Block all public access to document bucket.
# RAG documents should not be public.
resource "aws_s3_bucket_public_access_block" "documents" {
  bucket = aws_s3_bucket.documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ------------------------------------------------------------------------------
# IAM
# ------------------------------------------------------------------------------

# ECS Task Execution Role.
# This role is used by ECS/Fargate to:
# - Pull Docker images from ECR
# - Write logs to CloudWatch
# - Read secrets from SSM Parameter Store
resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.name_prefix}-ecs-task-execution-role"

  # Trust policy allows ECS tasks service to assume this role.
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# Attach AWS managed policy required for ECS task execution.
resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Store DATABASE_URL in SSM Parameter Store.
# ECS will inject it into the container as a secret.
# Note: The value still exists in Terraform state, so use secure remote state in production.
resource "aws_ssm_parameter" "database_url" {
  name        = "/${var.app_name}/${var.environment}/DATABASE_URL"
  description = "Database URL for ${local.name_prefix} backend"
  type        = "SecureString"
  value       = local.database_url

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# Allow ECS execution role to read OpenAI API key and DATABASE_URL from SSM.
resource "aws_iam_role_policy" "ecs_ssm_read" {
  name = "${local.name_prefix}-ssm-read-policy"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          local.openai_api_key_parameter_arn,
          aws_ssm_parameter.database_url.arn
        ]
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# Security Groups
# ------------------------------------------------------------------------------

# ALB security group.
# Allows public HTTP traffic on port 80.
resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Security group for public ALB"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Allow public HTTP traffic to ALB"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow outbound traffic from ALB"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# Backend security group.
# Allows only ALB to access backend container port 8000.
resource "aws_security_group" "backend" {
  name        = "${local.name_prefix}-backend-sg"
  description = "Security group for ECS backend service"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "Allow ALB to reach FastAPI backend"
    from_port       = var.backend_container_port
    to_port         = var.backend_container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Allow backend outbound traffic to RDS, OpenAI, SSM, CloudWatch"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# RDS security group.
# Allows only backend ECS tasks to access PostgreSQL on port 5432.
resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "Allow backend ECS tasks to connect to PostgreSQL"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  egress {
    description = "Allow outbound traffic from RDS"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# RDS PostgreSQL
# ------------------------------------------------------------------------------

# RDS subnet group tells AWS which subnets RDS can use.
# For learning, we use default VPC subnets.
# For production, use private subnets.
resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet-group"
  subnet_ids = data.aws_subnets.default.ids

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# RDS PostgreSQL instance.
# This stores conversations, messages, documents, chunks, and pgvector data.
resource "aws_db_instance" "postgres" {
  identifier = "${local.name_prefix}-postgres"

  engine         = "postgres"
  engine_version = var.database_engine_version == "" ? null : var.database_engine_version

  instance_class    = var.database_instance_class
  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = var.database_name
  username = var.database_username
  password = var.database_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible = false

  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# Load Balancer
# ------------------------------------------------------------------------------

# Application Load Balancer exposes the backend publicly over HTTP.
resource "aws_lb" "app" {
  name               = "${local.name_prefix}-alb"
  load_balancer_type = "application"
  internal           = false

  security_groups = [aws_security_group.alb.id]
  subnets         = data.aws_subnets.default.ids

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# Target group represents backend ECS tasks behind the ALB.
# target_type = ip is required for Fargate awsvpc networking.
resource "aws_lb_target_group" "backend" {
  name        = "${local.name_prefix}-backend-tg"
  port        = var.backend_container_port
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    port                = "traffic-port"
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# Listener tells ALB how to handle incoming HTTP traffic.
# Port 80 requests are forwarded to the backend target group.
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

# ------------------------------------------------------------------------------
# ECS
# ------------------------------------------------------------------------------

# ECS cluster hosts the backend Fargate service.
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# ECS task definition is the blueprint for running the backend container.
# It defines image, CPU, memory, ports, environment variables, secrets, and logging.
resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name_prefix}-backend-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]

  cpu    = var.ecs_cpu
  memory = var.ecs_memory

  execution_role_arn = aws_iam_role.ecs_task_execution.arn

  # Use X86_64 because the backend image is built with linux/amd64.
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = local.backend_container_name
      image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
      essential = true

      portMappings = [
        {
          containerPort = var.backend_container_port
          hostPort      = var.backend_container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "OPENAI_MODEL"
          value = var.openai_model
        },
        {
          name  = "FRONTEND_URL"
          value = var.frontend_url
        }
      ]

      secrets = [
        {
          name      = "OPENAI_API_KEY"
          valueFrom = local.openai_api_key_parameter_arn
        },
        {
          name      = "DATABASE_URL"
          valueFrom = aws_ssm_parameter.database_url.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.backend.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  depends_on = [
    aws_iam_role_policy_attachment.ecs_task_execution_policy,
    aws_iam_role_policy.ecs_ssm_read
  ]

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}

# ECS service keeps the backend task running and registers it with the ALB target group.
resource "aws_ecs_service" "backend" {
  name            = "${local.name_prefix}-backend-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn

  desired_count = var.ecs_desired_count
  launch_type   = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.backend.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = local.backend_container_name
    container_port   = var.backend_container_port
  }

  depends_on = [
    aws_lb_listener.http
  ]

  tags = {
    Project     = var.app_name
    Environment = var.environment
  }
}