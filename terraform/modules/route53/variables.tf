variable "alb_dns_name" {
  description = "Public DNS name of the ALB"
  type        = string
}

variable "alb_zone_id" {
  description = "Zone ID of the ALB, so Route53 can create an alias record for it"
  type        = string
}

variable "domain_name" {
  description = "The domain name to create the Route53 zone for"
  type        = string
}