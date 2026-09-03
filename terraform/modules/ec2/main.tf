data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-resolute-26.04-arm64-server-20260604"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical
}

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

resource "aws_iam_role" "ec2" {
  name = "sayargyi-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "secrets_access" {
  name = "sayargyi-ec2-secrets-access"
  role = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = [
        data.aws_secretsmanager_secret.openai_api_key.arn,
        data.aws_secretsmanager_secret.deepseek_api_key.arn,
        data.aws_secretsmanager_secret.meilisearch_key.arn,
      ]
    }]
  })
}

# Pull the app image from ECR (GetAuthorizationToken must be on "*").
resource "aws_iam_role_policy" "ecr_pull" {
  name = "sayargyi-ec2-ecr-pull"
  role = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
        ]
        Resource = var.ecr_repository_arn
      }
    ]
  })
}

# Enables Session Manager (aws ssm start-session) without SSH keys or open port 22.
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2" {
  name = "sayargyi-ec2-profile"
  role = aws_iam_role.ec2.name
}

resource "aws_security_group" "app" {
  name        = "sayargyi-ec2"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22 
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}


resource "aws_instance" "sayargyi" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t4g.medium"
  subnet_id     = data.aws_subnets.default.ids[0]
  key_name = "sayargyi"
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  
  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = <<-EOF
    #!/bin/bash
    apt-get update
    apt-get install -y docker.io docker-compose-plugin git
    systemctl enable --now docker
  EOF
  tags = {
    Name = "sayargyi"
  }
}