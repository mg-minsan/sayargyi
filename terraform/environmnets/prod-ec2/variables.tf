variable "aws_region" {
  description = "The AWS region to deploy resources in"
  type        = string
  default     = "ap-southeast-1"
}

variable "repository_name" {
    description = "The name of the ECR repository"
    type        = string
}