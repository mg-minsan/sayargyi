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

module "ecr" {
  source          = "../../modules/ecr"
  repository_name = var.repository_name
}

module "ecs" {
  source             = "../../modules/ecs"
  ecr_repository_url = module.ecr.repository_url
  aws_region         = var.aws_region
  target_group_arn    = module.alb.target_group_arn
  alb_security_group_id = module.alb.alb_security_group_id
  db_host             = module.rds.rds_address
  db_password_secret_arn = module.rds.rds_master_password_arn
}

module "alb" {
  source          = "../../modules/alb"
  certificate_arn = module.acm.certificate_arn
}

module "rds" {
  source = "../../modules/rds"
  ecs_security_group_id = module.ecs.security_group_id
}

module "route53" {
  source = "../../modules/route53"
  domain_name =  var.domain_name
  alb_dns_name = module.alb.alb_dns_name
  alb_zone_id  = module.alb.alb_zone_id
}

module "acm" {
  source      = "../../modules/acm"
  domain_name =  var.domain_name
  zone_id     = module.route53.zone_id
}