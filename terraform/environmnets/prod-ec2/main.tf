terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_ecr_repository" "sayargyi" {
  name = "sayargyi-repo"
}

module "ec2" {
  source             = "../../modules/ec2"
  ecr_repository_arn = data.aws_ecr_repository.sayargyi.arn
}


module "ecr" {
  source          = "../../modules/ecr"
  repository_name = var.repository_name
}