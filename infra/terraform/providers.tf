# Define the Terraform version and required providers.
# This project uses the AWS provider to create cloud infrastructure.
terraform {
  required_version = ">= 1.5.7"

  required_providers {
    # AWS provider manages AWS resources such as ECS, RDS, ALB, IAM, S3, etc.
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }

    # Random provider is used to generate a unique suffix for globally unique resources like S3 buckets.
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# Configure the AWS provider.
# var.aws_region comes from variables.tf / terraform.tfvars.
provider "aws" {
  region = var.aws_region
}