output "alb_dns_name" {
  description = "Public DNS name of the ALB"
  value       = aws_lb.sayargyi.dns_name
}

output "target_group_arn" {
  description = "ARN of the target group ECS should register with"
  value       = aws_lb_target_group.sayargyi.arn
}

output "alb_security_group_id" {
  description = "Security group ID of the ALB, so ECS can allow traffic from it"
  value       = aws_security_group.alb.id
}

output "alb_zone_id" {
  description = "Zone ID of the ALB, so Route53 can create an alias record for it"
  value       = aws_lb.sayargyi.zone_id
}