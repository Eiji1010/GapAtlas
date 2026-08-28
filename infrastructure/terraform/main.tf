# GapAtlas のインフラ本体。構成の正本は docs/architecture.md「全体構成」。
#
#   API Gateway HTTP API -> Lambda API -> SQS -> Lambda Worker
#                                                 +- DynamoDB
#                                                 +- S3 -> Glue -> Athena
#
# **`terraform apply` は行わない**(docs/requirements.md「依頼書からの逸脱」)。
# 検証は `terraform init -backend=false` と `terraform validate` まで。
# そのためリモート state(backend)は設定しない。

terraform {
  required_version = "~> 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # タグはここで一括付与する。個々のリソースで tags を書かない。
  default_tags {
    tags = {
      Project     = "GapAtlas"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

locals {
  # リソース名の接頭辞。環境を分けても衝突しないようにする。
  name_prefix = "${var.project_name}-${var.environment}"

  # Glue テーブルの LOCATION。
  # backend/src/gapatlas/adapters/s3/keys.py の CURATED_PREFIX / CURATED_DATASET
  # (= "curated" / "gap_scores")と一致させること。末尾の "/" も
  # athena.py の curated_table_location() と揃える。
  curated_location = "s3://${var.s3_bucket_name}/curated/gap_scores/"
}
