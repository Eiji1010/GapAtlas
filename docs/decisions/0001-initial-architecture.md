# ADR 0001: 初期アーキテクチャ

- Status: Accepted
- Date: 2026-08-28

## 背景

DevNetwork Hackathon 2026 向けの MVP を、限られた期間で「常に起動・テスト可能」な状態を保ちながら実装する必要がある。

## 決定

- Frontend は Cloudflare Pages、Backend は AWS(API Gateway HTTP API + Lambda + SQS + DynamoDB + S3 + Glue + Athena)とする
- Lambda を VPC に入れず、NAT Gateway を作らない
- 進捗更新は WebSocket / SSE ではなく 2秒 Polling とする
- 非同期処理は Step Functions ではなく SQS + Lambda Worker とする
- バックエンドの層は `api` / `application` / `domain` / `adapters` / `config` の5つに留める

## 理由

- 依頼書で ECS / EKS / RDS / Redis / WebSocket / Step Functions が明示的に禁止されている
- VPC + NAT Gateway は MVP に不要なコストと構築時間を発生させる
- Polling は実装が単純で、5か国 15〜30秒という SLO に対して十分
- 層を増やすと1機能の実装に触るファイルが増え、並行作業時の衝突が増える

## 結果

- Lambda から VPC 内リソースへアクセスできない。MVP では必要ない
- Polling により API 呼び出し回数は増えるが、DynamoDB の GetItem/Query のみで完結する
