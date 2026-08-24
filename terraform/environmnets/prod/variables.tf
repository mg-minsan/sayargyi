variable "aws_region" {
    description = "The AWS region to deploy resources"
    type        = string
    default     = "ap-southeast-1"
}

variable "repository_name" {
    description = "The name of the ECR repository"
    type        = string
}

variable "domain_name" {
    description = "The domain name to create the Route53 zone for"
    type        = string
}