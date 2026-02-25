terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_s3_bucket" "data_bucket" {
  bucket = "agentic-apothecary-data-637423406602"
}

resource "aws_dynamodb_table" "inventory_table" {
  name           = "Inventory"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "product_id"

  attribute {
    name = "product_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "patient_state_table" {
  name           = "PatientState"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "patient_id"

  attribute {
    name = "patient_id"
    type = "S"
  }
}

resource "aws_security_group" "ec2_sg" {
  name        = "agentic_apothecary_sg"
  description = "Allow SSH and Streamlit"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 8501
    to_port     = 8501
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

resource "aws_instance" "app_server" {
  ami           = "ami-0fb0b230890ccd1e6"
  instance_type = "t2.micro"
  key_name      = "vockey"
  vpc_security_group_ids = [aws_security_group.ec2_sg.id]

  tags = {
    Name = "Agentic-Apothecary-Server"
  }
}

resource "aws_sns_topic" "order_notifications" {
  name = "order-notifications"
}

output "instance_public_ip" {
  value = aws_instance.app_server.public_ip
}

output "bucket_name" {
  value = aws_s3_bucket.data_bucket.id
}

output "sns_topic_arn" {
  value = aws_sns_topic.order_notifications.arn
}
