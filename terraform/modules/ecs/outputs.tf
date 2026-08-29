output "security_group_id" {
  description = "Security group ID of the ECS, allowed to reach the RDS instance"
  value       = aws_security_group.allow_8501.id
}

output "pdc_security_group_id" {
  description = "Security group ID of the Grafana PDC agent, allowed to reach the RDS instance"
  value       = aws_security_group.pdc_agent.id
}