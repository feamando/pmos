#!/bin/bash
# claude_bedrock_login.sh
# claude_bedrock_login "bedrock-user"

# Function to load AWS SSO credentials for Claude CLI with Bedrock integration
claude_bedrock_login() {
 local profile="$1"
 aws sso login --profile "$profile"

 echo "Logging in with profile: $profile"
 # Use AWS CLI to get current credentials for the SSO profile
 creds_json=$(aws sts get-caller-identity --profile "$profile" >/dev/null 2>&1 &&
  aws configure export-credentials --profile "$profile" --format env)

 if [ -z "$creds_json" ]; then
  echo "SSO credentials missing or expired. Run: aws sso login --profile $profile"
  return 1
 fi
 eval "$creds_json"
 export AWS_PROFILE="$profile"
 export AWS_REGION="eu-west-1" # Set your region
 export CLAUDE_CODE_USE_BEDROCK=1
 # Optionally: export DISABLE_PROMPT_CACHING=1
 echo "AWS credentials for $profile loaded for Claude CLI."
}