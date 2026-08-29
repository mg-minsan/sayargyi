data "aws_vpc" "default" {
    default = true
}

data "aws_subnets" "default" {
    filter {
        name   = "vpc-id"
        values = [data.aws_vpc.default.id]
    }
}

data "aws_secretsmanager_secret" "openai_api_key" {
  name = "sayargyi/openai-api-key"
}

data "aws_secretsmanager_secret" "deepseek_api_key" {
  name = "sayargyi/deepseek-api-key"
}

data "aws_secretsmanager_secret" "meilisearch_key" {
  name = "sayargyi/meili-master-key"
}

data "aws_secretsmanager_secret" "pdc_agent_token" {
  name = "sayargyi/pdc-agent-token"
}

resource "aws_security_group" "allow_8501" {
  name        = "allow_8501"
  description = "Allow inbound traffic on port 8501 and all outbound traffic"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    description = "Streamlit app port"
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    security_groups = [var.alb_security_group_id]
  }
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "sayargyi_ecs_role" {
    name = "sayargyi_ecs_role"
    assume_role_policy = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
      }]
    })
}

resource "aws_iam_role_policy_attachment" "sayargyi_ecs_execution" {
  role       = aws_iam_role.sayargyi_ecs_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "secrets_access" {
  name = "sayargyi-secrets-access"
  role = aws_iam_role.sayargyi_ecs_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = [
        data.aws_secretsmanager_secret.openai_api_key.arn,
        data.aws_secretsmanager_secret.deepseek_api_key.arn,
        data.aws_secretsmanager_secret.meilisearch_key.arn,
        data.aws_secretsmanager_secret.pdc_agent_token.arn,
        var.db_password_secret_arn,
      ]
    }]
  })
}

resource "aws_iam_role" "sayargyi_ecs_task_role" {
  name = "sayargyi_ecs_task_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "ecs_exec" {
  name = "sayargyi-ecs-exec"
  role = aws_iam_role.sayargyi_ecs_task_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel",
      ]
      Resource = "*"
    }]
  })
}
  
resource "aws_cloudwatch_log_group" "sayargyi" {
    name              = "/ecs/sayargyi"
    retention_in_days = 7
}

resource "aws_ecs_task_definition" "sayargyi" {
    requires_compatibilities = ["FARGATE"]
    family = "service"
    network_mode             = "awsvpc"
    # cpu                      = "512"
    # memory                   = "1024"
    cpu                      = "512"
    memory                   = "1024"
    execution_role_arn       = aws_iam_role.sayargyi_ecs_role.arn
    task_role_arn            = aws_iam_role.sayargyi_ecs_task_role.arn
    volume {
        name = "sayargyi-efs"
        efs_volume_configuration {
            file_system_id = aws_efs_file_system.sayargyi.id
        }
    }
    container_definitions = jsonencode([{
        name     = "sayargyi"
        image    = "${var.ecr_repository_url}:latest"
        portMappings    = [{
            containerPort = 8501
            hostPort      = 8501
            protocol      = "tcp"
        }]
        logConfiguration = {
            logDriver = "awslogs"
            options = {
                "awslogs-group"         = aws_cloudwatch_log_group.sayargyi.name
                "awslogs-region"        = var.aws_region
                "awslogs-stream-prefix" = "sayargyi"
            }
        }
        environment = [
            {
                name  = "POSTGRES_HOST"
                value = var.db_host
            },
            {
                name  = "POSTGRES_DB"
                value = "sayargyi"
            },
            {
                name  = "POSTGRES_USER"
                value = "postgres"
            },
            {
                name = "MEILI_HOST"
                value = "http://localhost:7700"
            }
        ]
        secrets = [
            {
                name      = "OPENAI_API_KEY"
                valueFrom = data.aws_secretsmanager_secret.openai_api_key.arn
            },
            {
                name      = "DEEPSEEK_API_KEY"
                valueFrom = data.aws_secretsmanager_secret.deepseek_api_key.arn
            },
            {
                name      = "MEILI_MASTER_KEY"
                valueFrom = data.aws_secretsmanager_secret.meilisearch_key.arn
            },
            {
                name      = "POSTGRES_PASSWORD"
                valueFrom = "${var.db_password_secret_arn}:password::"
            }
        ]
    },
    {
        name     = "meilisearch"
        image    = "getmeili/meilisearch:v1.9"
        portMappings    = [{
            containerPort = 7700
            hostPort      = 7700
            protocol      = "tcp"
        }]
        secrets = [
            {
                name      = "MEILI_MASTER_KEY"
                valueFrom = data.aws_secretsmanager_secret.meilisearch_key.arn
            }
        ]
        logConfiguration = {
            logDriver = "awslogs"
            options = {
                "awslogs-group"         = aws_cloudwatch_log_group.sayargyi.name
                "awslogs-region"        = var.aws_region
                "awslogs-stream-prefix" = "meilisearch"
            }
        }
        mountPoints = [
            {
                sourceVolume  = "sayargyi-efs"
                containerPath = "/meili_data"
                readOnly      = false
            }
        ]
    }
    ])
}

resource "aws_ecs_cluster" "sayargyi" {
  name = "sayargyi-cluster"
}

resource "aws_ecs_service" "sayargyi" {
    depends_on = [aws_iam_role_policy_attachment.sayargyi_ecs_execution]
    name            = "sayargyi-service"
    cluster         = aws_ecs_cluster.sayargyi.id
    task_definition = aws_ecs_task_definition.sayargyi.arn
    desired_count   = 1
    launch_type     = "FARGATE"
    enable_execute_command = true
    load_balancer {
        target_group_arn = var.target_group_arn
        container_name   = "sayargyi"
        container_port   = 8501
    }
    network_configuration {
        subnets         = data.aws_subnets.default.ids
        security_groups = [aws_security_group.allow_8501.id]
        assign_public_ip = true
    }
}

resource "aws_efs_file_system" "sayargyi" {
  creation_token = "sayargyi-efs"

}

resource "aws_security_group" "efs" {
  name        = "allow_efs"
  description = "Allow inbound traffic on EFS and all outbound traffic"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    description = "EFS"
    from_port   = 2049
    to_port     = 2049
    protocol    = "tcp"
    security_groups = [aws_security_group.allow_8501.id]
  }
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    security_groups = [aws_security_group.allow_8501.id]
  }
}

resource "aws_efs_mount_target" "sayargyi" {
  for_each = toset(data.aws_subnets.default.ids)
  file_system_id  = aws_efs_file_system.sayargyi.id
  subnet_id       = each.value
  security_groups = [aws_security_group.efs.id]
}

# Grafana Cloud Private Datasource Connect agent: tunnels the hosted Grafana dashboard to RDS.
resource "aws_cloudwatch_log_group" "pdc_agent" {
  name              = "/ecs/pdc_agent"
  retention_in_days = 7
}

resource "aws_security_group" "pdc_agent" {
  name        = "pdc_agent"
  description = "No inbound; outbound HTTPS to Grafana Cloud and Postgres to RDS"
  vpc_id      = data.aws_vpc.default.id
  egress {
    description = "HTTPS to Grafana Cloud"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    description = "Postgres to RDS"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    description = "SSH tunnel to Grafana Cloud PDC gateway"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "pdc_agent" {
  family                   = "pdc-agent"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.sayargyi_ecs_role.arn
  task_role_arn            = aws_iam_role.sayargyi_ecs_task_role.arn
  container_definitions = jsonencode([{
    name      = "pdc-agent"
    image     = "grafana/pdc-agent:latest"
    essential = true
    command = [
      "-cluster", "prod-ap-southeast-1",
      "-gcloud-hosted-grafana-id", "1243720",
    ]
    secrets = [{
      name      = "GCLOUD_PDC_SIGNING_TOKEN"
      valueFrom = data.aws_secretsmanager_secret.pdc_agent_token.arn
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.pdc_agent.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "pdc-agent"
      }
    }
  }])
}

resource "aws_ecs_service" "pdc_agent" {
  name            = "pdc_agent_service"
  cluster         = aws_ecs_cluster.sayargyi.id
  task_definition = aws_ecs_task_definition.pdc_agent.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.pdc_agent.id]
    assign_public_ip = true
  }
}
