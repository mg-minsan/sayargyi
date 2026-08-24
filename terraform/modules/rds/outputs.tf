output rds_endpoint {
  description = "The endpoint of the RDS instance"
  value       = aws_db_instance.sayargyi.endpoint
}

output rds_master_password_arn {
  description = "The ARN of the secret containing the RDS master password"
  value       = aws_db_instance.sayargyi.master_user_secret[0].secret_arn
}

output rds_address {
  description = "The address of the RDS instance"
  value       = aws_db_instance.sayargyi.address
}