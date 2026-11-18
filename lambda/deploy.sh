#!/usr/bin/env bash
# Despliega la Lambda proxy en las 3 regiones requeridas por Alexa Smart Home.
# Uso: AWS_PROFILE=hassdns-alexa bash deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

FN="hassdns-alexa-proxy"
ROLE="hassdns-alexa-lambda-exec"
PROFILE="${AWS_PROFILE:-hassdns-alexa}"
REGIONS="us-east-1 eu-west-1 us-west-2"
ACCOUNT=$(aws sts get-caller-identity --profile "$PROFILE" --query Account --output text)

zip -j -q /tmp/hassdns-alexa-proxy.zip handler.py

# Rol de ejecución (una vez, global)
if ! aws iam get-role --profile "$PROFILE" --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --profile "$PROFILE" --role-name "$ROLE" \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --profile "$PROFILE" --role-name "$ROLE" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  echo "rol $ROLE creado (esperando propagación…)"; sleep 10
fi

for R in $REGIONS; do
  if aws lambda get-function --profile "$PROFILE" --region "$R" --function-name "$FN" >/dev/null 2>&1; then
    aws lambda update-function-code --profile "$PROFILE" --region "$R" \
      --function-name "$FN" --zip-file fileb:///tmp/hassdns-alexa-proxy.zip --query FunctionArn --output text
  else
    aws lambda create-function --profile "$PROFILE" --region "$R" \
      --function-name "$FN" --runtime python3.12 --handler handler.handler \
      --role "arn:aws:iam::$ACCOUNT:role/$ROLE" --timeout 10 --memory-size 128 \
      --zip-file fileb:///tmp/hassdns-alexa-proxy.zip --query FunctionArn --output text
  fi
done
echo "OK — ARNs arriba (us-east-1, eu-west-1, us-west-2)"
