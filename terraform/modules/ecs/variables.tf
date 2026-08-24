variable "ecr_repository_url" {
    type = string
    description = "The URL of the ECR repository"
}

variable "aws_region" {
  description = "The AWS region to deploy resources"
  type        = string
  default = "ap-southeast-1"
}

variable "target_group_arn" {
  type        = string
  description = "ARN of the ALB target group to register the ECS service with"
}

variable "alb_security_group_id" {
  type        = string
  description = "Security group ID of the ALB, allowed to reach the ECS task"
}

variable "db_host" {
  type        = string
  description = "Hostname of the RDS database"
}

variable "db_password_secret_arn" {
  type        = string
  description = "ARN of the AWS Secrets Manager secret containing the RDS database password"
}