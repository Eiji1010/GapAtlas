GapAtlas Lambda deployment package placeholder.

このディレクトリは、実際の Lambda デプロイパッケージが無い状態でも
`terraform validate` と `terraform plan` が通るようにするためのダミーです。
中身は zip 化されて aws_lambda_function.filename に渡されます。

**この zip をそのままデプロイしてもハンドラは見つかりません。**
実際のパッケージの作り方は infrastructure/README.md
「Lambda デプロイパッケージの作り方」を参照してください。

作成したパッケージを使うときは、展開先ディレクトリを
`lambda_package_source_dir` 変数に渡します。
