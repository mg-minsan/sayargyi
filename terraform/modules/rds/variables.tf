variable "ecs_security_group_id" {
  type        = string
  description = "Security group ID of the ECS, allowed to reach the RDS instance"
}

variable "pdc_security_group_id" {
  type        = string
  description = "Security group ID of the Grafana PDC agent, allowed to reach the RDS instance"
}