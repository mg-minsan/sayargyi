data "aws_vpc" "default" {
    default = true
}

data "aws_subnets" "default" {
    filter {
        name   = "vpc-id"
        values = [data.aws_vpc.default.id]
    }
}

resource "aws_security_group" "rds-allow" {
  name        = "sayargyi-rds-allow"
  description = "Allow inbound traffic on port 8501 and all outbound traffic"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    description = "RDS Postgres port"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    security_groups = [var.ecs_security_group_id, var.pdc_security_group_id]
  }
  egress {
    description     = "Allow outbound to ECS only"
    from_port       = 0
    to_port         = 0
    protocol        = "-1"
    security_groups = [var.ecs_security_group_id, var.pdc_security_group_id]
  }
}

resource "aws_db_subnet_group" "sayargyi" {
  name       = "sayargyi-db-subnet-group"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_db_instance" "sayargyi" {
  allocated_storage    = 20
  db_name              = "sayargyi"
  engine               = "postgres"
  engine_version       = "16"
  instance_class       = "db.t4g.micro"
  username             = "postgres"
  skip_final_snapshot  = true
  vpc_security_group_ids = [aws_security_group.rds-allow.id]
  db_subnet_group_name = aws_db_subnet_group.sayargyi.name
  publicly_accessible = false
  manage_master_user_password = true
}