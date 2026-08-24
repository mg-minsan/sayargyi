output "security_group_id" {
  description = "Security group ID of the ECS, allowed to reach the RDS instance"
  value       = aws_security_group.allow_8501.id
}